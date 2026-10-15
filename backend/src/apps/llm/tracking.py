"""聊天模型的观测包装和输入预算检查。"""

import asyncio
import logging
import time
from typing import Any, AsyncIterator

from anthropic import APITimeoutError as AnthropicTimeoutError
from httpx import TimeoutException
from langchain_core.messages import BaseMessage
from openai import APITimeoutError as OpenAITimeoutError

from apps.core.config import get_settings, settings_context
from apps.core.errors import DomainError
from apps.core.logging import redact
from apps.core.request_context import get_request_id
from apps.llm.metrics import RunMetricsCollector, build_step_metrics, log_llm_step
from apps.llm.runtime import LLMRuntime, current_llm_runtime, get_llm_runtime
from apps.llm.token_budget import (
    BudgetExceededError,
    check_budget,
    estimate_tokens,
    log_token_budget_warn,
)

logger = logging.getLogger(__name__)
MODEL_TIMEOUTS = (asyncio.TimeoutError, AnthropicTimeoutError, OpenAITimeoutError, TimeoutException)


def _discard_result(task: asyncio.Future[Any]) -> None:
    if not task.cancelled():
        task.exception()


async def _bounded_model_task(task: asyncio.Future[Any], timeout: float) -> Any:
    """Stop awaiting at the deadline even if a provider suppresses cancellation."""
    try:
        done, _ = await asyncio.wait({task}, timeout=timeout)
        if done:
            return task.result()
    except asyncio.CancelledError:
        task.cancel()
        task.add_done_callback(_discard_result)
        raise
    task.cancel()
    task.add_done_callback(_discard_result)
    # Give cooperative SDK clients one turn to release their sockets, without
    # waiting for a provider that ignores the cancellation request.
    await asyncio.sleep(0)
    raise asyncio.TimeoutError


async def _next_stream_chunk(
    queue: asyncio.Queue[Any], provider: asyncio.Future[Any], timeout: float
) -> Any:
    if not queue.empty():
        return queue.get_nowait()
    if provider.done():
        provider.result()
        raise StopAsyncIteration
    take = asyncio.create_task(queue.get())
    try:
        done, _ = await asyncio.wait(
            {take, provider}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
        )
        if take in done:
            return take.result()
        if provider in done:
            if not queue.empty():
                return queue.get_nowait()
            provider.result()
            raise StopAsyncIteration
        raise asyncio.TimeoutError
    finally:
        if not take.done():
            take.cancel()
        take.add_done_callback(_discard_result)


class TrackedChatModel:
    """包装 LLM，记录 step 耗时与 token 用量"""

    def __init__(self, llm: Any, step: str):
        self._llm = llm
        self._step = step
        self._settings = get_settings()
        self._model_name = self._settings.default_llm_model or "unknown"
        self._runtime = current_llm_runtime()

    def _get_runtime(self) -> LLMRuntime:
        return self._runtime or get_llm_runtime(self._settings.job_max_concurrency)

    def _run_budget_check(self, messages: list[BaseMessage]) -> None:
        with settings_context(self._settings):
            token_estimate = estimate_tokens(messages, step=self._step, model=self._model_name)
            budget_check = check_budget(token_estimate, step=self._step, model=self._model_name)
            log_token_budget_warn(budget_check)
            run = RunMetricsCollector.current()
            if run is not None:
                run.set_budget(budget_check)
            if not budget_check.allowed:
                raise BudgetExceededError(budget_check)

    def _record_step(
        self,
        usage: Any,
        duration_ms: int,
        status: str,
        error: str = "",
    ) -> None:
        with settings_context(self._settings):
            record = build_step_metrics(
                self._step,
                self._model_name,
                usage,
                duration_ms,
                status,
                redact(error)[:200],
            )
            run = RunMetricsCollector.current()
            if run is not None:
                run.add_step(record)
            log_llm_step({**record.to_dict(), "request_id": get_request_id()})

    async def ainvoke(self, messages: list[BaseMessage], **kwargs: Any) -> Any:
        self._run_budget_check(messages)
        started = time.perf_counter()
        try:
            task = await self._get_runtime().start(
                lambda: self._llm.ainvoke(messages, **kwargs),
                capacity_timeout=self._settings.llm_call_timeout,
            )
            try:
                response = await _bounded_model_task(task, self._settings.llm_call_timeout)
            except MODEL_TIMEOUTS as exc:
                raise DomainError(
                    "模型调用超时，请重试",
                    code="LLM_CALL_TIMEOUT",
                    status_code=504,
                    retryable=True,
                ) from exc
            duration_ms = int((time.perf_counter() - started) * 1000)
            usage = getattr(response, "usage_metadata", None)
            self._record_step(usage, duration_ms, "ok")
            return response
        except BudgetExceededError:
            raise
        except asyncio.CancelledError:
            self._record_step({}, int((time.perf_counter() - started) * 1000), "cancelled")
            raise
        except Exception as e:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._record_step({}, duration_ms, "error", str(e))
            raise

    async def astream(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        self._run_budget_check(messages)
        started = time.perf_counter()
        last_chunk = None
        try:
            queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=1)
            stopped = asyncio.Event()

            async def produce() -> None:
                stream = self._llm.astream(messages, **kwargs).__aiter__()
                try:
                    while not stopped.is_set():
                        try:
                            chunk = await stream.__anext__()
                        except StopAsyncIteration:
                            break
                        if stopped.is_set():
                            break
                        await queue.put(chunk)
                finally:
                    close = getattr(stream, "aclose", None)
                    if close is not None:
                        # Cleanup retains the same permit. Repeated shutdown
                        # cancellation cannot detach a still-running close.
                        closing = asyncio.ensure_future(close())
                        while not closing.done():
                            try:
                                await asyncio.shield(closing)
                            except asyncio.CancelledError:
                                continue
                        closing.result()

            task = await self._get_runtime().start(
                produce, capacity_timeout=self._settings.llm_call_timeout
            )
            try:
                while True:
                    try:
                        chunk = await _next_stream_chunk(
                            queue, task, self._settings.llm_stream_idle_timeout
                        )
                    except StopAsyncIteration:
                        break
                    except MODEL_TIMEOUTS as exc:
                        raise DomainError(
                            "模型输出等待超时，请重试",
                            code="LLM_STREAM_IDLE_TIMEOUT",
                            status_code=504,
                            retryable=True,
                        ) from exc
                    last_chunk = chunk
                    yield chunk
            finally:
                stopped.set()
                if not task.done():
                    task.cancel()
                    await asyncio.sleep(0)
            duration_ms = int((time.perf_counter() - started) * 1000)
            usage = getattr(last_chunk, "usage_metadata", None) if last_chunk else None
            if not usage:
                logger.debug(
                    "stream response missing usage_metadata for step=%s model=%s",
                    self._step,
                    self._model_name,
                )
            self._record_step(usage, duration_ms, "ok")
        except BudgetExceededError:
            raise
        except asyncio.CancelledError:
            self._record_step({}, int((time.perf_counter() - started) * 1000), "cancelled")
            raise
        except Exception as e:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._record_step({}, duration_ms, "error", str(e))
            raise
