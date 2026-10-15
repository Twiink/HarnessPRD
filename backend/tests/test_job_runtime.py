import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from apps.core.config import Settings, settings_context
from apps.core.errors import DomainError
from apps.db.repositories.jobs import JobRepository, submission_hash
from apps.db.repositories.events import EventRepository
from apps.domain.jobs import JobOutcome
from apps.runtime.job_manager import JobManager
from apps.services.sessions.state import save_session, load_session_data_raw
from apps.services.documents.versions import (
    get_current_version,
    list_versions,
    sync_from_job,
)


class CompleteExecutor:
    async def execute(self, job, emit):
        await emit({"type": "text_delta", "content": "# "})
        await emit({"type": "text_delta", "content": "测试需求"})
        return JobOutcome("# 测试需求", result={"type": "done"})


class BlockingExecutor:
    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = False

    async def execute(self, job, emit):
        await emit({"type": "text_delta", "content": "partial"})
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def session():
    return save_session(
        {"requirementsSummary": {"product_name": "测试项目", "features": [{"name": "登录"}]}}
    )["id"]


def config(database, **kwargs):
    return Settings(
        _env_file=None,
        database_path=database.path,
        job_poll_interval=0.01,
        job_lease_seconds=0.15,
        **kwargs,
    )


async def wait_terminal(manager, job_id):
    async def wait():
        while manager.jobs.get(job_id)["status"] not in ("succeeded", "failed", "cancelled"):
            await asyncio.sleep(0.01)
        return manager.jobs.get(job_id)

    return await asyncio.wait_for(wait(), 3)


def test_success_is_atomic_and_idempotent_and_events_survive_restart(isolated_database):
    async def run():
        settings = config(isolated_database)
        with settings_context(settings):
            manager = JobManager(isolated_database, settings, CompleteExecutor())
            await manager.start()
            try:
                session_id = session()
                job_id = await manager.submit(session_id, "prd", {}, "key")
                job = await wait_terminal(manager, job_id)
                assert job["status"] == "succeeded"
                assert job["attempt_count"] == 1
                assert await manager.submit(session_id, "prd", {}, "key") == job_id
                current = get_current_version(session_id, "prd")
                sync_from_job(session_id, "prd", "# 测试需求", source_job_id=job_id)
                assert len(list_versions(session_id, "prd")["versions"]) == 1
                assert get_current_version(session_id, "prd")["id"] == current["id"]
                assert load_session_data_raw(session_id)["activeJobId"] is None
                events = manager.event_repository.list(job_id)
                assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
                assert events[-1]["event_type"] == "succeeded"
                assert any(e["event_type"] == "done" for e in events)
                with pytest.raises(DomainError) as error:
                    await manager.submit(
                        session_id, "prd", {"requirements_summary": {"changed": True}}, "key"
                    )
                assert error.value.code == "IDEMPOTENCY_CONFLICT"
                resumed = "".join(
                    [frame async for frame in manager.events.stream(job_id, events[1]["sequence"])]
                )
                assert "id: 1\n" not in resumed
                assert "data: [DONE]" in resumed
                assert "event: succeeded" in resumed
                assert manager.events._subscribers == {}
                assert EventRepository(isolated_database).list(job_id) == events
            finally:
                await manager.close()

    asyncio.run(run())


def test_shutdown_interrupts_and_next_manager_recovers(isolated_database):
    async def run():
        settings = config(isolated_database)
        with settings_context(settings):
            blocked = BlockingExecutor()
            first = JobManager(isolated_database, settings, blocked)
            await first.start()
            job_id = await first.submit(session(), "prd", {})
            await asyncio.wait_for(blocked.started.wait(), 1)
            await first.close()
            assert blocked.cancelled
            assert first.active_count == 0
            assert first.jobs.get(job_id)["status"] == "interrupted"
            second = JobManager(isolated_database, settings, CompleteExecutor())
            await second.start()
            try:
                final = await wait_terminal(second, job_id)
                assert final["status"] == "succeeded"
                assert final["attempt_count"] == 2
                assert len(list_versions(final["session_id"], "prd")["versions"]) == 1
            finally:
                await second.close()

    asyncio.run(run())


def test_cancel_prevents_document_write_and_heartbeat_renews(isolated_database):
    async def run():
        settings = config(isolated_database)
        with settings_context(settings):
            blocked = BlockingExecutor()
            manager = JobManager(isolated_database, settings, blocked)
            await manager.start()
            try:
                session_id = session()
                job_id = await manager.submit(session_id, "prd", {})
                await asyncio.wait_for(blocked.started.wait(), 1)
                first_lease = manager.jobs.get(job_id)["lease_until"]
                await asyncio.sleep(0.18)
                running = manager.jobs.get(job_id)
                assert running["attempt_count"] == 1
                assert running["lease_until"] > first_lease
                cancelled = await manager.cancel(job_id)
                assert cancelled["status"] == "cancelled"
                assert blocked.cancelled
                assert get_current_version(session_id, "prd") is None
                assert load_session_data_raw(session_id)["activeJobId"] is None
                assert await manager.cancel(job_id) == cancelled
                assert manager.event_repository.list(job_id)[-1]["event_type"] == "cancelled"
            finally:
                await manager.close()

    asyncio.run(run())


