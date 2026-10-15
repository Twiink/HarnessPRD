"""Attempt boundaries reset drafts through the existing browser snapshot protocol."""

import asyncio
import json

import pytest

from apps.core.config import Settings, settings_context
from apps.core.errors import DomainError
from apps.db.repositories.jobs import JobRepository, submission_hash
from apps.runtime.job_manager import JobManager
from apps.services.sessions.state import save_session


@pytest.mark.parametrize("resume", [False, True], ids=["same-connection", "cursor-replay"])
def test_retry_stream_resets_previous_attempt_before_final_failure(isolated_database, resume):
    class RetryThenFail:
        async def execute(self, job, emit):
            await emit({"type": "text_delta", "content": f"attempt-{job['attempt_count']}-draft"})
            raise DomainError("generation failed", retryable=job["attempt_count"] == 1)

    async def run():
        settings = Settings(
            _env_file=None,
            database_path=isolated_database.path,
            job_poll_interval=0.005,
            job_max_attempts=2,
        )
        with settings_context(settings):
            manager = JobManager(isolated_database, settings, RetryThenFail())
            await manager.start()
            try:
                sid = save_session({"requirementsSummary": {"product_name": "retry stream"}})["id"]
                job_id = await manager.submit(sid, "prd", {})
                if resume:

                    async def first_attempt_persisted():
                        while True:
                            events = manager.event_repository.list(job_id)
                            first_delta = next(
                                (e for e in events if e["event_type"] == "text_delta"), None
                            )
                            if first_delta:
                                return first_delta
                            await asyncio.sleep(0.005)

                    first_delta = await asyncio.wait_for(first_attempt_persisted(), timeout=2)
                    after = first_delta["sequence"]
                    draft = first_delta["payload"]["content"]
                else:
                    after, draft = 0, ""
                snapshots, seen_sequences = [], []

                async def consume():
                    nonlocal draft
                    async for frame in manager.events.stream(job_id, after):
                        for line in frame.splitlines():
                            if not line.startswith("data: {"):
                                continue
                            event = json.loads(line[6:])
                            seen_sequences.append(event["sequence"])
                            # These are the public onSnapshot/onChunk behaviors used by jobStream.ts.
                            if event["type"] == "snapshot":
                                snapshots.append(event)
                                draft = event["draft_content"] or ""
                            elif event["type"] in ("text_delta", "chunk"):
                                draft += event["content"]

                await asyncio.wait_for(consume(), timeout=3)
                final = manager.jobs.get(job_id)
                assert final["status"] == "failed"
                assert final["attempt_count"] == 2
                assert draft == final["draft_content"] == "attempt-2-draft"
                assert seen_sequences == list(range(after + 1, seen_sequences[-1] + 1))
                assert snapshots
                for snapshot in snapshots:
                    assert snapshot["status"] == "running"
                    assert snapshot["artifact"] == "prd"
                    assert snapshot["phase"] == "generating"
                    assert snapshot["draft_content"] == ""
                    assert snapshot["review"] is None
                events = manager.event_repository.list(job_id)
                for index, event in enumerate(events):
                    if event["event_type"] == "started":
                        assert events[index + 1]["event_type"] == "snapshot"
                        assert (
                            events[index + 1]["payload"]["attempt_count"]
                            == event["payload"]["attempt_count"]
                        )
            finally:
                await manager.close()

    asyncio.run(run())


def test_attempt_snapshot_and_claim_commit_atomically(isolated_database, monkeypatch):
    sid = save_session({})["id"]
    repository = JobRepository(isolated_database)
    job_id = repository.create(sid, "prd", {}, None, submission_hash("prd", {}), None)
    original = repository.events.append

    def fail_snapshot(job_id, event):
        if event["type"] == "snapshot":
            raise RuntimeError("snapshot persistence failed")
        return original(job_id, event)

    monkeypatch.setattr(repository.events, "append", fail_snapshot)
    with pytest.raises(RuntimeError, match="snapshot persistence failed"):
        repository.claim("worker", 30, 2)
    job = repository.get(job_id)
    assert job["status"] == "queued"
    assert job["attempt_count"] == 0
    assert [event["event_type"] for event in repository.events.list(job_id)] == ["queued"]
