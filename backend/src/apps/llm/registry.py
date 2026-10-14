"""按配置路径和模型名称缓存模型能力，隔离应用配置。"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from apps.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelCaps:
    name: str
    context_window: int
    max_output_tokens: int
    encoding: str = "cl100k_base"


def _load_raw(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    models = data.get("models")
    if not isinstance(models, dict):
        raise ValueError("Model registry must contain a models mapping")
    return models


def _resolve_entry(
    model_name: str, models: dict[str, Any], seen: set[str] | None = None
) -> tuple[str, dict[str, Any]]:
    seen = set() if seen is None else seen
    if model_name in seen:
        raise ValueError(f"circular alias: {model_name}")
    seen.add(model_name)
    entry = models.get(model_name)
    if entry is None:
        return "default", models.get("default") or {}
    if not isinstance(entry, dict):
        raise ValueError(f"Invalid model capabilities: {model_name}")
    if entry.get("alias_of"):
        return _resolve_entry(entry["alias_of"], models, seen)
    return model_name, entry


@lru_cache(maxsize=128)
def _resolve(path: Path, model_name: str) -> ModelCaps:
    resolved_name, entry = _resolve_entry(model_name, _load_raw(path))
    context = int(entry.get("context_window") or 32768)
    output = int(entry.get("max_output_tokens") or 4096)
    if context <= 0 or output <= 0 or output >= context:
        raise ValueError(f"Invalid token limits for model: {model_name}")
    return ModelCaps(
        name=resolved_name,
        context_window=context,
        max_output_tokens=output,
        encoding=str(entry.get("encoding") or "cl100k_base"),
    )


def resolve(model_name: str) -> ModelCaps:
    return _resolve(get_settings().models_config_path.resolve(), model_name)


def resolve_max_output(model_name: str) -> int:
    return resolve(model_name).max_output_tokens


def hardware_input_cap(model_name: str) -> int:
    caps = resolve(model_name)
    return max(caps.context_window - caps.max_output_tokens, 1)


setattr(resolve, "cache_clear", _resolve.cache_clear)
