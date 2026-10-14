import sqlite3

import pytest

from apps.db.connection import Database, database_context, get_connection, transaction


def test_migrations_are_repeatable_and_preserve_existing_data(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE project_sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL, entry_mode TEXT, current_stage TEXT, status TEXT, session_data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO project_sessions VALUES ('s','old',NULL,NULL,NULL,'{}','now','now')"
        )
    database = Database(path)
    database.migrate()
    database.migrate()
    with database_context(database), get_connection() as conn:
        assert conn.execute("SELECT title FROM project_sessions").fetchone()[0] == "old"
        assert len(conn.execute("SELECT * FROM schema_migrations").fetchall()) == 2
        columns = {row[1] for row in conn.execute("PRAGMA table_info(generation_jobs)")}
        assert {"attempt_count", "lease_until", "idempotency_key", "cancel_requested"} <= columns
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_nested_writes_rollback_together(isolated_database):
    with pytest.raises(RuntimeError), transaction():
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO project_sessions VALUES ('s','old',NULL,NULL,NULL,'{}','now','now')"
            )
        with get_connection() as conn:
            conn.execute("UPDATE project_sessions SET title='new' WHERE id='s'")
        raise RuntimeError("rollback")
    with get_connection() as conn:
        assert conn.execute("SELECT * FROM project_sessions").fetchall() == []


def test_legacy_jobs_are_migrated_without_dropping_history(tmp_path):
    from apps.db.migrations import _initial

    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        _initial(conn)
        conn.execute(
            "INSERT INTO project_sessions VALUES ('s','old',NULL,NULL,NULL,'{}','now','now')"
        )
        for job_id, session_id, status in [
            ("done", "s", "completed"),
            ("live", "s", "running"),
            ("duplicate", "s", "pending"),
            ("orphan", "deleted", "pending"),
        ]:
            conn.execute(
                "INSERT INTO generation_jobs (id,session_id,artifact,status,phase,payload_json,created_at,updated_at) VALUES (?,?,'prd',?,'writing','{}',?,?)",
                (job_id, session_id, status, job_id, job_id),
            )
        conn.execute("INSERT INTO documents VALUES ('doc','s','prd','v2','now','now')")
        for version in (1, 2):
            conn.execute(
                "INSERT INTO document_versions VALUES (?, 'doc', ?, ?, 'generate','done',NULL,NULL,'now')",
                (f"v{version}", version, f"content {version}"),
            )
    database = Database(path)
    database.migrate()
    database.migrate()
    with database_context(database), get_connection() as conn:
        assert (
            conn.execute("SELECT status FROM generation_jobs WHERE id='done'").fetchone()[0]
            == "succeeded"
        )
        assert (
            conn.execute("SELECT status FROM generation_jobs WHERE id='orphan'").fetchone()[0]
            == "failed"
        )
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 2
        assert (
            conn.execute("SELECT source_job_id FROM document_versions WHERE id='v1'").fetchone()[0]
            is None
        )
        assert (
            conn.execute("SELECT source_job_id FROM document_versions WHERE id='v2'").fetchone()[0]
            == "done"
        )
        assert (
            conn.execute("SELECT COUNT(*) FROM job_events WHERE job_id='done'").fetchone()[0] == 2
        )
