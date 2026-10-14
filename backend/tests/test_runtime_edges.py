"""租约失败、取消响应与终态分页的回归边界。"""

import asyncio

import httpx
import pytest

from apps.core.config import Settings, settings_context
from apps.db.repositories.events import EventRepository
from apps.db.repositories.jobs import JobRepository, submission_hash
from apps.domain.jobs import JobOutcome
from apps.runtime.events import EventBroker
from apps.runtime.job_manager import JobManager
from apps.services.session_service import save_session
from apps.services.document_version_service import get_current_version


def session():
    return save_session({"requirementsSummary": {"product_name": "edge"}})["id"]


async def terminal(manager, job_id):
    async def wait():
        while manager.jobs.get(job_id)["status"] not in ("succeeded", "failed", "cancelled"):
            await asyncio.sleep(0.01)
        return manager.jobs.get(job_id)

    return await asyncio.wait_for(wait(), 2)


def test_httpx_transport_timeout_retries(isolated_database):
    class Timeout:
        calls = 0

        async def execute(self, job, emit):
            self.calls += 1
            if self.calls == 1:
                raise httpx.ReadTimeout("transport timed out")
            return JobOutcome("# recovered")

    async def run():
        settings = Settings(
            _env_file=None, database_path=isolated_database.path, job_poll_interval=0.01
        )
        with settings_context(settings):
            executor = Timeout()
            manager = JobManager(isolated_database, settings, executor)
            await manager.start()
            try:
                job_id = await manager.submit(session(), "prd", {})
                final = await terminal(manager, job_id)
                assert final["status"] == "succeeded"
                assert final["attempt_count"] == 2
            finally:
                await manager.close()

    asyncio.run(run())


def test_terminal_replay_drains_more_than_one_page(isolated_database, monkeypatch):
    repo = JobRepository(isolated_database)
    events = EventRepository(isolated_database)
    job_id = repo.create(session(), "prd", {}, None, submission_hash("prd", {}), None)
    original = events.list
    count = 0

    def race(job_id, after=0, limit=500):
        nonlocal count
        count += 1
        if count == 2:
            with isolated_database.transaction():
                for _ in range(501):
                    events.append(job_id, {"type": "text_delta", "content": "x"})
                repo.finish(job_id, "succeeded")
                events.append(job_id, {"type": "succeeded", "status": "succeeded"})
            return []
        return original(job_id, after, limit)

    monkeypatch.setattr(events, "list", race)

    async def run():
        broker = EventBroker(events, repo)
        result = "".join([frame async for frame in broker.stream(job_id)])
        assert "id: 503\n" in result
        assert "event: succeeded" in result
        assert result.count("event: text_delta") == 501
        assert result.endswith("data: [DONE]\n\n")

    asyncio.run(run())


@pytest.mark.parametrize("action", ["cancel", "close"])
def test_execution_that_swallows_first_cancel_is_drained_and_fenced(isolated_database, action):
    class IgnoreOnce:
        def __init__(self):
            self.started = asyncio.Event()
            self.swallowed = asyncio.Event()
            self.finished = False

        async def execute(self, job, emit):
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.swallowed.set()
            try:
                await asyncio.Event().wait()
            finally:
                self.finished = True
            return JobOutcome("must not commit")

    async def run():
        settings = Settings(
            _env_file=None, database_path=isolated_database.path, job_poll_interval=0.01
        )
        with settings_context(settings):
            executor = IgnoreOnce()
            manager = JobManager(isolated_database, settings, executor)
            await manager.start()
            job_id = await manager.submit(session(), "prd", {})
            await asyncio.wait_for(executor.started.wait(), 1)
            try:
                operation = manager.cancel(job_id) if action == "cancel" else manager.close()
                await asyncio.wait_for(operation, 0.7)
                assert executor.finished
                assert get_current_version(manager.jobs.get(job_id)["session_id"], "prd") is None
                expected = "cancelled" if action == "cancel" else "interrupted"
                assert manager.jobs.get(job_id)["status"] == expected
            finally:
                await manager.close()

    asyncio.run(run())


