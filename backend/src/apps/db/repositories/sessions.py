"""Session row access and deletion of session-owned records."""

from apps.db.connection import get_connection
from apps.domain.jobs import ACTIVE_STATUSES


def get(session_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM project_sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None


def list_all() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, title, entry_mode, current_stage, status, created_at, updated_at
            FROM project_sessions ORDER BY updated_at DESC"""
        ).fetchall()
        return [dict(row) for row in rows]


def insert(row: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO project_sessions
            (id, title, entry_mode, current_stage, status, session_data, created_at, updated_at)
            VALUES (:id, :title, :entry_mode, :current_stage, :status, :session_data,
                    :created_at, :updated_at)""",
            row,
        )


def update(session_id: str, entry_mode: str, stage: str, status: str, data: str, now: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE project_sessions SET entry_mode=?, current_stage=?, status=?,
            session_data=?, updated_at=? WHERE id=?""",
            (entry_mode, stage, status, data, now, session_id),
        )


def update_data(session_id: str, data: str, now: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE project_sessions SET session_data=?, updated_at=? WHERE id=?",
            (data, now, session_id),
        )


def active_job_id(session_id: str, exclude_job_id: str | None = None) -> str | None:
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT id FROM generation_jobs WHERE session_id=? AND status IN ({placeholders}) AND id!=? ORDER BY created_at,id LIMIT 1",
            (session_id, *ACTIVE_STATUSES, exclude_job_id or ""),
        ).fetchone()
        return row["id"] if row else None


def delete_tree(session_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM job_events WHERE job_id IN (SELECT id FROM generation_jobs WHERE session_id=?)",
            (session_id,),
        )
        conn.execute("DELETE FROM generation_jobs WHERE session_id=?", (session_id,))
        conn.execute(
            """DELETE FROM document_versions WHERE document_id IN
            (SELECT id FROM documents WHERE session_id=?)""",
            (session_id,),
        )
        conn.execute("DELETE FROM documents WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM project_sessions WHERE id=?", (session_id,))
