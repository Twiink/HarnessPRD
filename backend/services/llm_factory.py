"""LLM 实例工厂 — 根据配置返回 Anthropic 或 OpenAI 模型"""

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from core.config import settings


def get_llm(temperature: float = 0.7) -> ChatAnthropic | ChatOpenAI:
    """根据环境配置创建 LLM 实例"""
    if settings.default_llm_provider == "anthropic":
        kwargs = dict(
            anthropic_api_key=settings.anthropic_credential,
            model=settings.default_llm_model,
            temperature=temperature,
            max_tokens=4096,
        )
        if settings.anthropic_base_url:
            kwargs["base_url"] = settings.anthropic_base_url
        if settings.anthropic_auth_token:
            kwargs["default_headers"] = {
                "Authorization": f"Bearer {settings.anthropic_auth_token}",
            }
        return ChatAnthropic(**kwargs)
    else:
        return ChatOpenAI(
            openai_api_key=settings.openai_api_key,
            model=settings.default_llm_model or "gpt-4o",
            temperature=temperature,
        )
