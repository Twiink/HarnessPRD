"""真实进程退出后，下一应用恢复 SQLite 中的租约与事件。"""

import os
import subprocess
import sys
from pathlib import Path
import time

from fastapi.testclient import TestClient

from apps.core.config import Settings
from apps.domain.jobs import JobOutcome
from apps.main import create_app

CHILD = """
import asyncio, os, sys, time
from fastapi.testclient import TestClient
from apps.core.config import Settings
from apps.main import create_app
class Blocked:
    async def execute(self, job, emit):
        await emit({'type':'text_delta','content':'partial'})
        await asyncio.Event().wait()
app=create_app(Settings(_env_file=None,database_path=sys.argv[1],job_poll_interval=.01,job_lease_seconds=.3),Blocked())
with TestClient(app) as client:
    session=client.post('/api/sessions',json={'session_data':{'requirementsSummary':{'product_name':'process recovery'}}}).json()
    created=client.post('/api/jobs',json={'session_id':session['id'],'artifact':'prd','payload':{}}).json()
    job_id=created['job_id']
    for _ in range(100):
        job=client.get('/api/jobs/'+job_id).json()
        if job['status']=='running' and job['draft_content']=='partial':
            print(job_id,flush=True)
            os._exit(0)
        time.sleep(.01)
raise RuntimeError('job did not start')
"""


class Recovered:
    async def execute(self, job, emit):
        await emit({"type": "text_delta", "content": "# Recovered"})
        return JobOutcome("# Recovered")


def test_abrupt_process_exit_recovers_without_lost_events_or_duplicate_versions(tmp_path):
    path = tmp_path / "process.db"
    process = subprocess.run(
        [sys.executable, "-c", CHILD, str(path)],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert process.returncode == 0, process.stderr
    job_id = process.stdout.strip()
    assert job_id
    app = create_app(
        Settings(_env_file=None, database_path=path, job_poll_interval=0.01, job_lease_seconds=0.3),
        Recovered(),
    )
    with TestClient(app) as client:
        for _ in range(200):
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] == "succeeded":
                break
            time.sleep(0.01)
        assert job["status"] == "succeeded"
        assert job["attempt_count"] == 2
        events = client.get(f"/api/jobs/{job_id}/events").json()["items"]
        assert any(event["payload"].get("content") == "partial" for event in events)
        assert events[-1]["event_type"] == "succeeded"
        assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
        history = client.get(f"/api/sessions/{job['session_id']}/documents/prd/versions").json()
        assert len(history["versions"]) == 1
