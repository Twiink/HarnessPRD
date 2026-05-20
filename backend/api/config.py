from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from core.config import settings


router = APIRouter(prefix="/api/config", tags=["config"])


class UpdateConfigRequest(BaseModel):
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    default_llm_provider: Optional[str] = None
    default_llm_model: Optional[str] = None


@router.get("/llm-providers")
async def get_llm_providers():
    """获取支持的大模型提供商列表"""
    return {
        "providers": [
            {
                "id": "anthropic",
                "name": "Anthropic (Claude)",
                "models": [
                    "MiniMax-M2.5",
                    "claude-opus-4-6",
                    "claude-sonnet-4-6",
                    "claude-3-5-sonnet-20241022",
                    "claude-haiku-4-5-20251001",
                ],
            },
            {
                "id": "openai",
                "name": "OpenAI (GPT)",
                "models": [
                    "gpt-4o",
                    "gpt-4o-mini",
                    "gpt-4-turbo",
                ],
            },
        ]
    }


@router.get("/current")
async def get_current_config():
    """获取当前配置（不返回 API KEY）"""
    return {
        "default_llm_provider": settings.default_llm_provider,
        "default_llm_model": settings.default_llm_model,
        "anthropic_base_url": settings.anthropic_base_url,
        "has_anthropic_key": bool(
            settings.anthropic_api_key
            and settings.anthropic_api_key != "your_anthropic_api_key_here"
        ),
        "has_openai_key": bool(
            settings.openai_api_key
            and settings.openai_api_key != "your_openai_api_key_here"
        ),
    }


@router.post("/update")
async def update_config(request: UpdateConfigRequest):
    """动态更新配置（运行时）"""
    updated_fields = []

    if request.anthropic_api_key:
        settings.anthropic_api_key = request.anthropic_api_key
        updated_fields.append("anthropic_api_key")

    if request.anthropic_base_url is not None:
        settings.anthropic_base_url = request.anthropic_base_url
        updated_fields.append("anthropic_base_url")

    if request.openai_api_key:
        settings.openai_api_key = request.openai_api_key
        updated_fields.append("openai_api_key")

    if request.default_llm_provider:
        if request.default_llm_provider not in ["anthropic", "openai"]:
            raise HTTPException(status_code=400, detail="不支持的 LLM 提供商")
        settings.default_llm_provider = request.default_llm_provider
        updated_fields.append("default_llm_provider")

    if request.default_llm_model:
        settings.default_llm_model = request.default_llm_model
        updated_fields.append("default_llm_model")

    return {"status": "success", "updated_fields": updated_fields}
