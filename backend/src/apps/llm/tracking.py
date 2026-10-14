"""聊天模型的观测包装和输入预算检查。"""

import logging
import time
from typing import Any, AsyncIterator

from langchain_core.messages import BaseMessage

from apps.core.config import get_settings, settings_context
from apps.core.logging import redact
from apps.core.request_context import get_request_id
from apps.llm.metrics import RunMetricsCollector, build_step_metrics, log_llm_step
from apps.llm.token_budget import (
    BudgetExceededError,
    check_budget,
    estimate_tokens,
    log_token_budget_warn,
)

logger = logging.getLogger(__name__)


class TrackedChatModel:
    """包装 LLM，记录 step 耗时与 token 用量"""

    def __init__(self, llm: Any, step: str):
        self._llm = llm
        self._step = step
        self._settings = get_settings()
        self._model_name = self._settings.default_llm_model or "unknown"

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
            response = await self._llm.ainvoke(messages, **kwargs)
            duration_ms = int((time.perf_counter() - started) * 1000)
            usage = getattr(response, "usage_metadata", None)
            self._record_step(usage, duration_ms, "ok")
            return response
        except BudgetExceededError:
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
            self._record_step({}, duration_ms, "error", str(e))
            raise