def test_concurrent_submissions_are_serialized_and_idempotent(isolated_database):
    session_id = session()
    repo = JobRepository(isolated_database)

    def submit(key):
        try:
            return repo.create(
                session_id,
                "prd",
                {"requirements_summary": {}},
                key,
                submission_hash("prd", {}),
                None,
            )
        except DomainError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, ["same"] * 4))
    assert len(set(results)) == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        conflicts = list(pool.map(submit, ["other1", "other2"]))
    assert conflicts == ["JOB_CONFLICT", "JOB_CONFLICT"]


def test_failed_finalization_rolls_back_document_and_done_event(isolated_database, monkeypatch):
    from apps.runtime import job_manager as module

    def fail_session(*args, **kwargs):
        raise RuntimeError("session mirror failed")

    monkeypatch.setattr(module, "sync_session_on_job_complete", fail_session)

    async def run():
        settings = config(isolated_database)
        with settings_context(settings):
            manager = JobManager(isolated_database, settings, CompleteExecutor())
            await manager.start()
            try:
                session_id = session()
                job_id = await manager.submit(session_id, "prd", {})
                final = await wait_terminal(manager, job_id)
                assert final["status"] == "failed"
                assert get_current_version(session_id, "prd") is None
                assert not any(
                    e["event_type"] == "done" for e in manager.event_repository.list(job_id)
                )
            finally:
                await manager.close()

    asyncio.run(run())


def test_expired_lease_recovers_but_valid_lease_is_not_stolen(isolated_database):
    from apps.db.connection import get_connection

    async def run():
        settings = config(isolated_database)
        with settings_context(settings):
            session_id = session()
            repo = JobRepository(isolated_database)
            job_id = repo.create(
                session_id,
                "prd",
                {"requirements_summary": {"product_name": "x"}},
                None,
                submission_hash("prd", {}),
                None,
            )
            claimed = repo.claim("dead-worker", 100, 3)
            manager = JobManager(isolated_database, settings, CompleteExecutor())
            await manager.start()
            try:
                await asyncio.sleep(0.04)
                assert repo.get(job_id)["worker_id"] == "dead-worker"
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE generation_jobs SET lease_until='2000-01-01' WHERE id=?", (job_id,)
                    )
                final = await wait_terminal(manager, job_id)
                assert final["status"] == "succeeded"
                assert final["attempt_count"] == 2
                assert not repo.progress(
                    job_id, "dead-worker", claimed["attempt_count"], draft_content="stale write"
                )
                assert "interrupted" in [
                    event["event_type"] for event in manager.event_repository.list(job_id)
                ]
            finally:
                await manager.close()

    asyncio.run(run())


def test_exhausted_interrupted_job_fails_with_terminal_events(isolated_database):
    async def run():
        settings = config(isolated_database, job_max_attempts=1)
        with settings_context(settings):
            blocked = BlockingExecutor()
            first = JobManager(isolated_database, settings, blocked)
            await first.start()
            session_id = session()
            job_id = await first.submit(session_id, "prd", {})
            await asyncio.wait_for(blocked.started.wait(), 1)
            await first.close()
            second = JobManager(isolated_database, settings, CompleteExecutor())
            await second.start()
            try:
                final = await wait_terminal(second, job_id)
                assert final["status"] == "failed"
                assert final["error_code"] == "ATTEMPTS_EXHAUSTED"
                assert second.event_repository.list(job_id)[-1]["event_type"] == "failed"
                assert load_session_data_raw(session_id)["activeJobId"] is None
            finally:
                await second.close()

    asyncio.run(run())


def test_stream_receives_event_written_during_replay_without_duplicate(isolated_database):
    from apps.runtime.events import EventBroker

    async def run():
        repo = JobRepository(isolated_database)
        events = EventRepository(isolated_database)
        broker = EventBroker(events, repo)
        job_id = repo.create(
            session(), "prd", {"requirements_summary": {}}, None, submission_hash("prd", {}), None
        )
        stream = broker.stream(job_id)
        first = await anext(stream)
        assert "id: 1" in first
        with isolated_database.transaction():
            events.append(job_id, {"type": "text_delta", "content": "tail"})
            repo.finish(job_id, "succeeded", result={"content": "tail"})
            events.append(job_id, {"type": "succeeded", "status": "succeeded"})
        broker.notify(job_id)
        rest = "".join([frame async for frame in stream])
        assert rest.count("id: 2\n") == 1
        assert rest.count("id: 3\n") == 1
        assert "data: [DONE]" in rest
        assert broker._subscribers == {}

    asyncio.run(run())


