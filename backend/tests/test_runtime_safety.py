"""Bounded jobs, persistent timeout fencing and batched streaming regressions."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from apps.core.config import Settings, settings_context
from apps.core.errors import DomainError
from apps.db.connection import database_context
from apps.db.repositories.jobs import JobRepository, submission_hash
from apps.domain.jobs import JobOutcome, LeaseLostError
from apps.runtime.job_manager import JobManager, prepare_payload
from apps.services.documents.versions import get_current_version
from apps.services.sessions.state import save_session


def session(name="safety"):
    return save_session({"requirementsSummary": {"product_name": name}})["id"]


async def until(predicate, timeout=3):
    async def wait():
        while not predicate():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(wait(), timeout)


def settings_for(database, **kwargs):
    return Settings(
        _env_file=None,
        database_path=database.path,
        job_poll_interval=0.005,
        **kwargs,
    )


def test_timeout_fences_before_cancellation_preserves_draft_and_bounds_retries(isolated_database):
    class Hangs:
        def __init__(self):
            self.cancelled_states = []

        async def execute(self, job, emit):
            if job["session_id"] == second_session:
                return JobOutcome("# next job")
            await emit({"type": "text_delta", "content": "partial"})
            await emit({"type": "text_delta", "content": " draft"})
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                current = manager.jobs.get(job["id"])
                self.cancelled_states.append((current["status"], current["worker_id"]))
                raise

    async def run():
        nonlocal manager, second_session
        config = settings_for(
            isolated_database, job_run_timeout=0.06, job_max_attempts=2, job_max_concurrency=1
        )
        with settings_context(config):
            executor = Hangs()
            manager = JobManager(isolated_database, config, executor)
            first_session, second_session = session(), session("next")
            await manager.start()
            try:
                first = await manager.submit(first_session, "prd", {})
                second = await manager.submit(second_session, "prd", {})
                await until(lambda: manager.jobs.get(first)["status"] == "failed")
                await until(lambda: manager.jobs.get(second)["status"] == "succeeded")
                failed = manager.jobs.get(first)
                assert failed["error_code"] == "JOB_RUN_TIMEOUT"
                assert failed["draft_content"] == "partial draft"
                assert failed["attempt_count"] == 2
                assert len(executor.cancelled_states) == 2
                assert all(
                    status != "running" and owner is None
                    for status, owner in executor.cancelled_states
                )
                assert get_current_version(first_session, "prd") is None
            finally:
                await manager.close()

    manager = second_session = None
    asyncio.run(run())


def test_timeout_keeps_stubborn_executor_in_slot_and_rejects_late_output(isolated_database):
    class Stubborn:
        def __init__(self):
            self.release = asyncio.Event()
            self.cancelled = asyncio.Event()
            self.late_rejected = False

        async def execute(self, job, emit):
            if job["session_id"] == next_session:
                return JobOutcome("# next")
            await emit({"type": "text_delta", "content": "safe draft"})
            while not self.release.is_set():
                try:
                    await self.release.wait()
                except asyncio.CancelledError:
                    self.cancelled.set()
            try:
                await emit({"type": "text_delta", "content": "late"})
            except LeaseLostError:
                self.late_rejected = True
            return JobOutcome("must not commit")

    async def run():
        nonlocal next_session
        config = settings_for(
            isolated_database, job_run_timeout=0.04, job_max_attempts=1, job_max_concurrency=1
        )
        with settings_context(config):
            executor = Stubborn()
            manager = JobManager(isolated_database, config, executor)
            await manager.start()
            try:
                first_session, next_session = session(), session("next")
                first = await manager.submit(first_session, "prd", {})
                second = await manager.submit(next_session, "prd", {})
                await asyncio.wait_for(executor.cancelled.wait(), 1)
                await asyncio.sleep(0.06)
                assert manager.jobs.get(first)["status"] == "failed"
                assert manager.jobs.get(second)["status"] == "queued"
                assert manager.active_count == 1
                assert first in manager.health["timed_out_tasks"]
                executor.release.set()
                await until(lambda: manager.jobs.get(second)["status"] == "succeeded")
                assert executor.late_rejected
                assert manager.jobs.get(first)["draft_content"] == "safe draft"
                assert get_current_version(first_session, "prd") is None
            finally:
                executor.release.set()
                await manager.close()

    next_session = None
    asyncio.run(run())


def test_queue_capacity_is_atomic_and_idempotent_replay_uses_no_slot(isolated_database):
    repo = JobRepository(isolated_database)
    sessions = [session(str(index)) for index in range(4)]

    def submit(sid):
        with database_context(isolated_database):
            try:
                return repo.create(
                    sid, "prd", {}, "key", submission_hash("prd", {}), None, max_queued=1
                )
            except DomainError as error:
                assert error.status_code == 503
                assert error.retryable
                return error.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, sessions))
    assert results.count("QUEUE_FULL") == 3
    successful = next(index for index, result in enumerate(results) if result != "QUEUE_FULL")
    assert submit(sessions[successful]) == results[successful]
    repo.finish(results[successful], "cancelled")
    assert submit(sessions[(successful + 1) % 4]) != "QUEUE_FULL"


def test_claim_skips_excluded_jobs_and_recovery_reads_bounded_batches(isolated_database):
    repo = JobRepository(isolated_database)
    job_ids = [
        repo.create(session(str(index)), "prd", {}, None, str(index), None) for index in range(8)
    ]
    claimed = repo.claim("worker", 30, 3, tuple(job_ids[:6]))
    assert claimed["id"] == job_ids[6]
    with isolated_database.transaction() as conn:
        conn.execute("UPDATE generation_jobs SET attempt_count=3 WHERE status='queued'")
    first = repo.recoverable(3, limit=2)
    assert len(first) == 2
    for job in first:
        repo.finish(job["id"], "failed")
    second = repo.recoverable(3, limit=2)
    assert len(second) == 2
    assert not ({job["id"] for job in first} & {job["id"] for job in second})
    with isolated_database.transaction() as conn:
        conn.execute(
            "UPDATE generation_jobs SET status='running',lease_until=NULL WHERE status='queued'"
        )
    assert len(repo.expired(limit=2)) == 2


def test_job_summary_validates_known_nested_fields_and_preserves_extensions():
    with pytest.raises(DomainError) as error:
        prepare_payload({}, "prd", {"requirements_summary": {"features": [{"name": 42}]}})
    assert error.value.code == "INVALID_JOB_PAYLOAD"
    assert error.value.status_code == 422
    result = prepare_payload(
        {}, "prd", {"requirements_summary": {"product_name": "safe", "custom": {"enabled": True}}}
    )
    assert result["requirements_summary"]["custom"] == {"enabled": True}


def test_progress_batches_bound_writes_and_keep_replay_order(isolated_database, monkeypatch):
    updates = []
    connect = isolated_database.connect

    def traced_connect():
        conn = connect()
        conn.set_trace_callback(
            lambda sql: (
                updates.append(sql)
                if sql.startswith("UPDATE generation_jobs SET draft_content=")
                else None
            )
        )
        return conn

    monkeypatch.setattr(isolated_database, "connect", traced_connect)

    class Chunks:
        async def execute(self, job, emit):
            for _ in range(1000):
                await emit({"type": "text_delta", "content": "x" * 64})
            await emit({"type": "phase", "phase": "review_started"})
            return JobOutcome("x" * 64000)

    async def run():
        config = settings_for(isolated_database)
        with settings_context(config):
            manager = JobManager(isolated_database, config, Chunks())
            await manager.start()
            try:
                job_id = await manager.submit(session(), "prd", {})
                await until(lambda: manager.jobs.get(job_id)["status"] == "succeeded")
                events = manager.event_repository.list(job_id)
                deltas = [event for event in events if event["event_type"] == "text_delta"]
                assert "".join(event["payload"]["content"] for event in deltas) == "x" * 64000
                assert len(updates) < 25
                assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
                assert events[-3]["event_type"] == "phase"
                replay = "".join(
                    [frame async for frame in manager.events.stream(job_id, deltas[-1]["sequence"])]
                )
                assert "event: phase" in replay and "event: succeeded" in replay
            finally:
                await manager.close()
            assert not [
                task
                for task in asyncio.all_tasks()
                if task is not asyncio.current_task()
                and task.get_name().startswith(("job:", "lease:", "progress:", "timeout:"))
            ]

    asyncio.run(run())


def test_small_pending_progress_flushes_on_interval(isolated_database):
    class Pauses:
        def __init__(self):
            self.emitted = asyncio.Event()

        async def execute(self, job, emit):
            await emit({"type": "text_delta", "content": "first"})
            await emit({"type": "text_delta", "content": " second"})
            self.emitted.set()
            await asyncio.Event().wait()

    async def run():
        config = settings_for(isolated_database, job_progress_flush_interval=0.02)
        with settings_context(config):
            executor = Pauses()
            manager = JobManager(isolated_database, config, executor)
            await manager.start()
            try:
                job_id = await manager.submit(session(), "prd", {})
                await asyncio.wait_for(executor.emitted.wait(), 1)
                await until(lambda: manager.jobs.get(job_id)["draft_content"] == "first second")
            finally:
                await manager.close()

    asyncio.run(run())


def test_persistent_scheduler_failure_degrades_health_and_recovers(
    isolated_database, monkeypatch, caplog
):
    class Unused:
        async def execute(self, job, emit):
            return JobOutcome("unused")

    async def run():
        config = settings_for(isolated_database, job_health_failure_seconds=0.03)
        manager = JobManager(isolated_database, config, Unused())
        await manager.start()
        original = manager._recover

        def fail():
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(manager, "_recover", fail)
        try:
            await until(lambda: not manager.healthy)
            assert manager.running
            assert manager.health["last_error_type"] == "OperationalError"
            assert manager.health["consecutive_failures"] > 1
            monkeypatch.setattr(manager, "_recover", original)
            await until(lambda: manager.healthy)
            assert manager.health["consecutive_failures"] == 0
            assert any(record.exc_info or record.exc_text for record in caplog.records)
        finally:
            await manager.close()

    asyncio.run(run())
