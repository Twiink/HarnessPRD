"""持久化事件日志，序号在任务事务内分配。"""

import json
from typing import Any

from apps.db.connection import Database
from apps.db.migrations import now_iso


class EventRepository:
    def __init__(self, database: Database):
        self.database = database

    def append(self, job_id: str, event: dict[str, Any]) -> dict[str, Any]:
        with self.database.transaction() as conn:
            sequence = conn.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM job_events WHERE job_id=?", (job_id,)
            ).fetchone()[0]
            created_at = now_iso()
            event_type = event["type"]
            conn.execute(
                "INSERT INTO job_events VALUES (?,?,?,?,?)",
                (job_id, sequence, event_type, json.dumps(event, ensure_ascii=False), created_at),
            )
        return {
            "job_id": job_id,
            "sequence": sequence,
            "event_type": event_type,
            "payload": event,
            "created_at": created_at,
        }

    def list(self, job_id: str, after: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        with self.database.read() as conn:
            rows = conn.execute(
                "SELECT * FROM job_events WHERE job_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                (job_id, after, limit),
            ).fetchall()
        return [
            {
                "job_id": row["job_id"],
                "sequence": row["sequence"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def latest_sequence(self, job_id: str) -> int:
        with self.database.read() as conn:
            return conn.execute(
                "SELECT COALESCE(MAX(sequence),0) FROM job_events WHERE job_id=?", (job_id,)
            ).fetchone()[0]
