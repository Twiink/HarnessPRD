"""LLM 观测指标 — StepMetrics、RunMetrics、RunMetricsCollector"""

import json
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from apps.core.config import settings
from apps.core.logging import redact
from apps.core.request_context import get_request_id, get_session_id

logger = logging.getLogger(__name__)

_current_run: ContextVar[Optional["RunMetrics"]] = ContextVar("current_run", default=None)


class LlmStep(str, Enum):
    CHAT_START = "chat_start"
    CHAT_CONTINUE = "chat_continue"
    SUMMARY_SYNC = "summary_sync"
    JSON_REPAIR = "json_repair"
    JSON_REGENERATE = "json_regenerate"
    PRD_WRITER = "prd_writer"
    PRD_REVIEW = "prd_review"
    PRD_REWRITE = "prd_rewrite"
    API_DOCS_GENERATE = "api_docs_generate"
    API_DOCS_REVIEW = "api_docs_review"
    PROMPTS_GENERATE = "prompts_generate"
    PROMPTS_REVIEW = "prompts_review"
    DOCUMENT_OPTIMIZE = "document_optimize"


@dataclass
class StepMetrics:
    step: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    status: str
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "duration_ms": self.duration_ms,
        }


@dataclass
class RunMetrics:
    run_type: str
    request_id: str
    started_at: float = field(default_factory=time.perf_counter)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    llm_call_count: int = 0
    steps: List[StepMetrics] = field(default_factory=list)
    revision_applied: Optional[bool] = None
    budget: Optional[Dict[str, Any]] = None
    injected_skills: Optional[List[Dict[str, Any]]] = None

    def add_step(self, step: StepMetrics) -> None:
        self.steps.append(step)
        self.llm_call_count += 1
        self.total_input_tokens += step.input_tokens
        self.total_output_tokens += step.output_tokens

    def set_budget(self, check: Any) -> None:
        usage = (
            check.to_budget_summary()
            if hasattr(check, "to_budget_summary")
            else check.to_context_usage()
        )
        if self.budget is None or usage["ratio"] >= self.budget.get("ratio", 0):
            self.budget = usage

    @property
    def total_duration_ms(self) -> int:
        return int((time.perf_counter() - self.started_at) * 1000)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "request_id": self.request_id,
            "run_type": self.run_type,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_duration_ms": self.total_duration_ms,
            "llm_call_count": self.llm_call_count,
            "steps": [s.to_summary_dict() for s in self.steps],
        }
        if self.revision_applied is not None:
            result["revision_applied"] = self.revision_applied
        if self.budget is not None:
            result["budget"] = self.budget
        if self.injected_skills:
            result["injected_skills"] = self.injected_skills
        return result


class RunMetricsCollector:
    def __init__(self, run: RunMetrics):
        self._run = run

    @classmethod
    def start(cls, run_type: str) -> "RunMetricsCollector":
        run = RunMetrics(run_type=run_type, request_id=get_request_id() or "")
        _current_run.set(run)
        return cls(run)

    @staticmethod
    def current() -> Optional[RunMetrics]:
        return _current_run.get()

    def set_budget(self, check: Any) -> None:
        self._run.set_budget(check)

    def set_injected_skills(self, skills: List[Dict[str, Any]]) -> None:
        self._run.injected_skills = skills

    def finish(self, revision_applied: Optional[bool] = None) -> RunMetrics:
        if revision_applied is not None:
            self._run.revision_applied = revision_applied
        elif any(s.step == LlmStep.PRD_REWRITE.value for s in self._run.steps):
            self._run.revision_applied = True
        elif self._run.steps:
            self._run.revision_applied = False
        _current_run.set(None)
        return self._run


def _normalize_usage(usage: Any) -> Dict[str, int]:
    if not usage:
        return {}
    if isinstance(usage, dict):
        data = usage
    else:
        data = dict(usage)
    return {
        "input_tokens": int(data.get("input_tokens") or 0),
        "output_tokens": int(data.get("output_tokens") or 0),
    }


def build_step_metrics(
    step: str,
    model: str,
    usage: Any,
    duration_ms: int,
    status: str,
    error: str = "",
) -> StepMetrics:
    normalized = _normalize_usage(usage)
    return StepMetrics(
        step=step,
        model=model,
        input_tokens=normalized.get("input_tokens", 0),
        output_tokens=normalized.get("output_tokens", 0),
        duration_ms=duration_ms,
        status=status,
        error=redact(error),
    )


def log_llm_step(record: Dict[str, Any]) -> None:
    if not settings.log_llm_metrics:
        return
    payload = {
        "event": "llm_step",
        "request_id": record.get("request_id") or get_request_id(),
        "session_id": get_session_id(),
        **{k: v for k, v in record.items() if k not in ("request_id", "event")},
    }
    logger.info(json.dumps(payload, ensure_ascii=False))


def log_run_summary(summary: RunMetrics) -> None:
    payload = {
        "event": "run_summary",
        "request_id": summary.request_id,
        "session_id": get_session_id(),
        **{k: v for k, v in summary.to_dict().items() if k != "request_id"},
    }
    logger.info(json.dumps(payload, ensure_ascii=False))
