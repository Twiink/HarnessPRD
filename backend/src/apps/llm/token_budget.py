"""Token 估算与应用层预算检查"""

import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, List, Optional

from langchain_core.messages import BaseMessage

from apps.core.config import settings
from apps.core.request_context import get_request_id, get_session_id
from apps.llm.metrics import LlmStep
from apps.llm.registry import hardware_input_cap, resolve, resolve_max_output

logger = logging.getLogger(__name__)

_last_budget_check: ContextVar[Optional["BudgetCheckResult"]] = ContextVar(
    "last_budget_check", default=None
)

_CHAT_HISTORY_STEPS = {LlmStep.CHAT_START.value, LlmStep.CHAT_CONTINUE.value}
_SINGLE_CALL_STEPS = {
    LlmStep.PRD_WRITER.value,
    LlmStep.PRD_REVIEW.value,
    LlmStep.PRD_REWRITE.value,
    LlmStep.API_DOCS_GENERATE.value,
    LlmStep.PROMPTS_GENERATE.value,
    LlmStep.DOCUMENT_OPTIMIZE.value,
}
_CONTEXT_BUDGET_STEPS = {
    LlmStep.SUMMARY_SYNC.value,
    LlmStep.JSON_REPAIR.value,
    LlmStep.JSON_REGENERATE.value,
}


@dataclass
class TokenEstimate:
    estimated_input_tokens: int
    budget_tokens: int
    max_output_tokens: int
    ratio: float
    estimator: str


@dataclass
class EffectiveBudget:
    effective_input_budget: int
    policy_cap: int
    hardware_cap: int
    budget_source: str  # 策略上限或模型物理上限
    max_output_tokens: int


@dataclass
class BudgetCheckResult:
    allowed: bool
    mode: str
    level: str
    estimated_input_tokens: int
    budget_tokens: int
    ratio: float
    message: str
    step: str
    model: str = ""
    policy_cap: int = 0
    hardware_cap: int = 0
    budget_source: str = ""

    def to_context_usage(self) -> dict:
        return {
            "estimated_input_tokens": self.estimated_input_tokens,
            "budget_tokens": self.budget_tokens,
            "ratio": round(self.ratio, 2),
            "level": self.level,
        }

    def to_budget_summary(self) -> dict:
        summary = self.to_context_usage()
        if self.budget_source:
            summary["budget_source"] = self.budget_source
        if self.model:
            summary["model"] = self.model
        if self.policy_cap:
            summary["policy_cap"] = self.policy_cap
        if self.hardware_cap:
            summary["hardware_cap"] = self.hardware_cap
        return summary


class BudgetExceededError(Exception):
    def __init__(self, check: BudgetCheckResult):
        self.check = check
        super().__init__(check.message)


def get_last_budget_check() -> Optional[BudgetCheckResult]:
    return _last_budget_check.get()


def _get_encoding(encoding_name: Optional[str] = None):
    if settings.token_estimator != "tiktoken":
        return None
    name = encoding_name or settings.token_encoding
    try:
        import tiktoken

        return tiktoken.get_encoding(name)
    except Exception as exc:
        logger.debug("tiktoken unavailable, fallback to char_heuristic: %s", exc)
        return None


def _message_role(msg: BaseMessage) -> str:
    role = getattr(msg, "type", "user")
    if role == "human":
        return "user"
    if role == "ai":
        return "assistant"
    return role


def _estimate_with_tiktoken(messages: List[BaseMessage], encoding) -> int:
    tokens = 0
    for msg in messages:
        tokens += 4
        tokens += len(encoding.encode(_message_role(msg)))
        tokens += len(encoding.encode(str(msg.content or "")))
    tokens += 2
    return tokens


def _estimate_with_char_heuristic(messages: List[BaseMessage]) -> int:
    total_chars = sum(len(str(msg.content or "")) for msg in messages)
    return int(total_chars * 0.6)


