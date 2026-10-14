"""只读脱敏配置接口，从配置的模型注册表读取可用模型。"""

from fastapi import APIRouter, Depends
import yaml

from apps.api.deps import get_resources
from apps.core.errors import DomainError
from apps.core.logging import redact

router = APIRouter(prefix="/api/config", tags=["config"])


def _provider_for(name: str, models: dict) -> str | None:
    seen = set()
    while name not in seen:
        seen.add(name)
        entry = models.get(name)
        if not isinstance(entry, dict):
            return None
        if entry.get("alias_of"):
            name = entry["alias_of"]
            continue
        provider = entry.get("provider")
        return "openai" if provider == "openai_compatible" else provider
    raise DomainError("模型注册表包含循环别名", code="INVALID_MODEL_REGISTRY", status_code=503)


@router.get("/llm-providers")
async def get_llm_providers(resources=Depends(get_resources)):
    with resources.settings.models_config_path.open(encoding="utf-8") as file:
        registry = yaml.safe_load(file) or {}
    models = registry.get("models")
    if not isinstance(models, dict):
        raise DomainError("模型注册表格式无效", code="INVALID_MODEL_REGISTRY", status_code=503)
    names = {"anthropic": "Anthropic (Claude)", "openai": "OpenAI 兼容"}
    groups = {provider: [] for provider in names}
    for model in models:
        if model == "default":
            continue
        provider = _provider_for(model, models)
        if provider in groups:
            groups[provider].append(redact(model))
    return {
        "providers": [
            {"id": provider, "name": label, "models": groups[provider]}
            for provider, label in names.items()
        ]
    }


@router.get("/current")
async def get_current_config(resources=Depends(get_resources)):
    settings = resources.settings
    return {
        "default_llm_provider": settings.default_llm_provider,
        "default_llm_model": redact(settings.default_llm_model),
        "anthropic_base_url": redact(settings.anthropic_base_url),
        "openai_base_url": redact(settings.openai_base_url),
        "has_anthropic_key": bool(
            settings.anthropic_credential.get_secret_value()
            and settings.anthropic_credential.get_secret_value() != "your_anthropic_api_key_here"
        ),
        "has_openai_key": bool(
            settings.openai_api_key.get_secret_value()
            and settings.openai_api_key.get_secret_value() != "your_openai_api_key_here"
        ),
    }


@router.post("/update", include_in_schema=False)
async def update_config():
    raise DomainError("配置由服务启动参数管理", code="METHOD_NOT_ALLOWED", status_code=405)
