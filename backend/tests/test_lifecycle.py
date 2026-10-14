import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from apps.core.config import Settings
from apps.main import create_app


def test_import_does_not_create_database_or_read_config(tmp_path):
    database = tmp_path / "not-created.db"
    result = subprocess.run(
        [sys.executable, "-c", "import apps.main"],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
            "DATABASE_PATH": str(database),
            "PORT": "not-an-integer",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not database.exists()


def test_resources_are_created_at_startup_and_closed_at_shutdown(tmp_path):
    path = tmp_path / "db.sqlite"
    app = create_app(Settings(_env_file=None, database_path=path))
    assert not path.exists()
    assert not hasattr(app.state, "resources")
    with TestClient(app) as client:
        resources = app.state.resources
        assert resources.ready
        assert client.get("/api/health/live").status_code == 200
        assert client.get("/api/health/ready").json() == {"status": "ready"}
        assert client.get("/api/metrics").json()["active_tasks"] == 0
    assert not resources.ready
    assert not resources.job_manager.running
    assert resources.job_manager.active_count == 0


def test_two_apps_isolate_database_and_settings(tmp_path):
    a = create_app(
        Settings(_env_file=None, database_path=tmp_path / "a.db", default_llm_model="first")
    )
    b = create_app(
        Settings(_env_file=None, database_path=tmp_path / "b.db", default_llm_model="second")
    )
    with TestClient(a) as first, TestClient(b) as second:
        response = first.post(
            "/api/sessions", json={"session_data": {"formData": {"product_name": "one"}}}
        )
        assert response.status_code in (200, 201)
        assert len(first.get("/api/sessions").json()["items"]) == 1
        assert second.get("/api/sessions").json()["items"] == []
        assert first.get("/api/config/current").json()["default_llm_model"] == "first"
        assert second.get("/api/config/current").json()["default_llm_model"] == "second"
