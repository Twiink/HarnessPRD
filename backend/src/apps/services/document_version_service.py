"""Document version use cases; SQL is owned by document/session repositories."""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from apps.db.connection import transaction
from apps.db.repositories import documents as repository
from apps.db.repositories import sessions as session_repository
from apps.domain.documents import (
    VALID_DOC_TYPES,
    VersionSourceKind,
    DocumentVersionError,
    SessionNotFoundError,
    InvalidDocTypeError,
    VersionNotFoundError,
    CheckpointError,
    RestoreError,
)

CONTENT_PREVIEW_LEN = 200
ARTIFACT_TO_DOC_TYPE = {
    "prd": "prd",
    "optimize-prd": "prd",
    "api-docs": "api-docs",
    "optimize-api-docs": "api-docs",
    "prompts": "prompts",
    "optimize-prompts": "prompts",
}
DOC_TYPE_TO_SESSION_FIELD = {
    "prd": "prdContent",
    "api-docs": "apiDocsContent",
    "prompts": "promptsContent",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_doc_type(doc_type: str) -> str:
    if doc_type not in VALID_DOC_TYPES:
        raise InvalidDocTypeError(doc_type)
    return doc_type


def _require_session(session_id: str) -> dict:
    session = session_repository.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    return session


def _build_preview(content: str) -> str:
    text = re.sub(r"\s+", " ", content or "").strip()
    return text if len(text) <= CONTENT_PREVIEW_LEN else text[:CONTENT_PREVIEW_LEN] + "..."


def _version_list_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    note = (meta.get("change_note") or "").strip()
    if note:
        out["change_note"] = note
    if meta.get("restored_from_version_no") is not None:
        out["restored_from_version_no"] = int(meta["restored_from_version_no"])
    return out


def _parse_metadata(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def merge_metadata(old: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(old or {})
    merged.update({key: value for key, value in (new or {}).items() if value is not None})
    return merged


def _row_to_version(row: dict, current_version_id: Optional[str]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "version_no": row["version_no"],
        "content": row["content"] or "",
        "source_kind": row["source_kind"],
        "source_job_id": row["source_job_id"],
        "parent_version_id": row["parent_version_id"],
        "metadata": _parse_metadata(row["metadata_json"]),
        "created_at": row["created_at"],
        "is_current": row["id"] == current_version_id,
        "content_preview": _build_preview(row["content"] or ""),
    }


def ensure_document(session_id: str, doc_type: str, conn=None) -> Dict[str, Any]:
    doc_type = _validate_doc_type(doc_type)
    with transaction():
        _require_session(session_id)
        doc = repository.get_document(session_id, doc_type)
        if doc is None:
            now = _now_iso()
            doc = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "doc_type": doc_type,
                "current_version_id": None,
                "created_at": now,
                "updated_at": now,
            }
            repository.insert_document(doc)
        return doc


def get_document(session_id: str, doc_type: str) -> Optional[Dict[str, Any]]:
    return repository.get_document(session_id, _validate_doc_type(doc_type))


def get_current_version(session_id: str, doc_type: str) -> Optional[Dict[str, Any]]:
    with transaction():
        doc = get_document(session_id, doc_type)
        if not doc or not doc["current_version_id"]:
            return None
        row = repository.get_version(doc["id"], doc["current_version_id"])
        return _row_to_version(row, doc["current_version_id"]) if row else None


def get_documents_by_session(session_id: str) -> List[Dict[str, Any]]:
    with transaction():
        _require_session(session_id)
        items = []
        for doc_type in VALID_DOC_TYPES:
            doc = get_document(session_id, doc_type)
            current = get_current_version(session_id, doc_type) if doc else None
            items.append(
                {
                    "doc_type": doc_type,
                    "document_id": doc["id"] if doc else None,
                    "current_version_id": doc["current_version_id"] if doc else None,
                    "current_version_no": current["version_no"] if current else None,
                    "updated_at": doc["updated_at"] if doc else None,
                }
            )
        return items


def list_versions(session_id: str, doc_type: str) -> Dict[str, Any]:
    doc_type = _validate_doc_type(doc_type)
    with transaction():
        _require_session(session_id)
        doc = get_document(session_id, doc_type)
        current_id = doc["current_version_id"] if doc else None
        rows = repository.list_versions(doc["id"]) if doc else []
        return {
            "doc_type": doc_type,
            "document_id": doc["id"] if doc else None,
            "current_version_id": current_id,
            "versions": [
                {
                    "id": row["id"],
                    "version_no": row["version_no"],
                    "source_kind": row["source_kind"],
                    "created_at": row["created_at"],
                    "content_preview": _build_preview(row["content"]),
                    "is_current": row["id"] == current_id,
                    **_version_list_metadata(_parse_metadata(row["metadata_json"])),
                }
                for row in rows
            ],
        }


def get_version(session_id: str, doc_type: str, version_id: str) -> Dict[str, Any]:
    doc_type = _validate_doc_type(doc_type)
    with transaction():
        session = _require_session(session_id)
        doc = get_document(session_id, doc_type)
        if doc is None:
            raise VersionNotFoundError(version_id)
        row = repository.get_version(doc["id"], version_id)
        if row is None:
            raise VersionNotFoundError(version_id)
        if (
            doc_type == "prd"
            and row["version_no"] == 1
            and not _parse_metadata(row["metadata_json"]).get("review")
            and row["source_kind"]
            not in (VersionSourceKind.CHECKPOINT.value, VersionSourceKind.RESTORE.value)
        ):
            backfill_prd_review_metadata(session_id, json.loads(session["session_data"]))
            row = repository.get_version(doc["id"], version_id)
            if row is None:
                raise VersionNotFoundError(version_id)
        return _row_to_version(row, doc["current_version_id"])


def update_version_note(
    session_id: str, doc_type: str, version_id: str, change_note: Optional[str] = None
) -> Dict[str, Any]:
    with transaction():
        current = get_version(session_id, doc_type, version_id)
        metadata = dict(current["metadata"])
        note = (change_note or "").strip()
        if note:
            metadata["change_note"] = note
        else:
            metadata.pop("change_note", None)
        repository.update_metadata(version_id, json.dumps(metadata, ensure_ascii=False))
        return get_version(session_id, doc_type, version_id)


def _append_version(
    doc: dict,
    content: str,
    source_kind: VersionSourceKind,
    source_job_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Dict[str, Any]:
    """Caller owns the transaction and decides which history operation to apply."""
    now = _now_iso()
    row = {
        "id": str(uuid.uuid4()),
        "document_id": doc["id"],
        "version_no": repository.next_version_number(doc["id"]),
        "content": content,
        "source_kind": source_kind.value,
        "source_job_id": source_job_id,
        "parent_version_id": doc["current_version_id"],
        "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
        "created_at": now,
    }
    repository.insert_version(row)
    repository.set_current(doc["id"], row["id"], now)
    return _row_to_version(row, row["id"])


def create_initial_version(
    session_id: str,
    doc_type: str,
    content: str,
    source_kind: VersionSourceKind,
    source_job_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    with transaction():
        doc = ensure_document(session_id, doc_type)
        if doc["current_version_id"]:
            raise DocumentVersionError(
                "current version already exists", code="DOCUMENT_CONFLICT", status_code=409
            )
        return _append_version(doc, content, source_kind, source_job_id, metadata)


def update_current_content(
    session_id: str,
    doc_type: str,
    content: str,
    source_kind: VersionSourceKind,
    source_job_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    with transaction():
        doc = ensure_document(session_id, doc_type)
        if not doc["current_version_id"]:
            return _append_version(doc, content, source_kind, source_job_id, metadata)
        row = repository.get_version(doc["id"], doc["current_version_id"])
        if row is None:
            raise VersionNotFoundError(doc["current_version_id"])
        merged = merge_metadata(_parse_metadata(row["metadata_json"]), metadata)
        # A successful retry promotes its initial failed draft without keeping the failure marker.
        if (
            source_job_id
            and source_job_id == row["source_job_id"]
            and not (metadata or {}).get("job_status")
        ):
            merged.pop("job_status", None)
        repository.update_version(
            row["id"],
            content,
            source_kind.value,
            source_job_id,
            json.dumps(merged, ensure_ascii=False),
        )
        repository.set_current(doc["id"], row["id"], _now_iso())
        updated = repository.get_version(doc["id"], row["id"])
        if updated is None:
            raise VersionNotFoundError(row["id"])
        return _row_to_version(updated, row["id"])


def append_generated_version(
    session_id: str,
    doc_type: str,
    content: str,
    source_job_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    with transaction():
        doc = ensure_document(session_id, doc_type)
        if source_job_id:
            existing = repository.version_by_job(doc["id"], source_job_id)
            if existing:
                return _row_to_version(existing, doc["current_version_id"])
        return _append_version(doc, content, VersionSourceKind.GENERATE, source_job_id, metadata)


def _sync_mirror(session_id: str, doc_type: str, content: str) -> None:
    from apps.services.session_service import sync_session_mirror_for_doc_type

    sync_session_mirror_for_doc_type(session_id, doc_type, content)


def checkpoint(
    session_id: str, doc_type: str, content: Optional[str] = None, change_note: Optional[str] = None
) -> Dict[str, Any]:
    with transaction():
        doc = ensure_document(session_id, doc_type)
        current = get_current_version(session_id, doc_type)
        snapshot = (content or "").strip() or (current["content"] if current else "")
        if not snapshot.strip():
            raise CheckpointError("无内容可保存")
        metadata = dict(current["metadata"]) if current else {}
        metadata.pop("review", None)
        if change_note:
            metadata["change_note"] = change_note
        version = _append_version(doc, snapshot, VersionSourceKind.CHECKPOINT, metadata=metadata)
        _sync_mirror(session_id, doc_type, snapshot)
        return {
            "version_id": version["id"],
            "version_no": version["version_no"],
            "document_id": doc["id"],
        }


def restore_version(session_id: str, doc_type: str, version_id: str) -> Dict[str, Any]:
    with transaction():
        doc = ensure_document(session_id, doc_type)
        if not doc["current_version_id"]:
            raise RestoreError("尚无当前文档")
        source = get_version(session_id, doc_type, version_id)
        if source["is_current"]:
            raise RestoreError("该记录已是当前工作稿")
        content = source["content"].strip()
        if not content:
            raise RestoreError("该记录无内容可恢复")
        metadata = {
            "restored_from_version_id": source["id"],
            "restored_from_version_no": source["version_no"],
        }
        if source["metadata"].get("run_summary"):
            metadata["run_summary"] = source["metadata"]["run_summary"]
        version = _append_version(doc, content, VersionSourceKind.RESTORE, metadata=metadata)
        _sync_mirror(session_id, doc_type, content)
        return {
            "version_id": version["id"],
            "version_no": version["version_no"],
            "document_id": doc["id"],
            "content": content,
        }


def build_metadata_from_job(
    job: Dict[str, Any],
    run_summary: Optional[Dict[str, Any]] = None,
    failed: bool = False,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    if run_summary:
        meta["run_summary"] = run_summary
    review = job.get("review")
    if review is None and job.get("review_json"):
        try:
            review = json.loads(job["review_json"])
        except (json.JSONDecodeError, TypeError):
            review = None
    if review:
        meta["review"] = review
    if failed:
        meta["job_status"] = "failed"
    return meta


def seed_context_documents_from_payload(
    session_id: str,
    artifact: str,
    payload: Dict[str, Any],
) -> None:
    """导入路径：将 Job payload 中的 PRD / 接口文档写入版本链（若尚未存在）。"""
    with transaction():
        prd = (payload.get("prd_content") or "").strip()
        api_docs = (payload.get("api_docs_content") or "").strip()

        if artifact in ("api-docs", "prompts") and prd:
            if get_current_version(session_id, "prd") is None:
                create_initial_version(
                    session_id,
                    "prd",
                    prd,
                    VersionSourceKind.IMPORT,
                )

        if artifact == "prompts" and api_docs:
            if get_current_version(session_id, "api-docs") is None:
                create_initial_version(
                    session_id,
                    "api-docs",
                    api_docs,
                    VersionSourceKind.IMPORT,
                )


def sync_from_job(
    session_id: str,
    artifact: str,
    content: str,
    review: Optional[Dict[str, Any]] = None,
    run_summary: Optional[Dict[str, Any]] = None,
    failed: bool = False,
    source_job_id: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    doc_type = ARTIFACT_TO_DOC_TYPE.get(artifact)
    if not doc_type or not (content or "").strip():
        return
    source_kind = (
        VersionSourceKind.OPTIMIZE
        if artifact.startswith("optimize-")
        else VersionSourceKind.GENERATE
    )
    metadata = build_metadata_from_job({"review": review}, run_summary, failed)
    if extra_metadata:
        metadata.update(extra_metadata)
    with transaction():
        doc = ensure_document(session_id, doc_type)
        current = get_current_version(session_id, doc_type)
        existing = repository.version_by_job(doc["id"], source_job_id) if source_job_id else None
        if existing:
            # Replays cannot move current back to an older task or replace a successful result.
            was_failed = _parse_metadata(existing["metadata_json"]).get("job_status") == "failed"
            if not failed and was_failed and current and current["id"] == existing["id"]:
                update_current_content(
                    session_id, doc_type, content, source_kind, source_job_id, metadata
                )
            return
        if failed and current and current["metadata"].get("job_status") != "failed":
            return
        if current is None:
            create_initial_version(
                session_id, doc_type, content, source_kind, source_job_id, metadata
            )
        elif (
            source_job_id
            and current.get("source_job_id")
            and current["source_job_id"] != source_job_id
        ):
            # Keep the earlier job association so both generation and optimization remain replayable.
            _append_version(doc, content, source_kind, source_job_id, metadata)
        elif source_kind == VersionSourceKind.GENERATE and repository.has_generated_version(
            doc["id"]
        ):
            append_generated_version(session_id, doc_type, content, source_job_id, metadata)
        else:
            # First completion replaces an imported or debounced initial draft.
            update_current_content(
                session_id, doc_type, content, source_kind, source_job_id, metadata
            )


def patch_current_metadata(session_id: str, doc_type: str, metadata: Dict[str, Any]) -> None:
    if not metadata:
        return
    with transaction():
        current = get_current_version(session_id, doc_type)
        if current:
            merged = merge_metadata(current["metadata"], metadata)
            repository.update_metadata(current["id"], json.dumps(merged, ensure_ascii=False))


def _prd_review_from_session(session_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    review = session_data.get("prdReviewResult")
    if review and isinstance(review, dict):
        return review
    return None


def backfill_prd_review_metadata(
    session_id: str,
    session_data: Dict[str, Any],
) -> None:
    """将 session 中的 prdReviewResult 回填到初始记录 metadata（仅老数据迁移，无 metadata 时）。"""
    review = _prd_review_from_session(session_data)
    if not review:
        return
    with transaction():
        doc = get_document(session_id, "prd")
        row = repository.version_by_number(doc["id"], 1) if doc else None
        if not row or row["source_kind"] in (
            VersionSourceKind.CHECKPOINT.value,
            VersionSourceKind.RESTORE.value,
        ):
            return
        existing = _parse_metadata(row["metadata_json"])
        if existing.get("review"):
            return
        merged = merge_metadata(existing, {"review": review})
        repository.update_metadata(row["id"], json.dumps(merged, ensure_ascii=False))


def migrate_session_documents_if_needed(
    session_id: str,
    session_data: Dict[str, Any],
) -> None:
    with transaction():
        for doc_type, field in DOC_TYPE_TO_SESSION_FIELD.items():
            content = (session_data.get(field) or "").strip()
            if not content:
                continue
            doc = get_document(session_id, doc_type)
            if doc and doc.get("current_version_id"):
                continue
            metadata: Optional[Dict[str, Any]] = None
            if doc_type == "prd":
                review = _prd_review_from_session(session_data)
                if review:
                    metadata = {"review": review}
            create_initial_version(
                session_id,
                doc_type,
                content,
                VersionSourceKind.IMPORT,
                metadata=metadata,
            )
        backfill_prd_review_metadata(session_id, session_data)


def sync_session_content_to_documents(
    session_id: str,
    session_data: Dict[str, Any],
) -> None:
    with transaction():
        for doc_type, field in DOC_TYPE_TO_SESSION_FIELD.items():
            content = session_data.get(field) or ""
            if not content.strip():
                continue
            current = get_current_version(session_id, doc_type)
            if current is None:
                create_initial_version(
                    session_id,
                    doc_type,
                    content,
                    VersionSourceKind.AUTO_SAVE,
                )
            elif content != current.get("content"):
                update_current_content(
                    session_id,
                    doc_type,
                    content,
                    VersionSourceKind.AUTO_SAVE,
                )


def refresh_session_content_from_documents(
    session_id: str,
    session_data: Dict[str, Any],
) -> bool:
    changed = False
    for doc_type, field in DOC_TYPE_TO_SESSION_FIELD.items():
        current = get_current_version(session_id, doc_type)
        if not current:
            continue
        if current.get("content") != session_data.get(field):
            session_data[field] = current["content"]
            changed = True
    return changed


def get_current_content_for_doc_type(session_id: str, doc_type: str) -> Optional[str]:
    current = get_current_version(session_id, doc_type)
    if not current:
        return None
    return current.get("content")
