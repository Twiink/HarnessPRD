"""交付守卫 — Job 创建前业务规则校验"""

from __future__ import annotations

from typing import Any, Dict

from apps.core.errors import DomainError
from apps.domain.documents.content_identity import valid_baseline
from apps.services.documents.versions import get_current_version


def _summary_from_session(session_data: Dict[str, Any]) -> Dict[str, Any] | None:
    summary = session_data.get("requirementsSummary")
    if summary and isinstance(summary, dict):
        return summary
    return None


def assert_can_create_job(
    session_data: Dict[str, Any],
    artifact: str,
    payload: Dict[str, Any] | None = None,
    *,
    session_id: str | None = None,
) -> None:
    payload = payload or {}

    if artifact == "prd":
        summary = payload.get("requirements_summary") or _summary_from_session(session_data)
        if not summary:
            raise DomainError("缺少结构化需求摘要", code="REQUIREMENTS_REQUIRED")
        return

    if artifact in ("api-docs", "prompts"):
        prd = (session_data.get("prdContent") or "").strip()
        if not prd:
            raise DomainError("PRD 内容为空", code="PRD_REQUIRED")
        current = (
            get_current_version(session_id, "prd")
            if session_id
            else {
                "id": session_data.get("prdBaselineVersionId"),
                "version_no": session_data.get("prdBaselineVersionNo"),
                "content": session_data.get("prdContent"),
            }
        )
        if not current or not current["id"] or not valid_baseline(session_data, current):
            raise DomainError("请先确认需求基线", code="BASELINE_REQUIRED")
        return

    if artifact.startswith("optimize-"):
        return
