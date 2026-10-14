"""编号迁移：升级现有 SQLite 数据，保留文档历史。"""

import sqlite3
import json
from datetime import datetime, timezone

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS project_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    entry_mode TEXT,
    current_stage TEXT,
    status TEXT,
    session_data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_CREATE_GENERATION_JOBS_SQL = """
CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    artifact TEXT NOT NULL,
    status TEXT NOT NULL,
    phase TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    draft_content TEXT DEFAULT '',
    previous_draft TEXT DEFAULT '',
    review_json TEXT,
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_CREATE_GENERATION_JOBS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_generation_jobs_session ON generation_jobs(session_id)
"""

_CREATE_DOCUMENTS_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    current_version_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(session_id, doc_type)
)
"""

_CREATE_DOCUMENT_VERSIONS_SQL = """
CREATE TABLE IF NOT EXISTS document_versions (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL,
    source_job_id TEXT,
    parent_version_id TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(document_id, version_no)
)
"""

_CREATE_DOCUMENTS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_documents_session ON documents(session_id)
"""

_CREATE_DOCUMENT_VERSIONS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_document_versions_document ON document_versions(document_id)
"""


LATEST_VERSION = 2


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _initial(conn: sqlite3.Connection) -> None:
    for statement in (
        _CREATE_TABLE_SQL,
        _CREATE_GENERATION_JOBS_SQL,
        _CREATE_GENERATION_JOBS_INDEX_SQL,
        _CREATE_DOCUMENTS_SQL,
        _CREATE_DOCUMENT_VERSIONS_SQL,
        _CREATE_DOCUMENTS_INDEX_SQL,
        _CREATE_DOCUMENT_VERSIONS_INDEX_SQL,
    ):
        conn.execute(statement)


def _reliable_jobs(conn: sqlite3.Connection) -> None:
    fields = {
        "attempt_count": "INTEGER NOT NULL DEFAULT 0",
        "worker_id": "TEXT",
        "lease_until": "TEXT",
        "started_at": "TEXT",
        "finished_at": "TEXT",
        "error_code": "TEXT",
        "cancel_requested": "INTEGER NOT NULL DEFAULT 0",
        "idempotency_key": "TEXT",
        "conflict_key": "TEXT",
        "request_id": "TEXT",
        "submission_hash": "TEXT",
    }
    columns = {row[1] for row in conn.execute("PRAGMA table_info(generation_jobs)")}
    for name, definition in fields.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE generation_jobs ADD COLUMN {name} {definition}")
    conn.execute("UPDATE generation_jobs SET status='succeeded' WHERE status='completed'")
    conn.execute("UPDATE generation_jobs SET conflict_key=REPLACE(artifact,'optimize-','')")
    active = conn.execute(
        "SELECT id,session_id,conflict_key FROM generation_jobs WHERE status IN ('pending','queued','running','interrupted') ORDER BY created_at,id"
    ).fetchall()
    seen = set()
    for row in active:
        key = (row["session_id"], row["conflict_key"])
        if key in seen:
            conn.execute(
                "UPDATE generation_jobs SET status='failed', error_code='LEGACY_JOB_CONFLICT', error='旧任务与另一活跃任务冲突', finished_at=?, lease_until=NULL WHERE id=?",
                (now_iso(), row["id"]),
            )
        seen.add(key)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_job_active_document ON generation_jobs(session_id,conflict_key) WHERE status IN ('pending','queued','running','interrupted')"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_job_idempotency ON generation_jobs(session_id,idempotency_key) WHERE idempotency_key IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_queue ON generation_jobs(status,lease_until,created_at)"
    )
    conn.execute("""CREATE TABLE IF NOT EXISTS job_events (
        job_id TEXT NOT NULL REFERENCES generation_jobs(id) ON DELETE CASCADE,
        sequence INTEGER NOT NULL, event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(job_id,sequence)
    )""")
    conn.execute(
        "UPDATE generation_jobs SET status='failed',error_code='SESSION_NOT_FOUND',error='任务所属方案已删除',finished_at=?,worker_id=NULL,lease_until=NULL WHERE status IN ('pending','queued','running','interrupted') AND session_id NOT IN (SELECT id FROM project_sessions)",
        (now_iso(),),
    )
    conn.execute(
        "UPDATE generation_jobs SET error='历史任务执行失败',error_code='LEGACY_FAILURE' WHERE status='failed' AND error_code IS NULL"
    )
    terminal = conn.execute(
        "SELECT * FROM generation_jobs WHERE status IN ('succeeded','failed','cancelled')"
    ).fetchall()
    for row in terminal:
        payload = {
            "type": "snapshot",
            "status": row["status"],
            "phase": row["phase"],
            "artifact": row["artifact"],
            "draft_content": row["draft_content"] or "",
        }
        conn.execute(
            "INSERT INTO job_events VALUES (?,?,?,?,?)",
            (row["id"], 1, "snapshot", json.dumps(payload, ensure_ascii=False), now_iso()),
        )
        conn.execute(
            "INSERT INTO job_events VALUES (?,?,?,?,?)",
            (
                row["id"],
                2,
                row["status"],
                json.dumps({"type": row["status"], "status": row["status"]}, ensure_ascii=False),
                now_iso(),
            ),
        )
    # 保留旧重复版本，只解除其中较早记录的任务关联。
    conn.execute("""UPDATE document_versions SET source_job_id=NULL
        WHERE source_job_id IS NOT NULL AND version_no < (
            SELECT MAX(v.version_no) FROM document_versions v
            WHERE v.document_id=document_versions.document_id
            AND v.source_job_id=document_versions.source_job_id
        )""")
    conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_document_job_version
        ON document_versions(document_id,source_job_id) WHERE source_job_id IS NOT NULL""")


MIGRATIONS = ((1, _initial), (2, _reliable_jobs))


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        if applied - {version for version, _ in MIGRATIONS}:
            raise RuntimeError("数据库迁移版本高于当前程序支持版本")
        for version, migration in MIGRATIONS:
            if version not in applied:
                migration(conn)
                conn.execute("INSERT INTO schema_migrations VALUES (?,?)", (version, now_iso()))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
