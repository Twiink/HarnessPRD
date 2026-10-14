from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_FILE, override=True)


class Settings(BaseSettings):
    # AI API 配置
    anthropic_api_key: str = ""
    anthropic_auth_token: str = ""
    anthropic_base_url: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""

    # 默认模型选择
    default_llm_provider: str = "anthropic"  # anthropic 或 openai（DeepSeek 等 OpenAI 兼容 API 用 openai）
    default_llm_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        validation_alias=AliasChoices("DEFAULT_LLM_MODEL", "ANTHROPIC_MODEL"),
    )

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8001

    # CORS 配置
    cors_origins: str = "http://localhost:5174,http://localhost:5173,http://localhost:3000"

    # 观测日志
    log_llm_metrics: bool = True
    log_level: str = "INFO"

    # Token 预算
    context_budget_tokens: int = 120000
    chat_history_budget: int = 60000
    single_call_input_budget: int = 100000
    token_budget_mode: str = "warn"
    token_estimator: str = "tiktoken"
    token_encoding: str = "cl100k_base"

    class Config:
        env_file = ENV_FILE
        case_sensitive = False
        extra = "ignore"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def anthropic_credential(self) -> str:
        return self.anthropic_auth_token or self.anthropic_api_key


settings = Settings()
