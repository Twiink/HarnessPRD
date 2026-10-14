import asyncio

import pytest

from apps.core.config import Settings, settings_context
from apps.domain.jobs import JobOutcome
from apps.runtime.job_manager import JobManager
from apps.services.session_service import load_session_data_raw, save_session
from tests.test_job_runtime import wait_terminal


class ParallelTerminalExecutor:
    def __init__(self):
        self.api_started = asyncio.Event()
        self.target_started = asyncio.Event()
        self.fail_target = asyncio.Event()
        self.finish_api = asyncio.Event()

    async def execute(self, job, emit):
        if job["artifact"] == "api-docs":
            self.api_started.set()
            await self.finish_api.wait()
            return JobOutcome("# API done")
        self.target_started.set()
        await self.fail_target.wait()
        raise ValueError("target generation failed")


@pytest.mark.parametrize("artifact", ["prd", "optimize-prd"])
@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
@pytest.mark.parametrize("with_api", [True, False], ids=["api-running", "no-other-active"])
def test_terminal_job_selects_remaining_active_job(
    isolated_database, artifact, terminal_status, with_api
):
    async def run():
        settings = Settings(
            _env_file=None,
            database_path=isolated_database.path,
            job_poll_interval=0.01,
            job_max_concurrency=2,
        )
        with settings_context(settings):
            executor = ParallelTerminalExecutor()
            manager = JobManager(isolated_database, settings, executor)
            await manager.start()
            try:
                session_id = save_session(
                    {
                        "requirementsSummary": {"product_name": "parallel terminal test"},
                        "prdContent": "# baseline",
                        "prdBaselineConfirmed": True,
                    }
                )["id"]
                api_job = None
                if with_api:
                    api_job = await manager.submit(session_id, "api-docs", {})
                    await asyncio.wait_for(executor.api_started.wait(), 1)
                payload = (
                    {"instruction": "Improve the baseline"} if artifact == "optimize-prd" else {}
                )
                target_job = await manager.submit(session_id, artifact, payload)
                await asyncio.wait_for(executor.target_started.wait(), 1)
                assert load_session_data_raw(session_id)["activeJobId"] == target_job

                if terminal_status == "cancelled":
                    final = await manager.cancel(target_job)
                else:
                    executor.fail_target.set()
                    final = await wait_terminal(manager, target_job)

                assert final["status"] == terminal_status
                assert load_session_data_raw(session_id)["activeJobId"] == api_job
                terminal_events = manager.event_repository.list(target_job)
                assert terminal_events[-1]["event_type"] == terminal_status
                if api_job:
                    assert manager.jobs.get(api_job)["status"] == "running"
                    executor.finish_api.set()
                    assert (await wait_terminal(manager, api_job))["status"] == "succeeded"
                    assert load_session_data_raw(session_id)["activeJobId"] is None
            finally:
                await manager.close()

    asyncio.run(run())
