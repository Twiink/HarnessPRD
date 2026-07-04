"""文档槽位与版本链"""

import json
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from db.database import get_connection

VALID_DOC_TYPES = ("prd", "api-docs", "prompts")
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


class VersionSourceKind(str, Enum):
    GENERATE = "generate"
    OPTIMIZE = "optimize"
    AUTO_SAVE = "auto_save"
    CHECKPOINT = "checkpoint"
    RESTORE = "restore"
    IMPORT = "import"


class DocumentVersionError(Exception):
    pass


class SessionNotFoundError(DocumentVersionError):
    pass


class InvalidDocTypeError(DocumentVersionError):
    pass


class VersionNotFoundError(DocumentVersionError):
    pass


class CheckpointError(DocumentVersionError):
    pass


class RestoreError(DocumentVersionError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_doc_type(doc_type: str) -> str:
    if doc_type not in VALID_DOC_TYPES:
        raise InvalidDocTypeError(doc_type)
    return doc_type


def _session_exists(session_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM project_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    return row is not None


def _require_session(session_id: str) -> None:
    if not _session_exists(session_id):
        raise SessionNotFoundError(session_id)


def _build_preview(content: str) -> str:
    text = re.sub(r"\s+", " ", content or "").strip()
    if len(text) <= CONTENT_PREVIEW_LEN:
        return text
    return text[:CONTENT_PREVIEW_LEN] + "..."


def _version_list_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    change_note = (meta.get("change_note") or "").strip()
    if change_note:
        out["change_note"] = change_note
    restored_from = meta.get("restored_from_version_no")
    if restored_from is not None:
        out["restored_from_version_no"] = int(restored_from)
    return out


def _parse_metadata(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def merge_metadata(old: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(old or {})
    if not new:
        return merged
    for key, value in new.items():
        if value is not None:
            merged[key] = value
    return merged


def _row_to_version(row, current_version_id: Optional[str]) -> Dict[str, Any]:
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
    _require_session(session_id)

    def _ensure(c):
        row = c.execute(
            "SELECT * FROM documents WHERE session_id = ? AND doc_type = ?",
            (session_id, doc_type),
        ).fetchone()
        if row:
            return dict(row)
        now = _now_iso()
        doc_id = str(uuid.uuid4())
        c.execute(
            """
            INSERT INTO documents (id, session_id, doc_type, current_version_id, created_at, updated_at)
            VALUES (?, ?, ?, NULL, ?, ?)
            """,
            (doc_id, session_id, doc_type, now, now),
        )
        return {
            "id": doc_id,
            "session_id": session_id,
            "doc_type": doc_type,
            "current_version_id": None,
            "created_at": now,
            "updated_at": now,
        }

    if conn is not None:
        return _ensure(conn)

    with get_connection() as c:
        doc = _ensure(c)
        c.commit()
        return doc


def get_document(session_id: str, doc_type: str) -> Optional[Dict[str, Any]]:
    doc_type = _validate_doc_type(doc_type)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE session_id = ? AND doc_type = ?",
            (session_id, doc_type),
        ).fetchone()
    return dict(row) if row else None


def get_current_version(session_id: str, doc_type: str) -> Optional[Dict[str, Any]]:
    doc = get_document(session_id, doc_type)
    if not doc or not doc.get("current_version_id"):
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM document_versions WHERE id = ?",
            (doc["current_version_id"],),
        ).fetchone()
    if not row:
        return None
    return _row_to_version(row, doc["current_version_id"])


def get_documents_by_session(session_id: str) -> List[Dict[str, Any]]:
    _require_session(session_id)
    items: List[Dict[str, Any]] = []
    with get_connection() as conn:
        for doc_type in VALID_DOC_TYPES:
            row = conn.execute(
                "SELECT * FROM documents WHERE session_id = ? AND doc_type = ?",
                (session_id, doc_type),
            ).fetchone()
            if not row:
                items.append(
                    {
                        "doc_type": doc_type,
                        "document_id": None,
                        "current_version_id": None,
                        "current_version_no": None,
                        "updated_at": None,
                    }
                )
                continue
            current_version_no = None
            if row["current_version_id"]:
                ver = conn.execute(
                    "SELECT version_no FROM document_versions WHERE id = ?",
                    (row["current_version_id"],),
                ).fetchone()
                if ver:
                    current_version_no = ver["version_no"]
            items.append(
                {
                    "doc_type": doc_type,
                    "document_id": row["id"],
                    "current_version_id": row["current_version_id"],
                    "current_version_no": current_version_no,
                    "updated_at": row["updated_at"],
                }
            )
    return items


def list_versions(session_id: str, doc_type: str) -> Dict[str, Any]:
    doc_type = _validate_doc_type(doc_type)
    _require_session(session_id)
    doc = get_document(session_id, doc_type)
    if not doc:
        return {
            "doc_type": doc_type,
            "document_id": None,
            "current_version_id": None,
            "versions": [],
        }
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM document_versions
            WHERE document_id = ?
            ORDER BY version_no DESC
            """,
            (doc["id"],),
        ).fetchall()
    current_id = doc.get("current_version_id")
    versions = [
        {
            "id": row["id"],
            "version_no": row["version_no"],
            "source_kind": row["source_kind"],
            "created_at": row["created_at"],
            "content_preview": _build_preview(row["content"] or ""),
            "is_current": row["id"] == current_id,
            **_version_list_metadata(_parse_metadata(row["metadata_json"])),
        }
        for row in rows
    ]
    return {
        "doc_type": doc_type,
        "document_id": doc["id"],
        "current_version_id": current_id,
        "versions": versions,
    }


def get_version(session_id: str, doc_type: str, version_id: str) -> Dict[str, Any]:
    doc_type = _validate_doc_type(doc_type)
    _require_session(session_id)
    doc = get_document(session_id, doc_type)
    if not doc:
        raise VersionNotFoundError(version_id)

    def _fetch():
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM document_versions WHERE id = ? AND document_id = ?",
                (version_id, doc["id"]),
            ).fetchone()

    row = _fetch()
    if not row:
        raise VersionNotFoundError(version_id)

    parsed = _parse_metadata(row["metadata_json"])
    if (
        doc_type == "prd"
        and row["version_no"] == 1
        and not parsed.get("review")
        and row["source_kind"]
        not in (VersionSourceKind.CHECKPOINT.value, VersionSourceKind.RESTORE.value)
    ):
        with get_connection() as conn:
            session_row = conn.execute(
                "SELECT session_data FROM project_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if session_row:
            session_data = json.loads(session_row["session_data"])
            backfill_prd_review_metadata(session_id, session_data)
            row = _fetch()
            if not row:
                raise VersionNotFoundError(version_id)

    return _row_to_version(row, doc.get("current_version_id"))


def update_version_note(
    session_id: str,
    doc_type: str,
    version_id: str,
    change_note: Optional[str] = None,
) -> Dict[str, Any]:
    doc_type = _validate_doc_type(doc_type)
    _require_session(session_id)
    doc = get_document(session_id, doc_type)
    if not doc:
        raise VersionNotFoundError(version_id)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM document_versions WHERE id = ? AND document_id = ?",
            (version_id, doc["id"]),
        ).fetchone()
        if not row:
            raise VersionNotFoundError(version_id)

        meta = _parse_metadata(row["metadata_json"])
        note = (change_note or "").strip()
        if note:
            meta["change_note"] = note
        else:
            meta.pop("change_note", None)

        conn.execute(
            "UPDATE document_versions SET metadata_json = ? WHERE id = ?",
            (json.dumps(meta, ensure_ascii=False), version_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM document_versions WHERE id = ?", (version_id,)
        ).fetchone()

    return _row_to_version(updated, doc.get("current_version_id"))


def create_initial_version(
    session_id: str,
    doc_type: str,
    content: str,
    source_kind: VersionSourceKind,
    source_job_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    doc_type = _validate_doc_type(doc_type)
    with get_connection() as conn:
        doc = ensure_document(session_id, doc_type, conn=conn)
        if doc.get("current_version_id"):
            raise DocumentVersionError("current version already exists")
        now = _now_iso()
        version_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO document_versions (
                id, document_id, version_no, content, source_kind,
                source_job_id, parent_version_id, metadata_json, created_at
            ) VALUES (?, ?, 1, ?, ?, ?, NULL, ?, ?)
            """,
            (
                version_id,
                doc["id"],
                content,
                source_kind.value,
                source_job_id,
                json.dumps(metadata or {}, ensure_ascii=False),
                now,
            ),
        )
        conn.execute(
            """
            UPDATE documents SET current_version_id = ?, updated_at = ? WHERE id = ?
            """,
            (version_id, now, doc["id"]),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM document_versions WHERE id = ?", (version_id,)
        ).fetchone()
    return _row_to_version(row, version_id)


def update_current_content(
    session_id: str,
    doc_type: str,
    content: str,
    source_kind: VersionSourceKind,
    source_job_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    doc_type = _validate_doc_type(doc_type)
    with get_connection() as conn:
        doc = ensure_document(session_id, doc_type, conn=conn)
        current_id = doc.get("current_version_id")
        now = _now_iso()
        if not current_id:
            return create_initial_version(
                session_id, doc_type, content, source_kind, source_job_id, metadata
            )
        row = conn.execute(
            "SELECT * FROM document_versions WHERE id = ?", (current_id,)
        ).fetchone()
        merged = merge_metadata(_parse_metadata(row["metadata_json"]), metadata)
        conn.execute(
            """
            UPDATE document_versions
            SET content = ?, source_kind = ?, source_job_id = COALESCE(?, source_job_id),
                metadata_json = ?
            WHERE id = ?
            """,
            (
                content,
                source_kind.value,
                source_job_id,
                json.dumps(merged, ensure_ascii=False),
                current_id,
            ),
        )
        conn.execute(
            "UPDATE documents SET updated_at = ? WHERE id = ?",
            (now, doc["id"]),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM document_versions WHERE id = ?", (current_id,)
        ).fetchone()
    return _row_to_version(updated, current_id)


def append_generated_version(
    session_id: str,
    doc_type: str,
    content: str,
    source_job_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """整份生成 Job 完成：在已有 current 时升新版，旧版进历史。"""
    doc_type = _validate_doc_type(doc_type)
    with get_connection() as conn:
        doc = ensure_document(session_id, doc_type, conn=conn)
        current_id = doc.get("current_version_id")
        if not current_id:
            return create_initial_version(
                session_id,
                doc_type,
                content,
                VersionSourceKind.GENERATE,
                source_job_id=source_job_id,
                metadata=metadata,
            )

        max_row = conn.execute(
            "SELECT MAX(version_no) AS m FROM document_versions WHERE document_id = ?",
            (doc["id"],),
        ).fetchone()
        next_no = int(max_row["m"] or 0) + 1
        now = _now_iso()
        new_version_id = str(uuid.uuid4())
        meta = dict(metadata or {})

        conn.execute(
            """
            INSERT INTO document_versions (
                id, document_id, version_no, content, source_kind,
                source_job_id, parent_version_id, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_version_id,
                doc["id"],
                next_no,
                content,
                VersionSourceKind.GENERATE.value,
                source_job_id,
                current_id,
                json.dumps(meta, ensure_ascii=False),
                now,
            ),
        )
        conn.execute(
            """
            UPDATE documents SET current_version_id = ?, updated_at = ? WHERE id = ?
            """,
            (new_version_id, now, doc["id"]),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM document_versions WHERE id = ?", (new_version_id,)
        ).fetchone()
    return _row_to_version(row, new_version_id)


def checkpoint(
    session_id: str,
    doc_type: str,
    content: Optional[str] = None,
    change_note: Optional[str] = None,
) -> Dict[str, Any]:
    doc_type = _validate_doc_type(doc_type)
    with get_connection() as conn:
        doc = ensure_document(session_id, doc_type, conn=conn)
        current_id = doc.get("current_version_id")
        parent_version_id = None
        body_content = (content or "").strip()

        if not current_id:
            if not body_content:
                raise CheckpointError("无内容可保存")
            now = _now_iso()
            version_id = str(uuid.uuid4())
            meta: Dict[str, Any] = {}
            if change_note:
                meta["change_note"] = change_note
            conn.execute(
                """
                INSERT INTO document_versions (
                    id, document_id, version_no, content, source_kind,
                    source_job_id, parent_version_id, metadata_json, created_at
                ) VALUES (?, ?, 1, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    version_id,
                    doc["id"],
                    body_content,
                    VersionSourceKind.CHECKPOINT.value,
                    json.dumps(meta, ensure_ascii=False),
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE documents SET current_version_id = ?, updated_at = ? WHERE id = ?
                """,
                (version_id, now, doc["id"]),
            )
            conn.commit()
            return {
                "version_id": version_id,
                "version_no": 1,
                "document_id": doc["id"],
            }

        current_row = conn.execute(
            "SELECT * FROM document_versions WHERE id = ?", (current_id,)
        ).fetchone()
        snapshot_content = body_content or (current_row["content"] or "")
        if not snapshot_content.strip():
            raise CheckpointError("无内容可保存")

        parent_version_id = current_id
        max_row = conn.execute(
            "SELECT MAX(version_no) AS m FROM document_versions WHERE document_id = ?",
            (doc["id"],),
        ).fetchone()
        next_no = int(max_row["m"] or 0) + 1
        now = _now_iso()
        new_version_id = str(uuid.uuid4())
        meta = merge_metadata(_parse_metadata(current_row["metadata_json"]), None)
        meta.pop("review", None)
        if change_note:
            meta["change_note"] = change_note

        conn.execute(
            """
            INSERT INTO document_versions (
                id, document_id, version_no, content, source_kind,
                source_job_id, parent_version_id, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                new_version_id,
                doc["id"],
                next_no,
                snapshot_content,
                VersionSourceKind.CHECKPOINT.value,
                parent_version_id,
                json.dumps(meta, ensure_ascii=False),
                now,
            ),
        )
        conn.execute(
            """
            UPDATE documents SET current_version_id = ?, updated_at = ? WHERE id = ?
            """,
            (new_version_id, now, doc["id"]),
        )
        conn.commit()
    return {
        "version_id": new_version_id,
        "version_no": next_no,
        "document_id": doc["id"],
    }


def restore_version(
    session_id: str,
    doc_type: str,
    version_id: str,
) -> Dict[str, Any]:
    doc_type = _validate_doc_type(doc_type)
    with get_connection() as conn:
        doc = ensure_document(session_id, doc_type, conn=conn)
        current_id = doc.get("current_version_id")
        if not current_id:
            raise RestoreError("尚无当前版本")

        source_row = conn.execute(
            "SELECT * FROM document_versions WHERE id = ? AND document_id = ?",
            (version_id, doc["id"]),
        ).fetchone()
        if not source_row:
            raise VersionNotFoundError(version_id)

        if source_row["id"] == current_id:
            raise RestoreError("该版本已是当前版本")

        source_content = (source_row["content"] or "").strip()
        if not source_content:
            raise RestoreError("该版本无内容可恢复")

        source_meta = _parse_metadata(source_row["metadata_json"])
        meta: Dict[str, Any] = {
            "restored_from_version_id": source_row["id"],
            "restored_from_version_no": source_row["version_no"],
        }
        if source_meta.get("run_summary"):
            meta["run_summary"] = source_meta["run_summary"]

        max_row = conn.execute(
            "SELECT MAX(version_no) AS m FROM document_versions WHERE document_id = ?",
            (doc["id"],),
        ).fetchone()
        next_no = int(max_row["m"] or 0) + 1
        now = _now_iso()
        new_version_id = str(uuid.uuid4())

        conn.execute(
            """
            INSERT INTO document_versions (
                id, document_id, version_no, content, source_kind,
                source_job_id, parent_version_id, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                new_version_id,
                doc["id"],
                next_no,
                source_content,
                VersionSourceKind.RESTORE.value,
                current_id,
                json.dumps(meta, ensure_ascii=False),
                now,
            ),
        )
        conn.execute(
            """
            UPDATE documents SET current_version_id = ?, updated_at = ? WHERE id = ?
            """,
            (new_version_id, now, doc["id"]),
        )
        conn.commit()

    return {
        "version_id": new_version_id,
        "version_no": next_no,
        "document_id": doc["id"],
        "content": source_content,
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
    if not doc_type:
        return
    if not (content or "").strip():
        return
    source_kind = (
        VersionSourceKind.OPTIMIZE
        if artifact.startswith("optimize-")
        else VersionSourceKind.GENERATE
    )
    job_row = {"review": review, "review_json": json.dumps(review, ensure_ascii=False) if review else None}
    metadata = build_metadata_from_job(job_row, run_summary=run_summary, failed=failed)
    if extra_metadata:
        metadata.update(extra_metadata)
    current = get_current_version(session_id, doc_type)
    if current is None:
        create_initial_version(
            session_id,
            doc_type,
            content,
            source_kind,
            source_job_id=source_job_id,
            metadata=metadata,
        )
    elif source_kind == VersionSourceKind.GENERATE:
        # 生成进行中前端 debounce 可能已把流式草稿落成 auto_save 的 v1；
        # 首次 Job 完成应覆盖 current，而不是再 append 出 v2。
        if _document_has_generate_version(session_id, doc_type):
            append_generated_version(
                session_id,
                doc_type,
                content,
                source_job_id=source_job_id,
                metadata=metadata,
            )
        else:
            update_current_content(
                session_id,
                doc_type,
                content,
                source_kind,
                source_job_id=source_job_id,
                metadata=metadata,
            )
    else:
        update_current_content(
            session_id,
            doc_type,
            content,
            source_kind,
            source_job_id=source_job_id,
            metadata=metadata,
        )


def _document_has_generate_version(session_id: str, doc_type: str) -> bool:
    """该文档是否已有过一次「生成」里程碑（用于区分首次完成 vs 再次点击生成）。"""
    doc_type = _validate_doc_type(doc_type)
    doc = get_document(session_id, doc_type)
    if not doc:
        return False
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM document_versions
            WHERE document_id = ? AND source_kind = ?
            LIMIT 1
            """,
            (doc["id"], VersionSourceKind.GENERATE.value),
        ).fetchone()
    return row is not None


def patch_current_metadata(
    session_id: str,
    doc_type: str,
    metadata: Dict[str, Any],
) -> None:
    if not metadata:
        return
    current = get_current_version(session_id, doc_type)
    if not current:
        return
    merged = merge_metadata(current.get("metadata"), metadata)
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE document_versions SET metadata_json = ? WHERE id = ?
            """,
            (json.dumps(merged, ensure_ascii=False), current["id"]),
        )
        conn.commit()


def _prd_review_from_session(session_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    review = session_data.get("prdReviewResult")
    if review and isinstance(review, dict):
        return review
    return None


def backfill_prd_review_metadata(
    session_id: str,
    session_data: Dict[str, Any],
) -> None:
    """将 session 中的 prdReviewResult 回填到 v1 metadata（仅老数据迁移，无 metadata 时）。"""
    review = _prd_review_from_session(session_data)
    if not review:
        return
    doc = get_document(session_id, "prd")
    if not doc:
        return
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM document_versions
            WHERE document_id = ? AND version_no = 1
            """,
            (doc["id"],),
        ).fetchone()
    if not row:
        return
    if row["source_kind"] in (
        VersionSourceKind.CHECKPOINT.value,
        VersionSourceKind.RESTORE.value,
    ):
        return
    existing = _parse_metadata(row["metadata_json"])
    if existing.get("review"):
        return
    merged = merge_metadata(existing, {"review": review})
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE document_versions SET metadata_json = ? WHERE id = ?
            """,
            (json.dumps(merged, ensure_ascii=False), row["id"]),
        )
        conn.commit()


def migrate_session_documents_if_needed(
    session_id: str,
    session_data: Dict[str, Any],
) -> None:
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
