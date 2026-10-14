"""真实执行器消费生成流的契约，模型流用确定性 Service 替身提供。"""

import asyncio

from apps.core.config import Settings, settings_context
from apps.runtime.job_executor import JobExecutor
from apps.runtime.job_manager import JobManager
from apps.services.document_version_service import get_current_version, list_versions
from apps.services.session_service import save_session


class Documents:
    async def generate_prd_from_summary_stream(self, *args):
        yield {"type": "phase", "phase": "writer_started"}
        yield {"type": "text_delta", "content": "initial"}
        yield {"type": "phase", "phase": "review_started"}
        yield {"type": "review", "content": {"passed": False, "issues": []}}
        yield {"type": "phase", "phase": "rewrite_started"}
        yield {"type": "text_delta", "content": "# revised"}
        yield {
            "type": "done",
            "final_prd": "# revised",
            "review": {"passed": False, "issues": []},
            "revision_applied": True,
        }


def test_actual_executor_records_review_rewrite_summary_and_one_final_version(isolated_database):
    async def run():
        settings = Settings(
            _env_file=None, database_path=isolated_database.path, job_poll_interval=0.01
        )
        with settings_context(settings):
            manager = JobManager(isolated_database, settings, JobExecutor(Documents()))
            await manager.start()
            try:
                session_id = save_session({"requirementsSummary": {"product_name": "rewrite"}})[
                    "id"
                ]
                job_id = await manager.submit(session_id, "prd", {})

                async def wait():
                    while manager.jobs.get(job_id)["status"] not in ("succeeded", "failed"):
                        await asyncio.sleep(0.01)

                await asyncio.wait_for(wait(), 2)
                job = manager.jobs.get(job_id)
                assert job["status"] == "succeeded"
                assert job["draft_content"] == "# revised"
                assert job["previous_draft"] == "initial"
                current = get_current_version(session_id, "prd")
                assert current["content"] == "# revised"
                assert current["metadata"]["run_summary"]["revision_applied"] is True
                assert (
                    current["metadata"]["run_summary"]["injected_skills"][0]["skill_id"]
                    == "prd-generator"
                )
                assert "quality_gate" in current["metadata"]
                assert len(list_versions(session_id, "prd")["versions"]) == 1
                events = manager.event_repository.list(job_id)
                done = [event for event in events if event["event_type"] == "done"]
                assert len(done) == 1
                assert done[0]["payload"]["final_prd"] == "# revised"
                assert [event["event_type"] for event in events][-3:] == [
                    "done",
                    "run_summary",
                    "succeeded",
                ]
            finally:
                await manager.close()

    asyncio.run(run())


def test_actual_executor_sqlite_setup_does_not_block_loop(isolated_database):
    import threading
    import time
    from apps.db.repositories.jobs import JobRepository, submission_hash

    class SimpleDocuments:
        async def generate_prd_from_summary_stream(self, *args):
            yield {"type": "text_delta", "content": "# result"}
            yield {"type": "done", "final_prd": "# result"}

    async def run():
        settings = Settings(_env_file=None, database_path=isolated_database.path)
        with settings_context(settings):
            session_id = save_session({"requirementsSummary": {"product_name": "locked"}})["id"]
            repo = JobRepository(isolated_database)
            job_id = repo.create(
                session_id,
                "prd",
                {"requirements_summary": {"product_name": "locked"}},
                None,
                submission_hash("prd", {}),
                None,
            )
            job = repo.get(job_id)
            held = threading.Event()

            def hold():
                conn = isolated_database.connect()
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    held.set()
                    time.sleep(0.3)
                    conn.rollback()
                finally:
                    conn.close()

            thread = threading.Thread(target=hold)
            thread.start()
            await asyncio.to_thread(held.wait)
            gaps = []

            async def probe():
                for _ in range(35):
                    start = asyncio.get_running_loop().time()
                    await asyncio.sleep(0.01)
                    gaps.append(asyncio.get_running_loop().time() - start)

            async def emit(event):
                pass

            try:
                probe_task = asyncio.create_task(probe())
                result = await JobExecutor(SimpleDocuments()).execute(job, emit)
                await probe_task
                assert result.content == "# result"
                assert max(gaps) < 0.1
            finally:
                await asyncio.to_thread(thread.join)

    asyncio.run(run())
