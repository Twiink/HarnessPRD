"""验证配置生命周期、凭证脱敏与应用之间的路径隔离。"""

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from apps.core import config


def test_import_does_not_construct_settings_or_mutate_environment():
    script = """
import os
from pydantic_settings import BaseSettings
def forbidden(*args, **kwargs):
    raise AssertionError('Settings constructed at import')
BaseSettings.__init__ = forbidden
before = dict(os.environ)
import apps.core.config
assert dict(os.environ) == before
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")}
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_settings_are_strict_frozen_and_secrets_are_masked():
    value = config.Settings(_env_file=None, openai_api_key="private-test-key")
    assert isinstance(value.openai_api_key, SecretStr)
    assert "private-test-key" not in repr(value)
    assert "private-test-key" not in value.model_dump_json()
    with pytest.raises(ValidationError):
        config.Settings(_env_file=None, unexpected_option=True)
    with pytest.raises(ValidationError):
        value.host = "0.0.0.0"


def test_backend_defaults_and_injected_paths(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    value = config.Settings(_env_file=None)
    assert config.BACKEND_DIR == backend
    assert value.host == "127.0.0.1"
    assert value.database_path == backend / "data" / "sessions.db"
    assert value.sqlite_busy_timeout_ms == 5000
    assert value.job_poll_interval == 0.1
    assert value.job_lease_seconds == 30
    assert value.job_max_attempts == 3
    assert value.job_max_concurrency == 2
    assert value.resources_dir == backend / "resources"
    assert value.skills_root == backend.parent / "skills"
    assert value.skills_config_path == backend.parent / "config" / "skills.yaml"
    assert value.models_config_path == backend / "config" / "models.yaml"
    injected = config.Settings(_env_file=None, resources_dir=tmp_path)
    assert injected.resources_dir == tmp_path


def test_environment_wins_over_dotenv_without_mutation(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=file-secret\nHOST=192.168.1.2\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "environment-secret")
    value = config.Settings(_env_file=env_file)
    assert value.openai_api_key.get_secret_value() == "environment-secret"
    assert os.environ["OPENAI_API_KEY"] == "environment-secret"
    assert value.host == "192.168.1.2"
    env_file.write_text("UNKNOWN_SETTING=value\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        config.Settings(_env_file=env_file)


def test_settings_context_is_nested_readonly_and_task_local():
    first = config.Settings(_env_file=None, default_llm_model="first")
    second = config.Settings(_env_file=None, default_llm_model="second")
    with config.settings_context(first):
        assert config.get_settings() is first
        assert config.settings.default_llm_model == "first"
        with pytest.raises(AttributeError):
            config.settings.default_llm_model = "mutated"
        with pytest.raises(RuntimeError):
            with config.settings_context(second):
                assert config.get_settings() is second
                raise RuntimeError("reset context")
        assert config.get_settings() is first

    async def read(value):
        with config.settings_context(value):
            await asyncio.sleep(0)
            return config.get_settings()

    async def run():
        return await asyncio.gather(read(first), read(second))

    assert asyncio.run(run()) == [first, second]


def test_logging_redacts_credentials_arguments_and_tracebacks():
    from apps.core.logging import configure_logging, redact

    value = config.Settings(_env_file=None, openai_api_key="arbitrary-private-key")
    root = logging.getLogger()
    old_level = root.level
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(self.format(record))

    handler = Capture()
    root.addHandler(handler)
    try:
        configure_logging(value)
        with config.settings_context(value):
            assert "arbitrary-private-key" not in redact("arbitrary-private-key")
            logging.getLogger("sdk.test").warning(
                "key=%s Bearer bearer-private https://user:pass-private@example.com",
                "arbitrary-private-key",
            )
            try:
                raise ValueError("arbitrary-private-key Bearer traceback-secret")
            except ValueError:
                logging.getLogger("sdk.test").exception("request failed")
        for secret in (
            "arbitrary-private-key",
            "bearer-private",
            "pass-private",
            "traceback-secret",
        ):
            assert secret not in "\n".join(records)
        assert "example.com" in records[0]
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)


def test_model_registry_cache_is_scoped_to_config_path(tmp_path):
    from apps.llm.registry import resolve

    for name, cap in (("one", 1000), ("two", 2000)):
        path = tmp_path / f"{name}.yaml"
        path.write_text(
            f"models:\n  example:\n    context_window: {cap}\n    max_output_tokens: 100\n"
        )
        with config.settings_context(config.Settings(_env_file=None, models_config_path=path)):
            assert resolve("example").context_window == cap


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_factory_unwraps_secrets_only_for_provider_clients(tmp_path, monkeypatch, provider):
    from apps.llm import factory

    registry = tmp_path / "models.yaml"
    registry.write_text(
        "models:\n  default:\n    context_window: 1000\n    max_output_tokens: 123\n"
    )
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(factory, "ChatAnthropic", create)
    monkeypatch.setattr(factory, "ChatOpenAI", create)
    value = config.Settings(
        _env_file=None,
        default_llm_provider=provider,
        models_config_path=registry,
        anthropic_api_key="anthropic-key",
        anthropic_auth_token="anthropic-token",
        openai_api_key="openai-key",
        anthropic_base_url="https://anthropic.example.com",
        openai_base_url="https://openai.example.com",
    )
    with config.settings_context(value):
        factory.get_llm(temperature=0.2)
    assert captured["max_tokens"] == 123
    assert captured["temperature"] == 0.2
    if provider == "anthropic":
        assert captured["anthropic_api_key"] == "anthropic-token"
        assert captured["default_headers"]["Authorization"] == "Bearer anthropic-token"
    else:
        assert captured["openai_api_key"] == "openai-key"


def test_skill_cache_is_scoped_to_root_and_config_path(tmp_path):
    from apps.services.skill_loader import load_skill_bundle

    for name in ("one", "two"):
        root = tmp_path / name
        skill = root / "same-skill"
        skill.mkdir(parents=True)
        (skill / "skill.yaml").write_text(
            "id: same-skill\nartifacts:\n  - path: instructions.md\n    role: instructions\n"
        )
        (skill / "instructions.md").write_text(name)
        path = tmp_path / f"{name}.yaml"
        path.write_text("bindings:\n  prd:\n    skills: [same-skill]\n")
        with config.settings_context(
            config.Settings(_env_file=None, skills_root=root, skills_config_path=path)
        ):
            assert load_skill_bundle("prd").artifacts[0].content == name


def test_skill_paths_cannot_escape_configured_root(tmp_path):
    from apps.services.skill_loader import load_skill_manifest, read_artifact_file

    root = tmp_path / "skills"
    skill = root / "safe"
    skill.mkdir(parents=True)
    (tmp_path / "secret.txt").write_text("secret")
    (skill / "escape.txt").symlink_to(tmp_path / "secret.txt")
    with config.settings_context(config.Settings(_env_file=None, skills_root=root)):
        for name in ("../other", str(tmp_path), "a/b"):
            with pytest.raises(ValueError):
                load_skill_manifest(name)
        for path in ("../../secret.txt", str(tmp_path / "secret.txt"), "escape.txt"):
            with pytest.raises(ValueError):
                read_artifact_file("safe", path)
