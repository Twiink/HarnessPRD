"""依据当前应用的配置创建模型客户端。"""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from apps.core.config import get_settings
from apps.llm.registry import resolve_max_output
from apps.llm.tracking import TrackedChatModel


def get_llm(temperature: float = 0.7) -> ChatAnthropic | ChatOpenAI:
    settings = get_settings()
    model = settings.default_llm_model or "gpt-4o"
    max_tokens = resolve_max_output(model)
    if settings.default_llm_provider == "anthropic":
        kwargs: dict[str, Any] = {
            "anthropic_api_key": settings.anthropic_credential.get_secret_value(),
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": settings.llm_call_timeout,
            "max_retries": 0,
        }
        if settings.anthropic_base_url:
            kwargs["base_url"] = settings.anthropic_base_url
        if settings.anthropic_auth_token:
            kwargs["default_headers"] = {
                "Authorization": f"Bearer {settings.anthropic_auth_token.get_secret_value()}",
            }
        return ChatAnthropic(**kwargs)
    kwargs = {
        "openai_api_key": settings.openai_api_key.get_secret_value(),
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": settings.llm_call_timeout,
        "max_retries": 0,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**kwargs)


def get_tracked_llm(step: str, temperature: float = 0.7) -> TrackedChatModel:
    return TrackedChatModel(get_llm(temperature=temperature), step=step)
