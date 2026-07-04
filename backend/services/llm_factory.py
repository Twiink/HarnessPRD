"""LLM 实例工厂 — 根据配置返回 Anthropic 或 OpenAI 模型，并提供观测包装层"""

import logging
import time
from typing import Any, AsyncIterator

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from core.config import settings
from core.request_context import get_request_id
from services.llm_metrics import (
    RunMetricsCollector,
    build_step_metrics,
    log_llm_step,
)
from services.model_registry import resolve_max_output
from services.token_estimator import (
    BudgetExceededError,
    check_budget,
    estimate_tokens,
    log_token_budget_warn,
)

logger = logging.getLogger(__name__)


def get_llm(temperature: float = 0.7) -> ChatAnthropic | ChatOpenAI:
    """根据环境配置创建 LLM 实例"""
    model = settings.default_llm_model or "gpt-4o"
    max_tokens = resolve_max_output(model)
    if settings.default_llm_provider == "anthropic":
        kwargs = dict(
            anthropic_api_key=settings.anthropic_credential,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if settings.anthropic_base_url:
            kwargs["base_url"] = settings.anthropic_base_url
        if settings.anthropic_auth_token:
            kwargs["default_headers"] = {
                "Authorization": f"Bearer {settings.anthropic_auth_token}",
            }
        return ChatAnthropic(**kwargs)
    kwargs = dict(
        openai_api_key=settings.openai_api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**kwargs)


class TrackedChatModel:
    """包装 LLM，记录 step 耗时与 token 用量"""

    def __init__(self, llm: ChatAnthropic | ChatOpenAI, step: str):
        self._llm = llm
        self._step = step
        self._model_name = settings.default_llm_model or "unknown"

    def _run_budget_check(self, messages: list[BaseMessage]) -> None:
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
        record = build_step_metrics(
            self._step,
            self._model_name,
            usage,
            duration_ms,
            status,
            error,
        )
        run = RunMetricsCollector.current()
        if run is not None:
            run.add_step(record)
        log_llm_step({**record.to_dict(), "request_id": get_request_id()})

    async def ainvoke(self, messages: list[BaseMessage], **kwargs: Any) -> Any:
        self._run_budget_check(messages)
        started = time.perf_counter()
        try:
            response = await self._llm.ainvoke(messages, **kwargs)
            duration_ms = int((time.perf_counter() - started) * 1000)
            usage = getattr(response, "usage_metadata", None)
            self._record_step(usage, duration_ms, "ok")
            return response
        except BudgetExceededError:
            raise
        except Exception as e:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._record_step({}, duration_ms, "error", str(e)[:200])
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
            async for chunk in self._llm.astream(messages, **kwargs):
                last_chunk = chunk
                yield chunk
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
        except Exception as e:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._record_step({}, duration_ms, "error", str(e)[:200])
            raise


def get_tracked_llm(step: str, temperature: float = 0.7) -> TrackedChatModel:
    """返回带观测的 LLM 包装实例"""
    return TrackedChatModel(get_llm(temperature=temperature), step=step)
