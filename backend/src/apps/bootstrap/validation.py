"""在任务调度和 ready 之前验证本地必需资源，不请求模型供应商。"""

import json
import logging

import yaml

from apps.core.config import Settings
from apps.core.errors import DomainError
from apps.core.resources.prompts import PROMPT_NAMES, get_prompt
from apps.core.resources.skill_loader import load_skill_bundle
from apps.llm.registry import resolve
from apps.domain.jobs import Artifact

logger = logging.getLogger(__name__)


def validate_resources(settings: Settings) -> None:
    try:
        for name in PROMPT_NAMES:
            if not get_prompt(name).strip():
                raise ValueError("empty prompt")
        if not (settings.resources_dir / "prd_template.md").read_text(encoding="utf-8").strip():
            raise ValueError("empty PRD template")
        questions = json.loads(
            (settings.resources_dir / "questions_config.json").read_text(encoding="utf-8")
        )
        if not isinstance(questions, dict) or not questions:
            raise ValueError("invalid questions configuration")
        registry = yaml.safe_load(settings.models_config_path.read_text(encoding="utf-8"))
        if not isinstance(registry, dict) or not isinstance(registry.get("models"), dict):
            raise ValueError("invalid models registry")
        if not registry["models"]:
            raise ValueError("empty models registry")
        for model in registry["models"]:
            resolve(model)
        bindings = yaml.safe_load(settings.skills_config_path.read_text(encoding="utf-8"))
        if not isinstance(bindings, dict) or not isinstance(bindings.get("bindings"), dict):
            raise ValueError("invalid skill registry")
        if {artifact.value for artifact in Artifact} - bindings["bindings"].keys():
            raise ValueError("missing required artifact bindings")
        if not settings.skills_root.is_dir():
            raise ValueError("missing skills directory")
        for artifact in bindings["bindings"]:
            bundle = load_skill_bundle(artifact)
            for item in bundle.artifacts:
                if item.role != "example" and not item.content.strip():
                    raise ValueError("missing required skill artifact")
    except (OSError, ValueError, TypeError, AttributeError, KeyError, yaml.YAMLError) as exc:
        logger.exception("必需资源校验失败 error_type=%s", type(exc).__name__)
        raise DomainError(
            "必需资源配置无效，请检查服务启动日志", code="INVALID_RESOURCES", status_code=503
        ) from exc
