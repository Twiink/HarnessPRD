"""文档、历史与来源快照的只读用例。"""

import json
import re
from typing import Any, Dict, List, Optional
from apps.db.connection import read_snapshot
from apps.db.repositories import documents as repository
from apps.db.repositories import sessions as session_repository
from apps.domain.documents import (
    VALID_DOC_TYPES,
    VersionSourceKind,
    SessionNotFoundError,
    InvalidDocTypeError,
    VersionNotFoundError,
)
from apps.domain.documents.content_identity import bind_metadata, content_hash

CONTENT_PREVIEW_LEN = 200


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


def _row_to_version(row: dict, current_version_id: Optional[str]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "version_no": row["version_no"],
        "content": row["content"] or "",
        "source_kind": row["source_kind"],
        "source_job_id": row["source_job_id"],
        "parent_version_id": row["parent_version_id"],
        "metadata": bind_metadata(row["content"] or "", _parse_metadata(row["metadata_json"])),
        "created_at": row["created_at"],
        "is_current": row["id"] == current_version_id,
        "content_preview": _build_preview(row["content"] or ""),
    }


def get_document(session_id: str, doc_type: str) -> Optional[Dict[str, Any]]:
    return repository.get_document(session_id, _validate_doc_type(doc_type))


def get_current_version(session_id: str, doc_type: str) -> Optional[Dict[str, Any]]:
    with read_snapshot():
        doc = get_document(session_id, doc_type)
        if not doc or not doc["current_version_id"]:
            return None
        row = repository.get_version(doc["id"], doc["current_version_id"])
        return _row_to_version(row, doc["current_version_id"]) if row else None


def get_documents_by_session(session_id: str) -> List[Dict[str, Any]]:
    with read_snapshot():
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
    with read_snapshot():
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
    with read_snapshot():
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
            needs_backfill = bool(json.loads(session["session_data"]).get("prdReviewResult"))
        else:
            needs_backfill = False
        result = _row_to_version(row, doc["current_version_id"])
        legacy = json.loads(session["session_data"])
        if (
            needs_backfill
            and row["content"] == legacy.get("prdContent")
            and not _parse_metadata(row["metadata_json"]).get("content_hash")
            and isinstance(legacy.get("prdReviewResult"), dict)
        ):
            # 旧数据报告仅叠加到查询快照；迁移写入由保存用例负责。
            result["metadata"]["review"] = legacy["prdReviewResult"]
        return result


def get_current_content_for_doc_type(session_id: str, doc_type: str) -> Optional[str]:
    current = get_current_version(session_id, doc_type)
    if not current:
        return None
    return current.get("content")


def build_source_snapshot(session_id: str, artifact: str, prepared_payload: dict) -> dict:
    """Describe the actual submitted inputs; overrides never inherit unrelated version IDs."""
    sources: dict[str, Any] = {}
    if artifact in ("optimize-api-docs", "optimize-prompts"):
        content = prepared_payload.get("current_content") or ""
        with read_snapshot():
            current = get_current_version(session_id, artifact.removeprefix("optimize-"))
            if current and current["content"] == content:
                sources = dict(current["metadata"].get("derived_from") or {})
            if not any(
                sources.get(key) for key in ("prd_content_hash", "prd_version_id", "prd_version_no")
            ):
                sources["unverified"] = True
            sources["input_content_hash"] = content_hash(content)
        return sources
    if artifact not in ("api-docs", "prompts"):
        return sources
    with read_snapshot():
        for doc_type, prefix in (("prd", "prd"), ("api-docs", "api_docs")):
            if doc_type == "api-docs" and artifact != "prompts":
                continue
            content = prepared_payload.get(f"{prefix}_content") or ""
            if doc_type == "api-docs" and not content:
                sources["api_docs_skipped"] = True
                continue
            sources[f"{prefix}_content_hash"] = content_hash(content)
            current = get_current_version(session_id, doc_type)
            if current and current["content"] == content:
                sources[f"{prefix}_version_id"] = current["id"]
                sources[f"{prefix}_version_no"] = current["version_no"]
    return sources
