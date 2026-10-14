"""澄清状态 / 交付守卫测试"""

import sys
from pathlib import Path

import pytest
from apps.core.errors import DomainError

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from apps.services.delivery_guards import assert_can_create_job  # noqa: E402


def _minimal_summary(**overrides):
    base = {
        "product_name": "测试产品",
        "product_goal": "帮助用户更高效地完成某项任务",
        "target_users": ["开发者"],
        "platform": "Web App",
        "features": [
            {"name": "功能A", "description": "描述足够长的功能说明", "user_value": "价值"},
        ],
    }
    base.update(overrides)
    return base


def test_prd_job_allowed_with_minimal_summary_even_if_goal_short():
    """澄清警告放行：后端不因字段薄 blocker PRD Job。"""
    summary = _minimal_summary(product_goal="短")
    assert_can_create_job(
        {"requirementsSummary": summary}, "prd", {"requirements_summary": summary}
    )


def test_prd_job_requires_summary():
    with pytest.raises(DomainError) as exc:
        assert_can_create_job({}, "prd")
    assert exc.value.status_code == 400
    assert exc.value.code == "REQUIREMENTS_REQUIRED"
    assert "摘要" in exc.value.message


def test_api_docs_job_requires_baseline():
    with pytest.raises(DomainError) as exc:
        assert_can_create_job({"prdContent": "# PRD"}, "api-docs")
    assert exc.value.status_code == 400
    assert exc.value.code == "BASELINE_REQUIRED"
    assert "基线" in exc.value.message


@pytest.mark.parametrize("artifact", ["api-docs", "prompts"])
def test_downstream_documents_require_nonempty_baseline_content(artifact):
    with pytest.raises(DomainError) as error:
        assert_can_create_job({"prdBaselineConfirmed": True, "prdContent": "  "}, artifact)
    assert error.value.code == "PRD_REQUIRED"
    assert error.value.status_code == 400


@pytest.mark.parametrize("artifact", ["api-docs", "prompts"])
def test_downstream_documents_accept_confirmed_baseline(artifact):
    assert_can_create_job({"prdBaselineConfirmed": True, "prdContent": "# PRD"}, artifact)


@pytest.mark.parametrize("artifact", ["optimize-prd", "optimize-api-docs", "optimize-prompts"])
def test_optimization_does_not_require_generation_inputs(artifact):
    assert_can_create_job({}, artifact)
