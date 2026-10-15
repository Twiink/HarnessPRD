"""会话展示状态与标题派生，不写入文档或会话。"""

import re
from typing import Any, Dict, Optional
from apps.core.errors import DomainError
from apps.domain.jobs import ACTIVE_STATUSES
from apps.domain.requirements.normalization import normalize_session_requirements

STAGE_LABELS: Dict[str, str] = {
    "form": "结构化需求",
    "chatting": "澄清对话",
    "generating-prd": "PRD",
    "review-prd": "PRD",
    "generating-api-docs": "接口文档",
    "review-api-docs": "接口文档",
    "generating-prompts": "提示词",
    "review-prompts": "提示词",
}


ENTRY_MODE_FORM_STAGE: Dict[str, str] = {
    "structured": "结构化需求",
    "prd": "PRD",
    "prompts": "提示词",
}


GENERATING_VIEW_BY_ARTIFACT: Dict[str, str] = {
    "prd": "generating-prd",
    "api-docs": "generating-api-docs",
    "prompts": "generating-prompts",
}


REVIEW_VIEW_BY_ARTIFACT: Dict[str, str] = {
    "prd": "review-prd",
    "api-docs": "review-api-docs",
    "prompts": "review-prompts",
}


OPTIMIZE_TO_CONTENT_ARTIFACT: Dict[str, str] = {
    "optimize-prd": "prd",
    "optimize-api-docs": "api-docs",
    "optimize-prompts": "prompts",
}


def _is_optimize_artifact(artifact: str) -> bool:
    return artifact.startswith("optimize-")


def _content_artifact_from_job_artifact(artifact: str) -> str:
    if _is_optimize_artifact(artifact):
        return OPTIMIZE_TO_CONTENT_ARTIFACT.get(artifact, artifact.replace("optimize-", ""))
    return artifact


def _apply_draft_to_session_data(session_data: Dict[str, Any], artifact: str, draft: str) -> None:
    content_artifact = _content_artifact_from_job_artifact(artifact)
    if content_artifact == "prd":
        session_data["prdContent"] = draft
    elif content_artifact == "api-docs":
        session_data["apiDocsContent"] = draft
    elif content_artifact == "prompts":
        session_data["promptsContent"] = draft


def _has_clarification_content(session_data: Dict[str, Any]) -> bool:
    """与前端 displayMessages 一致：至少有一条可展示的澄清内容（非 system、跳过首条 seed）。"""
    messages = session_data.get("messages") or []
    if not isinstance(messages, list):
        return False
    visible = [m for m in messages if isinstance(m, dict) and m.get("role") != "system"]
    if len(visible) <= 1:
        return False
    for msg in visible[1:]:
        content = (msg.get("content") or "").strip()
        if content:
            return True
    return False


def _fallback_before_prd(session_data: Dict[str, Any]) -> str:
    if (session_data.get("prdContent") or "").strip():
        return "review-prd"
    if _has_clarification_content(session_data):
        return "chatting"
    return "form"


def normalize_session_view_state(
    session_data: Dict[str, Any],
    include_job_draft: bool = True,
    *,
    session_id: str | None = None,
) -> Dict[str, Any]:
    data = downgrade_generating_view_state(
        normalize_session_requirements(session_data), include_job_draft, session_id=session_id
    )
    view_state = data.get("viewState")
    if view_state == "chatting" and not _has_clarification_content(data):
        data["viewState"] = "form"
    return data


def downgrade_generating_view_state(
    session_data: Dict[str, Any],
    include_job_draft: bool = True,
    *,
    session_id: str | None = None,
) -> Dict[str, Any]:
    active_job_id = session_data.get("activeJobId")
    if active_job_id and session_id:
        try:
            from apps.services.generation.jobs import get_job

            job = get_job(active_job_id)
            if job["session_id"] == session_id and job["status"] in ACTIVE_STATUSES:
                session_data = dict(session_data)
                artifact = job["artifact"]
                if _is_optimize_artifact(artifact):
                    content_artifact = _content_artifact_from_job_artifact(artifact)
                    session_data["viewState"] = REVIEW_VIEW_BY_ARTIFACT.get(
                        content_artifact, session_data.get("viewState", "review-prd")
                    )
                else:
                    session_data["viewState"] = GENERATING_VIEW_BY_ARTIFACT.get(
                        artifact, session_data.get("viewState", "form")
                    )
                draft = (job.get("draft_content") or "").strip()
                if draft and include_job_draft:
                    _apply_draft_to_session_data(session_data, artifact, draft)
                if job.get("review") and include_job_draft:
                    session_data["prdReviewResult"] = job["review"]
                return session_data
        except KeyError:
            pass
        except DomainError as error:
            if error.code != "JOB_NOT_FOUND":
                raise

    view_state = session_data.get("viewState")
    if not view_state or not str(view_state).startswith("generating-"):
        return session_data

    prd_content = session_data.get("prdContent") or ""
    api_docs = session_data.get("apiDocsContent") or ""
    prompts = session_data.get("promptsContent") or ""

    fallback = {
        "generating-prd": "review-prd",
        "generating-api-docs": (
            "review-api-docs"
            if api_docs.strip()
            else "review-prd"
            if prd_content.strip()
            else "review-prd"
        ),
        "generating-prompts": (
            "review-prompts"
            if prompts.strip()
            else "review-api-docs"
            if api_docs.strip()
            else "review-prd"
            if prd_content.strip()
            else "review-prd"
        ),
    }
    session_data = dict(session_data)
    session_data["viewState"] = fallback.get(view_state, "review-prd")
    return session_data


def _extract_title_from_prd(text: str) -> Optional[str]:
    if not text or not text.strip():
        return None
    heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if heading:
        return heading.group(1).strip()
    name_match = re.search(r"产品名称[：:]\s*(.+)", text)
    if name_match:
        return name_match.group(1).strip().split("\n")[0].strip()
    return None


def extract_title(session_data: Dict[str, Any], record_id: str) -> str:
    summary = session_data.get("requirementsSummary") or {}
    form_data = session_data.get("formData") or {}

    structured_name = (summary.get("product_name") or form_data.get("product_name") or "").strip()
    if structured_name:
        return structured_name

    prd_text = (session_data.get("prdContent") or session_data.get("manualPrdInput") or "").strip()
    prd_title = _extract_title_from_prd(prd_text)
    if prd_title:
        return prd_title

    return record_id


def derive_current_stage(session_data: Dict[str, Any]) -> str:
    view_state = session_data.get("viewState") or "form"
    entry_mode = session_data.get("entryMode") or "structured"
    if view_state == "form":
        return ENTRY_MODE_FORM_STAGE.get(entry_mode, "结构化需求")
    return STAGE_LABELS.get(view_state, view_state)


def derive_status(session_data: Dict[str, Any]) -> str:
    view_state = session_data.get("viewState") or "form"
    if str(view_state).startswith("generating-"):
        return "生成中"
    if view_state == "review-prompts":
        return "已完成"
    return "进行中"
