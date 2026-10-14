"""不可变的应用配置：惰性加载，并通过上下文隔离不同应用和任务。"""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        hide_input_in_errors=True,
    )

    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_auth_token: SecretStr = SecretStr("")
    anthropic_base_url: str = ""
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = ""

    default_llm_provider: Literal["anthropic", "openai"] = "anthropic"
    default_llm_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        validation_alias=AliasChoices("DEFAULT_LLM_MODEL", "ANTHROPIC_MODEL"),
    )
    host: str = "127.0.0.1"
    port: int = Field(default=8001, ge=1, le=65535)
    cors_origins: str = "http://localhost:5174,http://localhost:5173,http://localhost:3000"
    log_llm_metrics: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    database_path: Path = BACKEND_DIR / "data" / "sessions.db"
    sqlite_busy_timeout_ms: int = Field(default=5000, ge=1)
    job_poll_interval: float = Field(default=0.1, gt=0)
    job_lease_seconds: float = Field(default=30, gt=0)
    job_max_attempts: int = Field(default=3, ge=1)
    job_max_concurrency: int = Field(default=2, ge=1)
    job_shutdown_timeout: float = Field(default=5, gt=0)
    resources_dir: Path = BACKEND_DIR / "resources"
    skills_root: Path = REPO_ROOT / "skills"
    skills_config_path: Path = REPO_ROOT / "config" / "skills.yaml"
    models_config_path: Path = BACKEND_DIR / "config" / "models.yaml"

    context_budget_tokens: int = Field(default=120000, ge=1)
    chat_history_budget: int = Field(default=60000, ge=1)
    single_call_input_budget: int = Field(default=100000, ge=1)
    token_budget_mode: Literal["warn", "reject"] = "warn"
    token_estimator: Literal["tiktoken", "char_heuristic"] = "tiktoken"
    token_encoding: str = "cl100k_base"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def anthropic_credential(self) -> SecretStr:
        return self.anthropic_auth_token or self.anthropic_api_key


_current_settings: ContextVar[Settings | None] = ContextVar("settings", default=None)


@lru_cache(maxsize=1)
def _default_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    value = _current_settings.get()
    return value if value is not None else _default_settings()


@contextmanager
def settings_context(settings: Settings) -> Iterator[Settings]:
    """绑定当前应用配置；上下文中创建的异步任务也继承此配置。"""
    token = _current_settings.set(settings)
    try:
        yield settings
    finally:
        _current_settings.reset(token)


class _SettingsProxy:
    __slots__ = ()

    def __getattr__(self, name: str):
        return getattr(get_settings(), name)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("settings is read-only; use settings_context()")

    def __repr__(self) -> str:
        return "<lazy read-only settings>"


settings = _SettingsProxy()
