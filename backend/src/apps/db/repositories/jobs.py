"""任务队列仓储，冲突检查、租约和状态转换均在事务中完成。"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from apps.core.errors import DomainError
from apps.db.connection import Database
from apps.db.migrations import now_iso
from apps.db.repositories.events import EventRepository
from apps.domain.jobs import ACTIVE_STATUSES, TERMINAL_STATUSES


def lease_deadline(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def submission_hash(artifact: str, payload: dict) -> str:
    raw = json.dumps([artifact, payload], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def row_to_job(row) -> dict[str, Any]:
    job = dict(row)
    job["review"] = json.loads(job["review_json"]) if job["review_json"] else None
    job["result"] = json.loads(job["result_json"]) if job["result_json"] else None
    job["cancel_requested"] = bool(job["cancel_requested"])
    return job


class JobRepository:
    def __init__(self, database: Database):
        self.database = database
        self.events = EventRepository(database)

    def get(self, job_id: str) -> dict[str, Any]:
        with self.database.read() as conn:
            row = conn.execute("SELECT * FROM generation_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise DomainError("任务不存在", code="JOB_NOT_FOUND", status_code=404)
        return row_to_job(row)

    def replay(self, session_id: str, key: str | None, digest: str) -> str | None:
        if key is None:
            return None
        with self.database.read() as conn:
            row = conn.execute(
                "SELECT id,submission_hash FROM generation_jobs WHERE session_id=? AND idempotency_key=?",
                (session_id, key),
            ).fetchone()
        if row:
            if row["submission_hash"] != digest:
                raise DomainError(
                    "幂等键已用于不同请求", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return row["id"]
        return None

    def create(
        self,
        session_id: str,
        artifact: str,
        payload: dict,
        key: str | None,
        digest: str,
        request_id: str | None,
    ) -> str:
        with self.database.transaction() as conn:
            replay = self.replay(session_id, key, digest)
            if replay:
                return replay
            if not conn.execute(
                "SELECT id FROM project_sessions WHERE id=?", (session_id,)
            ).fetchone():
                raise DomainError("方案不存在", code="SESSION_NOT_FOUND", status_code=404)
            conflict_key = artifact.removeprefix("optimize-")
            row = conn.execute(
                "SELECT id FROM generation_jobs WHERE session_id=? AND conflict_key=? AND status IN ('pending','queued','running','interrupted')",
                (session_id, conflict_key),
            ).fetchone()
            if row:
                raise DomainError(
                    "该文档已有进行中的任务",
                    code="JOB_CONFLICT",
                    status_code=409,
                    details={"job_id": row["id"]},
                )
            job_id = str(uuid.uuid4())
            now = now_iso()
            conn.execute(
                """INSERT INTO generation_jobs
                (id,session_id,artifact,status,phase,payload_json,created_at,updated_at,
                 conflict_key,idempotency_key,submission_hash,request_id)
                VALUES (?,?,?,'queued','queued',?,?,?,?,?,?,?)""",
                (
                    job_id,
                    session_id,
                    artifact,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                    now,
                    conflict_key,
                    key,
                    digest,
                    request_id,
                ),
            )
            self.events.append(job_id, {"type": "queued", "status": "queued"})
            return job_id

    def active(self, session_id: str, artifact: str) -> dict[str, Any] | None:
        with self.database.read() as conn:
            row = conn.execute(
                "SELECT * FROM generation_jobs WHERE session_id=? AND conflict_key=? AND status IN ('pending','queued','running','interrupted') ORDER BY created_at LIMIT 1",
                (session_id, artifact.removeprefix("optimize-")),
            ).fetchone()
        return row_to_job(row) if row else None

    def claim(
        self,
        worker_id: str,
        lease_seconds: float,
        max_attempts: int,
        exclude_job_ids: tuple[str, ...] = (),
    ) -> dict[str, Any] | None:
        with self.database.read() as conn:
            if not conn.execute(
                "SELECT 1 FROM generation_jobs WHERE status IN ('pending','queued','interrupted') AND cancel_requested=0 AND attempt_count<? LIMIT 1",
                (max_attempts,),
            ).fetchone():
                return None
        with self.database.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM generation_jobs WHERE status IN ('pending','queued','interrupted') AND cancel_requested=0 AND attempt_count<? ORDER BY created_at,id",
                (max_attempts,),
            ).fetchall()
            for row in rows:
                job_id = row["id"]
                if job_id in exclude_job_ids:
                    continue
                conn.execute(
                    "UPDATE generation_jobs SET status='running',phase='starting',worker_id=?,lease_until=?,attempt_count=attempt_count+1,started_at=COALESCE(started_at,?),finished_at=NULL,error=NULL,error_code=NULL,draft_content='',previous_draft='',review_json=NULL,result_json=NULL,updated_at=? WHERE id=?",
                    (worker_id, lease_deadline(lease_seconds), now_iso(), now_iso(), job_id),
                )
                claimed = self.get(job_id)
                self.events.append(
                    job_id,
                    {
                        "type": "started",
                        "status": "running",
                        "attempt_count": claimed["attempt_count"],
                        "draft_content": "",
                    },
                )
                return claimed
        return None

    def owned(self, job_id: str, worker_id: str, attempt: int) -> bool:
        job = self.get(job_id)
        return (
            job["status"] == "running"
            and job["worker_id"] == worker_id
            and job["attempt_count"] == attempt
            and not job["cancel_requested"]
            and bool(job["lease_until"])
            and job["lease_until"] > now_iso()
        )

    def progress(self, job_id: str, worker_id: str, attempt: int, **fields) -> bool:
        allowed = {"draft_content", "previous_draft", "phase", "review_json"}
        if set(fields) - allowed:
            raise ValueError("不支持的任务进度字段")
        with self.database.transaction() as conn:
            if not self.owned(job_id, worker_id, attempt):
                return False
            fields["updated_at"] = now_iso()
            conn.execute(
                "UPDATE generation_jobs SET "
                + ",".join(f"{key}=?" for key in fields)
                + " WHERE id=?",
                (*fields.values(), job_id),
            )
            return True

    def renew(self, job_id: str, worker_id: str, attempt: int, seconds: float) -> bool:
        with self.database.transaction() as conn:
            cursor = conn.execute(
                "UPDATE generation_jobs SET lease_until=?,updated_at=? WHERE id=? AND status='running' AND worker_id=? AND attempt_count=? AND cancel_requested=0 AND lease_until>?",
                (lease_deadline(seconds), now_iso(), job_id, worker_id, attempt, now_iso()),
            )
            return cursor.rowcount == 1

    def finish(
        self,
        job_id: str,
        status: str,
        *,
        code: str | None = None,
        message: str | None = None,
        result: dict | None = None,
    ) -> bool:
        if status not in TERMINAL_STATUSES:
            raise ValueError("无效的终态")
        with self.database.transaction() as conn:
            job = self.get(job_id)
            if job["status"] in TERMINAL_STATUSES:
                return False
            conn.execute(
                """UPDATE generation_jobs SET status=?,phase=?,error_code=?,error=?,
                result_json=?,lease_until=NULL,worker_id=NULL,finished_at=?,updated_at=? WHERE id=?""",
                (
                    status,
                    "done" if status == "succeeded" else status,
                    code,
                    message,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    now_iso(),
                    now_iso(),
                    job_id,
                ),
            )
            return True

    def request_cancel(self, job_id: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            job = self.get(job_id)
            if job["status"] not in TERMINAL_STATUSES:
                conn.execute(
                    "UPDATE generation_jobs SET cancel_requested=1,updated_at=? WHERE id=?",
                    (now_iso(), job_id),
                )
            return self.get(job_id)

    def interrupt(self, job_id: str, worker_id: str, attempt: int) -> None:
        with self.database.transaction() as conn:
            job = self.get(job_id)
            if (
                job["status"] == "running"
                and job["worker_id"] == worker_id
                and job["attempt_count"] == attempt
            ):
                conn.execute(
                    "UPDATE generation_jobs SET status='interrupted',phase='interrupted',worker_id=NULL,lease_until=NULL,updated_at=? WHERE id=?",
                    (now_iso(), job_id),
                )
                self.events.append(
                    job_id, {"type": "interrupted", "status": "interrupted", "retryable": True}
                )

    def expired(self) -> list[dict[str, Any]]:
        with self.database.read() as conn:
            rows = conn.execute(
                "SELECT * FROM generation_jobs WHERE status='running' AND (lease_until IS NULL OR lease_until<=?)",
                (now_iso(),),
            ).fetchall()
        return [row_to_job(row) for row in rows]

    def requeue(self, job_id: str) -> None:
        with self.database.transaction() as conn:
            conn.execute(
                "UPDATE generation_jobs SET status='queued',phase='queued',worker_id=NULL,lease_until=NULL,updated_at=? WHERE id=? AND status='interrupted'",
                (now_iso(), job_id),
            )
            self.events.append(job_id, {"type": "queued", "status": "queued", "retryable": True})

    def counts(self) -> dict[str, int]:
        with self.database.read() as conn:
            return {
                row["status"]: row["total"]
                for row in conn.execute(
                    "SELECT status,COUNT(*) total FROM generation_jobs GROUP BY status"
                )
            }

    def unfinished(self) -> list[dict[str, Any]]:
        with self.database.read() as conn:
            rows = conn.execute(
                "SELECT * FROM generation_jobs WHERE status IN ('pending','queued','interrupted','running')"
            ).fetchall()
        return [row_to_job(row) for row in rows]
