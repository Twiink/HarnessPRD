"""需求就绪度单元测试"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.requirements_readiness import (  # noqa: E402
    assess_requirements_readiness,
    readiness_has_blockers,
)


def _minimal_summary(**overrides):
    base = {
        "product_name": "测试产品",
        "product_goal": "帮助用户更高效地完成某项任务",
        "target_users": ["开发者"],
        "platform": "Web App",
        "mvp_features": [
            {"name": "功能A", "description": "描述足够长的功能说明", "user_value": "价值"},
        ],
        "in_scope": ["MVP"],
        "out_of_scope": ["登录"],
    }
    base.update(overrides)
    return base


def test_ready_summary_no_blockers():
    result = assess_requirements_readiness(_minimal_summary())
    assert result["blockers"] == []
    assert result["score"] >= 80


def test_missing_product_name_blocker():
    result = assess_requirements_readiness(_minimal_summary(product_name=""))
    assert readiness_has_blockers(_minimal_summary(product_name=""))
    assert any(c["id"] == "summary.product_name" for c in result["blockers"])


def test_empty_mvp_blocker():
    result = assess_requirements_readiness(_minimal_summary(mvp_features=[]))
    assert any(c["id"] == "summary.mvp_features" for c in result["blockers"])


def test_missing_summary():
    result = assess_requirements_readiness(None)
    assert result["score"] == 0
    assert len(result["blockers"]) == 1


if __name__ == "__main__":
    test_ready_summary_no_blockers()
    test_missing_product_name_blocker()
    test_empty_mvp_blocker()
    test_missing_summary()
    print("ok")
