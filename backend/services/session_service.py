"""方案（Session）业务逻辑"""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.database import get_connection
from services.document_version_service import (
    migrate_session_documents_if_needed,
    refresh_session_content_from_documents,
    sync_session_content_to_documents,
    backfill_prd_review_metadata,
    DOC_TYPE_TO_SESSION_FIELD,
)

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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def normalize_session_view_state(session_data: Dict[str, Any]) -> Dict[str, Any]:
    data = downgrade_generating_view_state(dict(session_data))
    view_state = data.get("viewState")
    if view_state == "chatting" and not _has_clarification_content(data):
        data["viewState"] = "form"
    return data


def downgrade_generating_view_state(session_data: Dict[str, Any]) -> Dict[str, Any]:
    active_job_id = session_data.get("activeJobId")
    if active_job_id:
        try:
            from services.job_service import get_job

            job = get_job(active_job_id)
            if job["status"] == "running":
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
                if draft:
                    _apply_draft_to_session_data(session_data, artifact, draft)
                if job.get("review"):
                    session_data["prdReviewResult"] = job["review"]
                return session_data
        except KeyError:
            pass

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
            else "review-prd" if prd_content.strip()
            else "review-prd"
        ),
        "generating-prompts": (
            "review-prompts"
            if prompts.strip()
            else "review-api-docs" if api_docs.strip()
            else "review-prd" if prd_content.strip()
            else "review-prd"
        ),
    }
    session_data = dict(session_data)
    session_data["viewState"] = fallback.get(view_state, "review-prd")
    return session_data


def load_session_data_raw(session_id: str) -> Dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT session_data FROM project_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    if not row:
        raise KeyError(session_id)
    return json.loads(row["session_data"])


def sync_session_active_job(session_id: str, job_id: str, artifact: str) -> None:
    data = load_session_data_raw(session_id)
    data["activeJobId"] = job_id
    data["viewState"] = GENERATING_VIEW_BY_ARTIFACT.get(artifact, data.get("viewState", "form"))
    save_session(data, session_id)


def sync_session_active_optimize_job(session_id: str, job_id: str) -> None:
    data = load_session_data_raw(session_id)
    data["activeJobId"] = job_id
    save_session(data, session_id)


def _clear_prd_baseline(session_data: Dict[str, Any]) -> None:
    session_data["prdBaselineConfirmed"] = False
    session_data["prdBaselineConfirmedAt"] = None
    session_data["prdBaselineVersionId"] = None
    session_data["prdBaselineVersionNo"] = None
    session_data["prdBaselineContentHash"] = None


def sync_session_on_optimize_complete(
    session_id: str,
    artifact: str,
    draft_content: str,
) -> None:
    content_artifact = _content_artifact_from_job_artifact(artifact)
    data = load_session_data_raw(session_id)
    data["activeJobId"] = None
    data["viewState"] = REVIEW_VIEW_BY_ARTIFACT.get(content_artifact, "review-prd")
    _apply_draft_to_session_data(data, artifact, draft_content)
    if artifact == "optimize-prd":
        _clear_prd_baseline(data)
    save_session(data, session_id)


def sync_session_on_optimize_failed(
    session_id: str,
    artifact: str,
    draft_content: str,
) -> None:
    content_artifact = _content_artifact_from_job_artifact(artifact)
    data = load_session_data_raw(session_id)
    data["activeJobId"] = None
    data["viewState"] = REVIEW_VIEW_BY_ARTIFACT.get(content_artifact, "review-prd")
    if draft_content.strip():
        _apply_draft_to_session_data(data, artifact, draft_content)
    save_session(data, session_id)


def sync_session_on_job_complete(
    session_id: str,
    artifact: str,
    draft_content: str,
    review: Optional[Dict[str, Any]] = None,
) -> None:
    data = load_session_data_raw(session_id)
    data["activeJobId"] = None
    data["viewState"] = REVIEW_VIEW_BY_ARTIFACT.get(artifact, "review-prd")
    if artifact == "prd":
        data["prdContent"] = draft_content
        if review is not None:
            data["prdReviewResult"] = review
        _clear_prd_baseline(data)
    elif artifact == "api-docs":
        data["apiDocsContent"] = draft_content
    elif artifact == "prompts":
        data["promptsContent"] = draft_content
    save_session(data, session_id)


def sync_session_mirror_for_doc_type(session_id: str, doc_type: str, content: str) -> None:
    field = DOC_TYPE_TO_SESSION_FIELD.get(doc_type)
    if not field:
        return
    data = load_session_data_raw(session_id)
    if data.get(field) == content:
        return
    data[field] = content
    save_session(data, session_id)


def sync_session_on_job_failed(session_id: str, artifact: str, draft_content: str) -> None:
    data = load_session_data_raw(session_id)
    data["activeJobId"] = None
    data["viewState"] = REVIEW_VIEW_BY_ARTIFACT.get(artifact, "review-prd")
    if draft_content.strip():
        if artifact == "prd":
            data["prdContent"] = draft_content
        elif artifact == "api-docs":
            data["apiDocsContent"] = draft_content
        elif artifact == "prompts":
            data["promptsContent"] = draft_content
    save_session(data, session_id)


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


def list_sessions() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, entry_mode, current_stage, status, created_at, updated_at
            FROM project_sessions
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_session(session_id: str) -> Dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM project_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    if not row:
        raise KeyError(session_id)

    session_data = json.loads(row["session_data"])
    session_data = normalize_session_view_state(session_data)
    migrate_session_documents_if_needed(session_id, session_data)
    backfill_prd_review_metadata(session_id, session_data)
    if refresh_session_content_from_documents(session_id, session_data):
        data_json = json.dumps(session_data, ensure_ascii=False)
        with get_connection() as conn:
            conn.execute(
                "UPDATE project_sessions SET session_data = ?, updated_at = ? WHERE id = ?",
                (data_json, _now_iso(), session_id),
            )
            conn.commit()

    return {
        "id": row["id"],
        "title": row["title"],
        "entry_mode": row["entry_mode"],
        "current_stage": row["current_stage"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "session_data": session_data,
    }


def save_session(session_data: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, str]:
    normalized = normalize_session_view_state(dict(session_data))
    entry_mode = normalized.get("entryMode") or "structured"
    current_stage = derive_current_stage(normalized)
    status = derive_status(normalized)
    now = _now_iso()
    data_json = json.dumps(normalized, ensure_ascii=False)

    if session_id:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, title FROM project_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row:
                raise KeyError(session_id)
            conn.execute(
                """
                UPDATE project_sessions
                SET entry_mode = ?, current_stage = ?, status = ?, session_data = ?, updated_at = ?
                WHERE id = ?
                """,
                (entry_mode, current_stage, status, data_json, now, session_id),
            )
            conn.commit()
        migrate_session_documents_if_needed(session_id, normalized)
        backfill_prd_review_metadata(session_id, normalized)
        if not normalized.get("activeJobId"):
            sync_session_content_to_documents(session_id, normalized)
        return {"id": session_id, "title": row["title"]}

    new_id = str(uuid.uuid4())
    title = extract_title(normalized, new_id)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO project_sessions
            (id, title, entry_mode, current_stage, status, session_data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id, title, entry_mode, current_stage, status, data_json, now, now),
        )
        conn.commit()
    migrate_session_documents_if_needed(new_id, normalized)
    backfill_prd_review_metadata(new_id, normalized)
    if not normalized.get("activeJobId"):
        sync_session_content_to_documents(new_id, normalized)
    return {"id": new_id, "title": title}


def delete_session(session_id: str) -> None:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM project_sessions WHERE id = ?", (session_id,)
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(session_id)
