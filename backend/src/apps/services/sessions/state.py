"""方案（Session）业务逻辑"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from apps.core.errors import DomainError
from apps.db.connection import transaction, read_snapshot
from apps.db.repositories import sessions as repository
from apps.domain.sessions import SessionNotFoundError, SessionJobConflictError
from apps.domain.jobs import ACTIVE_STATUSES
from apps.domain.documents.content_identity import valid_baseline
from apps.services.documents.versions import (
    migrate_session_documents_if_needed,
    refresh_session_content_from_documents,
    sync_session_content_to_documents,
    backfill_prd_review_metadata,
    DOC_TYPE_TO_SESSION_FIELD,
    get_current_version,
)


from apps.services.sessions.presentation import (
    GENERATING_VIEW_BY_ARTIFACT,
    REVIEW_VIEW_BY_ARTIFACT,
    _content_artifact_from_job_artifact,
    _apply_draft_to_session_data,
    normalize_session_view_state,
    extract_title,
    derive_current_stage,
    derive_status,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_session_data_raw(session_id: str) -> Dict[str, Any]:
    row = repository.get(session_id)
    if row is None:
        raise SessionNotFoundError(session_id)
    return json.loads(row["session_data"])


def _sanitize_job_pointers(data: Dict[str, Any], session_id: str | None) -> Dict[str, Any]:
    from apps.services.generation.jobs import get_job

    clean = dict(data)
    for field in ("activeJobId", "activeOptimizeJobId"):
        if field not in clean:
            continue
        candidate = clean[field]
        clean[field] = None
        if not candidate or session_id is None:
            continue
        try:
            job = get_job(candidate)
        except DomainError as exc:
            if exc.code == "JOB_NOT_FOUND":
                continue
            raise
        if job["session_id"] != session_id or job["status"] not in ACTIVE_STATUSES:
            continue
        if field == "activeOptimizeJobId" and not job["artifact"].startswith("optimize-"):
            continue
        clean[field] = candidate
    return clean


def sync_session_active_job(session_id: str, job_id: str, artifact: str) -> None:
    with transaction():
        data = load_session_data_raw(session_id)
        data["activeJobId"] = job_id
        data["viewState"] = GENERATING_VIEW_BY_ARTIFACT.get(artifact, data.get("viewState", "form"))
        save_session(data, session_id)


def sync_session_active_optimize_job(session_id: str, job_id: str) -> None:
    with transaction():
        data = load_session_data_raw(session_id)
        data["activeJobId"] = job_id
        save_session(data, session_id)


def _clear_prd_baseline(session_data: Dict[str, Any]) -> None:
    session_data["prdBaselineConfirmed"] = False
    session_data["prdBaselineConfirmedAt"] = None
    session_data["prdBaselineVersionId"] = None
    session_data["prdBaselineVersionNo"] = None
    session_data["prdBaselineContentHash"] = None


def invalidate_prd_state_for_content(session_id: str, content: str) -> None:
    """Invalidate conclusions in the same transaction that changes durable PRD content."""
    with transaction():
        data = load_session_data_raw(session_id)
        changed = data.get("prdContent") != content
        invalid_baseline = data.get("prdBaselineConfirmed") and not valid_baseline(
            data, get_current_version(session_id, "prd")
        )
        if not changed and not invalid_baseline:
            return
        _clear_prd_baseline(data)
        if changed:
            data["prdReviewResult"] = None
        repository.update_data(session_id, json.dumps(data, ensure_ascii=False), _now_iso())


def sync_session_on_optimize_complete(
    session_id: str,
    artifact: str,
    draft_content: str,
    job_id: Optional[str] = None,
) -> None:
    with transaction():
        content_artifact = _content_artifact_from_job_artifact(artifact)
        data = load_session_data_raw(session_id)
        refresh_session_content_from_documents(session_id, data)
        if job_id is None or data.get("activeJobId") == job_id:
            data["activeJobId"] = (
                repository.active_job_id(session_id, exclude_job_id=job_id) if job_id else None
            )
        data["viewState"] = REVIEW_VIEW_BY_ARTIFACT.get(content_artifact, "review-prd")
        _apply_draft_to_session_data(data, artifact, draft_content)
        if artifact == "optimize-prd":
            _clear_prd_baseline(data)
        save_session(data, session_id)


def sync_session_on_optimize_failed(
    session_id: str,
    artifact: str,
    draft_content: str,
    job_id: Optional[str] = None,
) -> None:
    with transaction():
        content_artifact = _content_artifact_from_job_artifact(artifact)
        data = load_session_data_raw(session_id)
        refresh_session_content_from_documents(session_id, data)
        if job_id is None or data.get("activeJobId") == job_id:
            data["activeJobId"] = (
                repository.active_job_id(session_id, exclude_job_id=job_id) if job_id else None
            )
        data["viewState"] = REVIEW_VIEW_BY_ARTIFACT.get(content_artifact, "review-prd")
        _apply_failed_draft(data, session_id, artifact, draft_content)
        save_session(data, session_id)


def sync_session_on_job_complete(
    session_id: str,
    artifact: str,
    draft_content: str,
    review: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
) -> None:
    with transaction():
        data = load_session_data_raw(session_id)
        refresh_session_content_from_documents(session_id, data)
        if job_id is None or data.get("activeJobId") == job_id:
            data["activeJobId"] = (
                repository.active_job_id(session_id, exclude_job_id=job_id) if job_id else None
            )
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
    with transaction():
        data = load_session_data_raw(session_id)
        if data.get(field) == content:
            return
        if doc_type == "prd":
            _clear_prd_baseline(data)
            data["prdReviewResult"] = None
        data[field] = content
        # Mirror only the selected document; do not auto-save unrelated document drafts.
        repository.update_data(session_id, json.dumps(data, ensure_ascii=False), _now_iso())


def sync_session_on_job_failed(
    session_id: str,
    artifact: str,
    draft_content: str,
    job_id: Optional[str] = None,
) -> None:
    with transaction():
        data = load_session_data_raw(session_id)
        refresh_session_content_from_documents(session_id, data)
        if job_id is None or data.get("activeJobId") == job_id:
            data["activeJobId"] = (
                repository.active_job_id(session_id, exclude_job_id=job_id) if job_id else None
            )
        data["viewState"] = REVIEW_VIEW_BY_ARTIFACT.get(artifact, "review-prd")
        _apply_failed_draft(data, session_id, artifact, draft_content)
        save_session(data, session_id)


def _apply_failed_draft(
    data: Dict[str, Any], session_id: str, artifact: str, draft_content: str
) -> None:
    doc_type = _content_artifact_from_job_artifact(artifact)
    if doc_type not in DOC_TYPE_TO_SESSION_FIELD:
        return
    current = get_current_version(session_id, doc_type)
    if current and current["metadata"].get("job_status") != "failed":
        # A failed stream may be visible in Session, but it must not replace durable success.
        _apply_draft_to_session_data(data, artifact, current["content"])
    else:
        # 未完成正文只保留在任务记录，终态清理不把临时镜像提升为正式文档。
        _apply_draft_to_session_data(data, artifact, "")


def list_sessions() -> List[Dict[str, Any]]:
    return repository.list_all()


def get_session(session_id: str) -> Dict[str, Any]:
    with read_snapshot():
        row = repository.get(session_id)
        if row is None:
            raise SessionNotFoundError(session_id)
        session_data = _sanitize_job_pointers(json.loads(row["session_data"]), session_id)
        has_active_job = repository.active_job_id(session_id) is not None
        needs_migration = not has_active_job and any(
            (session_data.get(field) or "").strip()
            and get_current_version(session_id, doc_type) is None
            for doc_type, field in DOC_TYPE_TO_SESSION_FIELD.items()
        )
        needs_refresh = refresh_session_content_from_documents(session_id, session_data)
        if not needs_migration and not needs_refresh:
            row["session_data"] = normalize_session_view_state(session_data, session_id=session_id)
            return row
    with transaction():
        row = repository.get(session_id)
        if row is None:
            raise SessionNotFoundError(session_id)
        session_data = _sanitize_job_pointers(json.loads(row["session_data"]), session_id)
        # 持久化文档只来自已保存正文，运行中草稿仅叠加到本次响应。
        if repository.active_job_id(session_id) is None:
            migrate_session_documents_if_needed(session_id, session_data)
            backfill_prd_review_metadata(session_id, session_data)
        if refresh_session_content_from_documents(session_id, session_data):
            row["updated_at"] = _now_iso()
            repository.update_data(
                session_id, json.dumps(session_data, ensure_ascii=False), row["updated_at"]
            )
        row["session_data"] = normalize_session_view_state(session_data, session_id=session_id)
        return row


def save_session(session_data: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, str]:
    with transaction():
        row = repository.get(session_id) if session_id else None
        if session_id and row is None:
            raise SessionNotFoundError(session_id)
        previous = json.loads(row["session_data"]) if row else {}
        for doc_type, field in DOC_TYPE_TO_SESSION_FIELD.items():
            current = get_current_version(session_id, doc_type) if session_id else None
            if field not in session_data:
                if current:
                    previous[field] = current["content"]
                continue
            if (session_data[field] is None or not session_data[field].strip()) and (
                (current and current["content"].strip()) or (previous.get(field) or "").strip()
            ):
                raise DomainError(
                    "已有文档正文不可清空", code="DOCUMENT_CONTENT_REQUIRED", status_code=422
                )
        normalized = normalize_session_view_state(
            _sanitize_job_pointers({**previous, **session_data}, session_id),
            include_job_draft=False,
            session_id=session_id,
        )
        if row and previous.get("prdContent") != normalized.get("prdContent"):
            _clear_prd_baseline(normalized)
            normalized["prdReviewResult"] = None
        entry_mode = normalized.get("entryMode") or "structured"
        current_stage = derive_current_stage(normalized)
        status = derive_status(normalized)
        now = _now_iso()
        data_json = json.dumps(normalized, ensure_ascii=False)
        if session_id:
            assert row is not None
            title = row["title"]
            repository.update(session_id, entry_mode, current_stage, status, data_json, now)
        else:
            session_id = str(uuid.uuid4())
            title = extract_title(normalized, session_id)
            repository.insert(
                {
                    "id": session_id,
                    "title": title,
                    "entry_mode": entry_mode,
                    "current_stage": current_stage,
                    "status": status,
                    "session_data": data_json,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        if repository.active_job_id(session_id) is None:
            migrate_session_documents_if_needed(session_id, normalized)
            backfill_prd_review_metadata(session_id, normalized)
            sync_session_content_to_documents(session_id, normalized)
        current_prd = get_current_version(session_id, "prd")
        if current_prd and current_prd["content"] == normalized.get("prdContent"):
            normalized["prdReviewResult"] = current_prd["metadata"].get("review")
        if normalized.get("prdBaselineConfirmed") and not valid_baseline(normalized, current_prd):
            _clear_prd_baseline(normalized)
        repository.update_data(session_id, json.dumps(normalized, ensure_ascii=False), now)
        return {"id": session_id, "title": title}


def delete_session(session_id: str) -> None:
    with transaction():
        if repository.get(session_id) is None:
            raise SessionNotFoundError(session_id)
        job_id = repository.active_job_id(session_id)
        if job_id:
            raise SessionJobConflictError(job_id)
        repository.delete_tree(session_id)
