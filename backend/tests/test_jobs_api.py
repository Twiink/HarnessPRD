import time

from fastapi.testclient import TestClient

from apps.core.config import Settings
from apps.domain.jobs import JobOutcome
from apps.main import create_app


class FakeExecutor:
    async def execute(self, job, emit):
        await emit({"type": "text_delta", "content": "# 测试 PRD"})
        return JobOutcome("# 测试 PRD", result={"final_prd": "# 测试 PRD"})


def test_job_http_events_and_sse_reconnect(tmp_path):
    app = create_app(
        Settings(_env_file=None, database_path=tmp_path / "db", job_poll_interval=0.01),
        FakeExecutor(),
    )
    with TestClient(app) as client:
        session = client.post(
            "/api/sessions",
            json={
                "session_data": {
                    "requirementsSummary": {"product_name": "测试", "features": [{"name": "登录"}]}
                }
            },
        ).json()
        body = {"session_id": session["id"], "artifact": "prd", "payload": {}}
        created = client.post(
            "/api/jobs",
            json=body,
            headers={"Idempotency-Key": "once", "X-Request-ID": "trace-test"},
        )
        assert created.status_code == 202
        assert created.headers["X-Request-ID"] == "trace-test"
        job_id = created.json()["job_id"]
        assert (
            client.post("/api/jobs", json=body, headers={"Idempotency-Key": "once"}).json()[
                "job_id"
            ]
            == job_id
        )
        for _ in range(100):
            response = client.get(f"/api/jobs/{job_id}")
            if response.json()["status"] == "succeeded":
                break
            time.sleep(0.01)
        assert response.json()["status"] == "succeeded"
        assert "payload_json" not in response.json()
        assert "worker_id" not in response.json()
        events = client.get(f"/api/jobs/{job_id}/events", params={"limit": 2}).json()
        assert len(events["items"]) == 2
        cursor = events["next_after"]
        rest = client.get(f"/api/jobs/{job_id}/events", params={"after": cursor}).json()
        assert rest["items"][0]["sequence"] > cursor
        stream = client.get(f"/api/jobs/{job_id}/stream", headers={"Last-Event-ID": str(cursor)})
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert f"id: {cursor}\n" not in stream.text
        assert "event: succeeded" in stream.text
        assert stream.text.endswith("data: [DONE]\n\n")
        assert (
            client.get(f"/api/jobs/{job_id}/stream", headers={"Last-Event-ID": "-1"}).status_code
            == 422
        )
        assert client.get(f"/api/jobs/{job_id}/events?after=-1").status_code == 422
        assert client.post(f"/api/jobs/{job_id}/cancel").json()["status"] == "succeeded"
        assert (
            len(
                client.get(f"/api/sessions/{session['id']}/documents/prd/versions").json()[
                    "versions"
                ]
            )
            == 1
        )
        invalid = client.post(
            "/api/jobs", json={**body, "artifact": "unknown", "api_key": "secret-value"}
        )
        assert invalid.status_code == 422
        assert set(("code", "message", "request_id", "retryable")) <= invalid.json().keys()
        assert "secret-value" not in invalid.text