def test_retryable_failure_is_bounded_and_final_write_happens_once(isolated_database):
    class RetryExecutor:
        calls = 0

        async def execute(self, job, emit):
            self.calls += 1
            await emit({"type": "text_delta", "content": "draft"})
            if self.calls == 1:
                raise DomainError(
                    "upstream unavailable", code="UPSTREAM_UNAVAILABLE", retryable=True
                )
            return JobOutcome("# recovered")

    async def run():
        settings = config(isolated_database)
        with settings_context(settings):
            executor = RetryExecutor()
            manager = JobManager(isolated_database, settings, executor)
            await manager.start()
            try:
                session_id = session()
                job_id = await manager.submit(session_id, "prd", {})
                final = await wait_terminal(manager, job_id)
                assert final["status"] == "succeeded"
                assert final["attempt_count"] == 2
                assert executor.calls == 2
                assert len(list_versions(session_id, "prd")["versions"]) == 1
                assert "retrying" in [
                    event["event_type"] for event in manager.event_repository.list(job_id)
                ]
            finally:
                await manager.close()

    asyncio.run(run())


def test_executor_ignoring_cancel_cannot_finalize(isolated_database):
    class IgnoresCancel(BlockingExecutor):
        async def execute(self, job, emit):
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return JobOutcome("must not be stored")

    async def run():
        settings = config(isolated_database)
        with settings_context(settings):
            executor = IgnoresCancel()
            manager = JobManager(isolated_database, settings, executor)
            await manager.start()
            try:
                session_id = session()
                job_id = await manager.submit(session_id, "prd", {})
                await asyncio.wait_for(executor.started.wait(), 1)
                result = await manager.cancel(job_id)
                assert result["status"] == "cancelled"
                assert get_current_version(session_id, "prd") is None
                assert not any(
                    e["event_type"] == "done" for e in manager.event_repository.list(job_id)
                )
            finally:
                await manager.close()

    asyncio.run(run())


def test_loading_active_session_does_not_materialize_cancelled_draft(isolated_database):
    from apps.services.sessions.state import get_session

    async def run():
        settings = config(isolated_database)
        with settings_context(settings):
            executor = BlockingExecutor()
            manager = JobManager(isolated_database, settings, executor)
            await manager.start()
            try:
                session_id = session()
                job_id = await manager.submit(session_id, "prd", {})
                await asyncio.wait_for(executor.started.wait(), 1)
                loaded = get_session(session_id)
                assert loaded["session_data"]["prdContent"] == "partial"
                assert get_current_version(session_id, "prd") is None
                await manager.cancel(job_id)
                assert get_current_version(session_id, "prd") is None
            finally:
                await manager.close()

    asyncio.run(run())


def test_parallel_artifacts_preserve_other_active_job(isolated_database):
    class ParallelExecutor:
        def __init__(self):
            self.api_started = asyncio.Event()
            self.finish_api = asyncio.Event()

        async def execute(self, job, emit):
            if job["artifact"] == "api-docs":
                self.api_started.set()
                await emit({"type": "text_delta", "content": "partial API"})
                await self.finish_api.wait()
                return JobOutcome("# API done")
            await self.api_started.wait()
            return JobOutcome("# Prompts done")

    async def run():
        settings = config(isolated_database)
        with settings_context(settings):
            executor = ParallelExecutor()
            manager = JobManager(isolated_database, settings, executor)
            await manager.start()
            try:
                session_id = save_session({"prdContent": "# baseline"})["id"]
                baseline = get_current_version(session_id, "prd")
                save_session(
                    {
                        "prdBaselineConfirmed": True,
                        "prdBaselineVersionId": baseline["id"],
                        "prdBaselineVersionNo": baseline["version_no"],
                        "prdBaselineContentHash": baseline["metadata"]["content_hash"][:16],
                    },
                    session_id,
                )
                api_job = await manager.submit(session_id, "api-docs", {})
                await asyncio.wait_for(executor.api_started.wait(), 1)
                prompts_job = await manager.submit(session_id, "prompts", {})
                assert (await wait_terminal(manager, prompts_job))["status"] == "succeeded"
                assert load_session_data_raw(session_id)["activeJobId"] == api_job
                assert get_current_version(session_id, "api-docs") is None
                executor.finish_api.set()
                assert (await wait_terminal(manager, api_job))["status"] == "succeeded"
                assert get_current_version(session_id, "prompts")["content"] == "# Prompts done"
                assert load_session_data_raw(session_id)["activeJobId"] is None
            finally:
                await manager.close()

    asyncio.run(run())
