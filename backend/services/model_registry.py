"""模型注册表 — 从 models.yaml 加载物理顶，供 budget 与 max_tokens 联动"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

MODELS_YAML = Path(__file__).resolve().parents[1] / "config" / "models.yaml"


@dataclass(frozen=True)
class ModelCaps:
    name: str
    context_window: int
    max_output_tokens: int
    encoding: str = "cl100k_base"


def _load_raw() -> Dict[str, Any]:
    with MODELS_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("models") or {}


def _resolve_entry(model_name: str, models: Dict[str, Any], seen: Optional[set] = None) -> tuple[str, Dict[str, Any]]:
    seen = seen or set()
    if model_name in seen:
        raise ValueError(f"circular alias: {model_name}")
    seen.add(model_name)

    entry = models.get(model_name)
    if entry is None:
        return "default", models.get("default") or {}

    alias = entry.get("alias_of")
    if alias:
        return _resolve_entry(alias, models, seen)
    return model_name, entry


@lru_cache(maxsize=128)
def resolve(model_name: str) -> ModelCaps:
    models = _load_raw()
    resolved_name, entry = _resolve_entry(model_name, models)

    if not entry:
        logger.warning("model_registry: unknown model %r, using default caps", model_name)
        _, entry = _resolve_entry("default", models)
        resolved_name = "default"

    if resolved_name != model_name and entry:
        logger.debug("model_registry: %r resolved to %r", model_name, resolved_name)

    return ModelCaps(
        name=resolved_name,
        context_window=int(entry.get("context_window") or 32768),
        max_output_tokens=int(entry.get("max_output_tokens") or 4096),
        encoding=str(entry.get("encoding") or "cl100k_base"),
    )


def resolve_max_output(model_name: str) -> int:
    """输出上限仅来自注册表；与 get_llm(max_tokens) 及 budget 预留联动。"""
    return resolve(model_name).max_output_tokens


def hardware_input_cap(model_name: str) -> int:
    caps = resolve(model_name)
    return max(caps.context_window - caps.max_output_tokens, 1)
