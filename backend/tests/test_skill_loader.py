"""Skill loader 单元测试 — 可用 pytest 或 python -m tests.test_skill_loader 运行"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from apps.core.resources.skill_loader import (  # noqa: E402
    compose_prompt_sections,
    load_skill_bundle,
    resolve_skill_ids,
)


def test_load_prd_bundle():
    bundle = load_skill_bundle("prd")
    assert bundle.skills == ["prd-generator"]
    assert len(bundle.artifacts) >= 4

    roles = {a.role for a in bundle.artifacts}
    assert "template" in roles
    assert "schema" in roles

    sections = compose_prompt_sections(bundle)
    assert "template" in sections
    assert "schema" in sections
    assert len(sections["template"]) > 100
    assert "{" in sections["schema"]


def test_optimize_prd_binding():
    skill_ids = resolve_skill_ids("optimize-prd")
    assert skill_ids == ["prd-generator"]


def test_empty_api_docs_binding():
    # api-docs 现已绑定 api-docs-generator，保留 prd 空绑定测试不适用；改测 optimize 绑定
    skill_ids = resolve_skill_ids("optimize-api-docs")
    assert skill_ids == ["api-docs-generator"]


def test_invalid_skill_raises():
    from apps.core.resources import skill_loader as skill_loader

    original = skill_loader._load_bindings_config
    skill_loader._load_bindings_config.cache_clear()
    skill_loader.load_skill_manifest.cache_clear()

    try:
        import yaml

        config_path = skill_loader.get_config_path()
        backup = config_path.read_text(encoding="utf-8")
        bad_config = yaml.safe_load(backup)
        bad_config["bindings"]["test-invalid"] = {"skills": ["nonexistent-skill-xyz"]}
        config_path.write_text(yaml.dump(bad_config, allow_unicode=True), encoding="utf-8")
        skill_loader._load_bindings_config.cache_clear()

        try:
            load_skill_bundle("test-invalid")
            raise AssertionError("应抛出配置校验异常")
        except ValueError as exc:
            assert "nonexistent-skill-xyz" in str(exc)
    finally:
        config_path.write_text(backup, encoding="utf-8")
        skill_loader._load_bindings_config.cache_clear()
        skill_loader.load_skill_manifest.cache_clear()


def test_api_docs_bundle():
    bundle = load_skill_bundle("api-docs")
    assert bundle.skills == ["api-docs-generator"]
    assert len(bundle.artifacts) >= 4
    sections = compose_prompt_sections(bundle)
    assert "reference" in sections
    assert "example" in sections


def test_prompts_bundle():
    bundle = load_skill_bundle("prompts")
    assert bundle.skills == ["prompts-generator"]
    sections = compose_prompt_sections(bundle)
    assert "template" in sections


def test_bundle_to_injected_meta():
    from apps.core.resources.skill_loader import bundle_to_injected_meta

    bundle = load_skill_bundle("api-docs")
    meta = bundle_to_injected_meta(bundle)
    assert len(meta) >= 1
    assert meta[0]["skill_id"] == "api-docs-generator"
    assert "team-api-guidelines.md" in meta[0]["artifacts"][0] or any(
        "team-api-guidelines" in a for a in meta[0]["artifacts"]
    )


if __name__ == "__main__":
    test_load_prd_bundle()
    test_optimize_prd_binding()
    test_empty_api_docs_binding()
    test_invalid_skill_raises()
    test_api_docs_bundle()
    test_prompts_bundle()
    test_bundle_to_injected_meta()
    print("All skill_loader tests passed.")
