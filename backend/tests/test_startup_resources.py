"""必需资源在 ready 前校验，运行故障返回可诊断的可重试协议。"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from apps.core.config import Settings
from apps.core.errors import DomainError
from apps.main import create_app


@pytest.mark.parametrize(
    "field", ["resources_dir", "models_config_path", "skills_root", "skills_config_path"]
)
def test_missing_resources_fail_startup_before_ready(tmp_path, field):
    settings = Settings(
        _env_file=None, database_path=tmp_path / "resource.db", **{field: tmp_path / "missing"}
    )
    app = create_app(settings)
    with pytest.raises(DomainError, match="资源") as failure:
        with TestClient(app):
            pytest.fail("invalid resources must not become ready")
    assert failure.value.code == "INVALID_RESOURCES"
    assert not getattr(getattr(app.state, "resources", None), "ready", False)


def test_interactive_stream_has_total_deadline_and_closes_source():
    import asyncio
    from apps.api.conversations import _make_sse_generator
    from apps.core.config import settings_context

    closed = []

    async def source():
        try:
            yield {"type": "chunk", "content": "draft"}
            await asyncio.Event().wait()
        finally:
            closed.append(True)

    async def run():
        with settings_context(Settings(_env_file=None, job_run_timeout=0.02)):
            return [event async for event in _make_sse_generator(source(), "test")()]

    events = asyncio.run(run())
    assert any('"code": "RUN_TIMEOUT"' in event for event in events)
    assert events[-1] == "data: [DONE]\n\n"
    assert closed == [True]


def test_missing_required_skill_file_fails_but_optional_example_is_allowed(tmp_path):
    root = tmp_path / "skills"
    skill = root / "test"
    skill.mkdir(parents=True)
    config = tmp_path / "skills.yaml"
    config.write_text(
        "bindings:\n  prd:\n    skills: [test]\n"
        + "".join(
            f"  {name}:\n    skills: []\n"
            for name in (
                "api-docs",
                "prompts",
                "optimize-prd",
                "optimize-api-docs",
                "optimize-prompts",
            )
        )
    )
    manifest = skill / "skill.yaml"
    manifest.write_text("id: test\nartifacts:\n  - path: missing.md\n    role: instructions\n")
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "test.db",
        skills_root=root,
        skills_config_path=config,
    )
    with pytest.raises(DomainError):
        with TestClient(create_app(settings)):
            pytest.fail("missing instructions must fail startup")
    manifest.write_text("id: test\nartifacts:\n  - path: missing.md\n    role: example\n")
    from apps.core.resources.skill_loader import load_skill_manifest

    load_skill_manifest.cache_clear()
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health/ready").status_code == 200


def test_missing_required_artifact_binding_fails_startup(tmp_path):
    config = tmp_path / "skills.yaml"
    config.write_text("bindings: {}\n")
    settings = Settings(
        _env_file=None, database_path=tmp_path / "empty.db", skills_config_path=config
    )
    with pytest.raises(DomainError) as failure:
        with TestClient(create_app(settings)):
            pytest.fail("all required artifact bindings must be declared")
    assert failure.value.code == "INVALID_RESOURCES"


def test_custom_prd_binding_without_schema_uses_shared_contract(tmp_path):
    from apps.core.config import settings_context
    from apps.services.generation.prompt_builders import _build_summary_sync_prompt

    root = tmp_path / "skills"
    skill = root / "custom"
    skill.mkdir(parents=True)
    (skill / "skill.yaml").write_text("id: custom\nartifacts: []\n")
    config = tmp_path / "skills.yaml"
    config.write_text("bindings:\n  prd:\n    skills: [custom]\n")
    settings = Settings(_env_file=None, skills_root=root, skills_config_path=config)
    with settings_context(settings):
        prompt = _build_summary_sync_prompt({"product_name": "demo"}, [])
    assert "product_name" in prompt
    assert "RequirementsInput" in prompt


def test_sqlite_busy_has_retryable_error_and_recovers(tmp_path):
    path = tmp_path / "locked.db"
    settings = Settings(_env_file=None, database_path=path, sqlite_busy_timeout_ms=5)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        with sqlite3.connect(path, isolation_level=None) as lock:
            lock.execute("BEGIN IMMEDIATE")
            response = client.post("/api/sessions", json={"session_data": {}})
            assert response.status_code == 503, response.text
            assert response.json()["code"] == "DB_BUSY"
            assert response.json()["retryable"] is True
            assert response.headers["Retry-After"] == "1"
            lock.rollback()
        assert client.post("/api/sessions", json={"session_data": {}}).status_code == 201
