"""Generation Job CRUD"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from db.database import get_connection

VALID_ARTIFACTS = {
    "prd",
    "api-docs",
    "prompts",
    "optimize-prd",
    "optimize-api-docs",
    "optimize-prompts",
}

CONFLICT_GROUPS = {
    "prd": {"prd", "optimize-prd"},
    "optimize-prd": {"prd", "optimize-prd"},
    "api-docs": {"api-docs", "optimize-api-docs"},
    "optimize-api-docs": {"api-docs", "optimize-api-docs"},
    "prompts": {"prompts", "optimize-prompts"},
    "optimize-prompts": {"prompts", "optimize-prompts"},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_job(row) -> Dict[str, Any]:
    review = json.loads(row["review_json"]) if row["review_json"] else None
    result = json.loads(row["result_json"]) if row["result_json"] else None
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "artifact": row["artifact"],
        "status": row["status"],
        "phase": row["phase"],
        "payload_json": row["payload_json"],
        "draft_content": row["draft_content"] or "",
        "previous_draft": row["previous_draft"] or "",
        "review_json": row["review_json"],
        "review": review,
        "result_json": row["result_json"],
        "result": result,
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class JobConflictError(Exception):
    def __init__(self, job_id: str):
        super().__init__("Job already running")
        self.job_id = job_id


def get_conflicting_running_job(session_id: str, artifact: str) -> Optional[Dict[str, Any]]:
    group = CONFLICT_GROUPS.get(artifact, {artifact})
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM generation_jobs
            WHERE session_id = ? AND status = 'running'
            ORDER BY created_at DESC
            """,
            (session_id,),
        ).fetchall()
    for row in rows:
        if row["artifact"] in group:
            return _row_to_job(row)
    return None


def get_running_job(session_id: str, artifact: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM generation_jobs
            WHERE session_id = ? AND artifact = ? AND status = 'running'
            ORDER BY created_at DESC LIMIT 1
            """,
            (session_id, artifact),
        ).fetchone()
    return _row_to_job(row) if row else None


def create_job(session_id: str, artifact: str, payload: dict) -> str:
    if artifact not in VALID_ARTIFACTS:
        raise ValueError(f"Unsupported artifact: {artifact}")

    existing = get_conflicting_running_job(session_id, artifact)
    if existing:
        raise JobConflictError(existing["id"])

    job_id = str(uuid.uuid4())
    now = _now_iso()
    if artifact == "prd":
        initial_phase = "writing"
    else:
        initial_phase = "generating"
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO generation_jobs (
                id, session_id, artifact, status, phase, payload_json,
                draft_content, previous_draft, review_json, result_json, error,
                created_at, updated_at
            ) VALUES (?, ?, ?, 'pending', ?, ?, '', '', NULL, NULL, NULL, ?, ?)
            """,
            (
                job_id,
                session_id,
                artifact,
                initial_phase,
                json.dumps(payload, ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.commit()
    return job_id


def get_job(job_id: str) -> Dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM generation_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    if not row:
        raise KeyError(job_id)
    return _row_to_job(row)


def update_job(job_id: str, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = _now_iso()
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [job_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE generation_jobs SET {columns} WHERE id = ?",
            values,
        )
        conn.commit()


def set_draft_content(job_id: str, content: str) -> None:
    update_job(job_id, draft_content=content)
