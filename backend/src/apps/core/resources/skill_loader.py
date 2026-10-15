"""Skill 知识层统一加载器 — 扫描、校验、读取、拼接 skill 内容"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from apps.core.config import REPO_ROOT, get_settings

logger = logging.getLogger(__name__)


@dataclass
class SkillArtifact:
    skill_id: str
    path: str
    role: str
    content: str


@dataclass
class SkillBundle:
    artifact: str
    skills: list[str] = field(default_factory=list)
    artifacts: list[SkillArtifact] = field(default_factory=list)


def get_repo_root() -> Path:
    return REPO_ROOT


def get_skills_root() -> Path:
    return get_settings().skills_root.resolve()


def get_config_path() -> Path:
    return get_settings().skills_config_path.resolve()


@lru_cache(maxsize=32)
def _load_bindings(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        raise FileNotFoundError(f"Skill 注册表不存在: {config_path}")
    with config_path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    bindings = data.get("bindings")
    if not isinstance(bindings, dict):
        raise ValueError("Skill 配置缺少 bindings 字段")
    return bindings


def _load_bindings_config() -> dict[str, Any]:
    return _load_bindings(get_config_path())


def _skill_dir(root: Path, skill_id: str) -> Path:
    if not skill_id or skill_id in (".", "..") or any(c in skill_id for c in ("/", "\\")):
        raise ValueError(f"Invalid skill id: {skill_id}")
    path = (root / skill_id).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Skill path escapes skills_root: {skill_id}")
    if not path.is_dir():
        raise ValueError(f"skills.yaml 引用了不存在的 skill 目录: {skill_id}")
    return path


def _artifact_path(root: Path, skill_id: str, relative_path: str) -> Path:
    directory = _skill_dir(root, skill_id)
    relative = Path(relative_path)
    if relative.is_absolute():
        raise ValueError("Skill artifact path must be relative")
    path = (directory / relative).resolve()
    if not path.is_relative_to(directory):
        raise ValueError("Skill artifact path escapes skill directory")
    return path


def _validate_skill_id(skill_id: str) -> None:
    _skill_dir(get_skills_root(), skill_id)


@lru_cache(maxsize=128)
def _load_manifest(root: Path, config_path: Path, skill_id: str) -> dict[str, Any]:
    manifest_path = _artifact_path(root, skill_id, "skill.yaml")
    if not manifest_path.is_file():
        raise ValueError(f"skill 目录缺少 skill.yaml: {skill_id}")
    with manifest_path.open(encoding="utf-8") as file:
        manifest = yaml.safe_load(file) or {}
    if manifest.get("id") != skill_id:
        raise ValueError(f"skill.yaml id 与目录名不一致: 目录={skill_id}, id={manifest.get('id')}")
    return manifest


def load_skill_manifest(skill_id: str) -> dict[str, Any]:
    return _load_manifest(get_skills_root(), get_config_path(), skill_id)


setattr(_load_bindings_config, "cache_clear", _load_bindings.cache_clear)
setattr(load_skill_manifest, "cache_clear", _load_manifest.cache_clear)


def resolve_skill_ids(artifact: str) -> list[str]:
    bindings = _load_bindings_config()
    binding = bindings.get(artifact)
    if binding is None:
        raise ValueError(f"config/skills.yaml 未声明 artifact 绑定: {artifact}")
    skill_ids = binding.get("skills") or []
    if not isinstance(skill_ids, list):
        raise ValueError(f"artifact {artifact} 的 skills 必须是列表")

    validated: list[tuple[int, str]] = []
    for skill_id in skill_ids:
        _validate_skill_id(skill_id)
        manifest = load_skill_manifest(skill_id)
        if manifest.get("enabled", True) is False:
            continue
        priority = manifest.get("priority", 100)
        validated.append((priority, skill_id))

    validated.sort(key=lambda item: item[0])
    return [skill_id for _, skill_id in validated]


def read_artifact_file(skill_id: str, relative_path: str) -> str:
    file_path = _artifact_path(get_skills_root(), skill_id, relative_path)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError as exc:
        logger.warning("读取 skill 文件失败: %s/%s — %s", skill_id, relative_path, exc)
        return ""


def load_skill_bundle(artifact: str) -> SkillBundle:
    skill_ids = resolve_skill_ids(artifact)
    bundle = SkillBundle(artifact=artifact, skills=skill_ids)

    for skill_id in skill_ids:
        manifest = load_skill_manifest(skill_id)
        artifacts_spec = manifest.get("artifacts") or []
        if not isinstance(artifacts_spec, list):
            continue

        for item in artifacts_spec:
            if not isinstance(item, dict):
                continue
            relative_path = item.get("path")
            role = item.get("role", "reference")
            if not relative_path:
                continue

            file_path = _artifact_path(get_skills_root(), skill_id, relative_path)
            if not file_path.is_file():
                if role == "example":
                    logger.warning("可选 example 文件缺失: %s/%s", skill_id, relative_path)
                else:
                    logger.warning("skill 文件缺失: %s/%s", skill_id, relative_path)
                content = ""
            else:
                content = read_artifact_file(skill_id, relative_path)

            bundle.artifacts.append(
                SkillArtifact(
                    skill_id=skill_id,
                    path=relative_path,
                    role=role,
                    content=content,
                )
            )

    return bundle


def compose_prompt_sections(bundle: SkillBundle) -> dict[str, str]:
    """按 role 分组拼接文本，缺失角色省略。"""
    role_order = ["instructions", "template", "reference", "schema", "example"]
    grouped: dict[str, list[str]] = {role: [] for role in role_order}

    for artifact in bundle.artifacts:
        if not artifact.content:
            continue
        if artifact.role not in grouped:
            grouped[artifact.role] = []
        grouped[artifact.role].append(artifact.content)

    sections: dict[str, str] = {}
    for role in role_order:
        parts = grouped.get(role) or []
        if parts:
            sections[role] = "\n\n".join(parts)
    return sections


def bundle_to_injected_meta(bundle: SkillBundle) -> list[dict[str, Any]]:
    """将 bundle 转为 run_summary.injected_skills 元数据。"""
    by_skill: dict[str, dict[str, Any]] = {}
    for artifact in bundle.artifacts:
        if not artifact.content:
            continue
        entry = by_skill.setdefault(
            artifact.skill_id,
            {"skill_id": artifact.skill_id, "version": "", "artifacts": []},
        )
        entry["artifacts"].append(artifact.path)

    for skill_id, entry in by_skill.items():
        manifest = load_skill_manifest(skill_id)
        entry["version"] = manifest.get("version", "")

    return list(by_skill.values())
