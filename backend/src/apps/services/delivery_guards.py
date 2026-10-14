"""交付守卫 — Job 创建前业务规则校验"""

from __future__ import annotations

from typing import Any, Dict

from apps.core.errors import DomainError


def _summary_from_session(session_data: Dict[str, Any]) -> Dict[str, Any] | None:
    summary = session_data.get("requirementsSummary")
    if summary and isinstance(summary, dict):
        return summary
    return None


def assert_can_create_job(
    session_data: Dict[str, Any],
    artifact: str,
    payload: Dict[str, Any] | None = None,
) -> None:
    payload = payload or {}

    if artifact == "prd":
        summary = payload.get("requirements_summary") or _summary_from_session(session_data)
        if not summary:
            raise DomainError("缺少结构化需求摘要", code="REQUIREMENTS_REQUIRED")
        return

    if artifact in ("api-docs", "prompts"):
        if not session_data.get("prdBaselineConfirmed"):
            raise DomainError("请先确认需求基线", code="BASELINE_REQUIRED")
        prd = (session_data.get("prdContent") or "").strip()
        if not prd:
            raise DomainError("PRD 内容为空", code="PRD_REQUIRED")
        return

    if artifact.startswith("optimize-"):
        return
