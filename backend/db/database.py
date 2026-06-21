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


def init_db() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