def _budget_for_step(step: str) -> int:
    if step in _CHAT_HISTORY_STEPS:
        return settings.chat_history_budget
    if step in _SINGLE_CALL_STEPS:
        return settings.single_call_input_budget
    if step in _CONTEXT_BUDGET_STEPS:
        return settings.context_budget_tokens
    return settings.context_budget_tokens


def resolve_effective_budget(step: str, model: str) -> EffectiveBudget:
    policy_cap = _budget_for_step(step)
    hw_cap = hardware_input_cap(model) if model else policy_cap
    if policy_cap <= hw_cap:
        effective = max(policy_cap, 1)
        source = "policy"
    else:
        effective = max(hw_cap, 1)
        source = "hardware"
    max_output = resolve_max_output(model) if model else resolve_max_output("default")
    return EffectiveBudget(
        effective_input_budget=effective,
        policy_cap=policy_cap,
        hardware_cap=hw_cap,
        budget_source=source,
        max_output_tokens=max_output,
    )


def estimate_tokens(
    messages: List[BaseMessage],
    step: str = "",
    model: str = "",
) -> TokenEstimate:
    budget = resolve_effective_budget(step, model)
    caps = resolve(model) if model else resolve("default")
    encoding = _get_encoding(caps.encoding)
    if encoding is not None:
        estimated = _estimate_with_tiktoken(messages, encoding)
        estimator = "tiktoken"
    else:
        estimated = _estimate_with_char_heuristic(messages)
        estimator = "char_heuristic"

    effective_budget = budget.effective_input_budget
    ratio = estimated / effective_budget
    return TokenEstimate(
        estimated_input_tokens=estimated,
        budget_tokens=effective_budget,
        max_output_tokens=budget.max_output_tokens,
        ratio=ratio,
        estimator=estimator,
    )


def _level_message(level: str, step: str) -> str:
    if level == "ok":
        return ""
    if level == "warn":
        if step in _CHAT_HISTORY_STEPS:
            return "对话内容较多，建议准备结束澄清并生成 PRD。"
        return "当前输入内容较多，可能影响生成质量。"
    if step in _CHAT_HISTORY_STEPS:
        return "对话内容过多，请先结束澄清并生成 PRD，或新建方案后继续。"
    if step == LlmStep.SUMMARY_SYNC.value:
        return "澄清对话内容过多，无法更新结构化摘要，请先精简对话或新建方案。"
    return "输入内容超出预算上限，请精简内容后重试。"


def check_budget(
    estimate: TokenEstimate,
    step: str,
    model: str = "",
) -> BudgetCheckResult:
    mode = settings.token_budget_mode.lower()
    if estimate.ratio < 0.6:
        level = "ok"
    elif estimate.ratio <= 0.95:
        level = "warn"
    else:
        level = "exceed"

    allowed = not (level == "exceed" and mode == "reject")
    message = _level_message(level, step)
    budget = resolve_effective_budget(step, model)

    result = BudgetCheckResult(
        allowed=allowed,
        mode=mode,
        level=level,
        estimated_input_tokens=estimate.estimated_input_tokens,
        budget_tokens=estimate.budget_tokens,
        ratio=estimate.ratio,
        message=message,
        step=step,
        model=model,
        policy_cap=budget.policy_cap,
        hardware_cap=budget.hardware_cap,
        budget_source=budget.budget_source,
    )
    _last_budget_check.set(result)
    return result


def log_token_budget_warn(check: BudgetCheckResult) -> None:
    if check.level not in ("warn", "exceed") or not check.allowed:
        return
    payload = {
        "event": "token_budget_warn",
        "request_id": get_request_id(),
        "session_id": get_session_id(),
        "step": check.step,
        "model": check.model,
        "ratio": round(check.ratio, 2),
        "level": check.level,
        "estimated_input_tokens": check.estimated_input_tokens,
        "budget_tokens": check.budget_tokens,
        "budget_source": check.budget_source,
        "message": check.message,
    }
    logger.warning(json.dumps(payload, ensure_ascii=False))