def test_heartbeat_database_error_releases_slot_and_does_not_orphan_task(
    isolated_database, monkeypatch
):
    import sqlite3

    class RetryAfterLease:
        started = None

        async def execute(self, job, emit):
            if job["attempt_count"] == 1:
                self.started.set()
                await asyncio.Event().wait()
            return JobOutcome("# second attempt")

    async def run():
        settings = Settings(
            _env_file=None,
            database_path=isolated_database.path,
            job_poll_interval=0.01,
            job_lease_seconds=0.06,
            job_max_concurrency=1,
        )
        with settings_context(settings):
            executor = RetryAfterLease()
            executor.started = asyncio.Event()
            manager = JobManager(isolated_database, settings, executor)
            renew = manager.jobs.renew
            calls = 0

            def fail_renew(*args):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise sqlite3.OperationalError("database is locked")
                return renew(*args)

            monkeypatch.setattr(manager.jobs, "renew", fail_renew)
            await manager.start()
            try:
                job_id = await manager.submit(session(), "prd", {})
                await asyncio.wait_for(executor.started.wait(), 1)
                final = await terminal(manager, job_id)
                assert final["status"] == "succeeded"
                assert final["attempt_count"] == 2
            finally:
                await manager.close()
            assert manager.active_count == 0
            assert not [
                task
                for task in asyncio.all_tasks()
                if task is not asyncio.current_task()
                and task.get_name().startswith(("job:", "lease:"))
            ]

    asyncio.run(run())


def test_real_sqlite_lock_does_not_block_event_loop_or_leave_executors(isolated_database):
    import threading
    import time

    class Restart:
        def __init__(self):
            self.started = asyncio.Event()

        async def execute(self, job, emit):
            if job["attempt_count"] == 1:
                self.started.set()
                await asyncio.Event().wait()
            return JobOutcome("# restart after contention")

    async def run():
        isolated_database.busy_timeout_ms = 40
        settings = Settings(
            _env_file=None,
            database_path=isolated_database.path,
            job_poll_interval=0.01,
            job_lease_seconds=0.09,
            job_max_concurrency=1,
        )
        with settings_context(settings):
            executor = Restart()
            manager = JobManager(isolated_database, settings, executor)
            await manager.start()
            held = threading.Event()

            def hold_lock():
                conn = isolated_database.connect()
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    held.set()
                    time.sleep(0.25)
                    conn.rollback()
                finally:
                    conn.close()

            job_id = await manager.submit(session(), "prd", {})
            await asyncio.wait_for(executor.started.wait(), 1)
            holder = threading.Thread(target=hold_lock)
            holder.start()
            await asyncio.to_thread(held.wait)
            gaps = []

            async def probe():
                for _ in range(30):
                    started = asyncio.get_running_loop().time()
                    await asyncio.sleep(0.01)
                    gaps.append(asyncio.get_running_loop().time() - started)

            try:
                probe_task = asyncio.create_task(probe())
                final = await terminal(manager, job_id)
                await probe_task
                assert final["status"] == "succeeded"
                assert final["attempt_count"] == 2
                assert max(gaps) < 0.1
            finally:
                await asyncio.to_thread(holder.join)
                await manager.close()
            assert not [
                task
                for task in asyncio.all_tasks()
                if task is not asyncio.current_task()
                and task.get_name().startswith(("job:", "lease:"))
            ]

    asyncio.run(run())


def test_shutdown_reports_timeout_and_fences_executor_until_it_cooperates(isolated_database):
    from apps.core.errors import DomainError

    class Stubborn:
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(self, job, emit):
            self.started.set()
            while not self.release.is_set():
                try:
                    await self.release.wait()
                except asyncio.CancelledError:
                    pass
            return JobOutcome("must not finalize during shutdown")

    async def run():
        settings = Settings(
            _env_file=None,
            database_path=isolated_database.path,
            job_poll_interval=0.01,
            job_shutdown_timeout=0.05,
        )
        with settings_context(settings):
            executor = Stubborn()
            manager = JobManager(isolated_database, settings, executor)
            await manager.start()
            job_id = await manager.submit(session(), "prd", {})
            await asyncio.wait_for(executor.started.wait(), 1)
            try:
                with pytest.raises(DomainError) as error:
                    await manager.close()
                assert error.value.code == "JOB_STOP_TIMEOUT"
                assert not manager.running
                assert manager.jobs.get(job_id)["status"] == "interrupted"
            finally:
                executor.release.set()
                await asyncio.sleep(0.02)
                await manager.close()
            job = manager.jobs.get(job_id)
            assert job["status"] == "interrupted"
            assert get_current_version(job["session_id"], "prd") is None

    asyncio.run(run())
