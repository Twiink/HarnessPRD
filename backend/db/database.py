"""SQLite 数据库连接与表初始化"""

from contextlib import contextmanager
from pathlib import Path

import sqlite3

DB_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DB_DIR / "sessions.db"

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


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(_CREATE_GENERATION_JOBS_SQL)
        conn.execute(_CREATE_GENERATION_JOBS_INDEX_SQL)
        conn.execute(_CREATE_DOCUMENTS_SQL)
        conn.execute(_CREATE_DOCUMENT_VERSIONS_SQL)
        conn.execute(_CREATE_DOCUMENTS_INDEX_SQL)
        conn.execute(_CREATE_DOCUMENT_VERSIONS_INDEX_SQL)
        conn.execute(
            """
            UPDATE generation_jobs
            SET status = 'failed',
                error = COALESCE(error, '服务重启，任务中断'),
                updated_at = ?
            WHERE status = 'running'
            """,
            (_now_iso(),),
        )
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
