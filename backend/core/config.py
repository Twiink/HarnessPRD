from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # AI API 配置
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    openai_api_key: str = ""

    # 默认模型选择
    default_llm_provider: str = "anthropic"  # anthropic 或 openai
    default_llm_model: str = "claude-3-5-sonnet-20241022"

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS 配置
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()