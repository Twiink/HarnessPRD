"""完整项目功能清单、会话转换与文档历史的回归验证。"""

import io
import json
import zipfile

import pytest

from apps.db import connection as database
from apps.services.delivery_export_service import build_delivery_zip
from apps.services.document_service import _build_prd_from_summary_prompt
from apps.services.document_version_service import (
    checkpoint,
    get_current_version,
    get_version,
    list_versions,
    restore_version,
    update_version_note,
)
from apps.services.requirements_normalization import normalize_feature_fields
from apps.services.session_service import get_session, save_session


def test_merge_feature_sources_preserves_details_and_is_idempotent():
    original = {
        "product_name": "测试项目",
        "features": [{"name": "登录", "description": "邮箱登录", "user_value": "待确认"}],
        "mvp_features": [{"name": "登录", "description": "手机号登录", "user_value": "进入工作台"}],
        "v2_features": ["登录", "历史记录"],
        "out_of_scope": ["支付"],
    }
    merged = normalize_feature_fields(original)
    assert [row["name"] for row in merged["features"]] == ["登录", "历史记录"]
    assert merged["features"][0]["description"] == "邮箱登录；手机号登录"
    assert merged["features"][0]["user_value"] == "进入工作台"
    assert merged["out_of_scope"] == ["支付"]
    assert "mvp_features" not in merged
    assert "v2_features" not in merged
    assert "mvp_features" in original
    assert normalize_feature_fields(merged) == merged


def test_merge_text_features_keeps_numeric_feature_names():
    merged = normalize_feature_fields(
        {
            "mvp_features": "1. 登录 | 邮箱认证 | 进入工作台\n2FA | 双因素认证 | 保护账户",
            "v2_features": "- 历史记录\n2. 收藏",
        }
    )
    assert [row["name"] for row in merged["features"]] == ["登录", "2FA", "历史记录", "收藏"]
    assert merged["features"][0]["description"] == "邮箱认证"


def test_feature_metadata_and_conflicting_priorities_are_preserved():
    merged = normalize_feature_fields(
        {
            "features": [
                {
                    "name": "登录",
                    "description": "邮箱认证",
                    "priority": "P0",
                    "acceptance": ["会话隔离"],
                }
            ],
            "mvp_features": [{"name": "登录", "description": "邮箱认证", "priority": "P1"}],
        }
    )
    assert len(merged["features"]) == 2
    assert merged["features"][0]["acceptance"] == ["会话隔离"]
    assert [row["priority"] for row in merged["features"]] == ["P0", "P1"]
    assert normalize_feature_fields(merged) == merged


def test_existing_session_load_and_save_uses_complete_features(isolated_database):
    data = {
        "viewState": "form",
        "formData": {"product_name": "测试项目", "mvp_features": "登录", "v2_features": "历史记录"},
        "requirementsSummary": {
            "product_name": "测试项目",
            "mvp_features": [{"name": "登录"}],
            "v2_features": ["历史记录"],
        },
        "pendingSummary": {"mvp_features": [{"name": "收藏"}], "v2_features": ["搜索"]},
    }
    session_id = save_session(data)["id"]
    # Simulate a persisted session created before the unified feature collection.
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE project_sessions SET session_data = ? WHERE id = ?",
            (json.dumps(data), session_id),
        )
        conn.commit()
    loaded = get_session(session_id)["session_data"]
    for key in ("formData", "requirementsSummary", "pendingSummary"):
        assert len(loaded[key]["features"]) == 2
        assert "mvp_features" not in loaded[key]
        assert "v2_features" not in loaded[key]
    save_session(loaded, session_id)
    assert get_session(session_id)["session_data"] == loaded


def test_prd_prompt_includes_all_feature_sources():
    prompt = _build_prd_from_summary_prompt({"mvp_features": ["登录"], "v2_features": ["历史记录"]})
    assert "登录" in prompt
    assert "历史记录" in prompt
    assert '"features"' in prompt
    assert "mvp_features" not in prompt
    assert "v2_features" not in prompt
    assert "未来规划" not in prompt


def test_document_history_restore_notes_and_delivery_remain_available(isolated_database):
    session_id = save_session(
        {"formData": {"product_name": "完整项目"}, "prdContent": "# 原始需求"}
    )["id"]
    original = get_current_version(session_id, "prd")
    saved = checkpoint(session_id, "prd", "# 更新后的需求", "审阅前备份")
    update_version_note(session_id, "prd", saved["version_id"], "已人工审阅")
    assert (
        get_version(session_id, "prd", saved["version_id"])["metadata"]["change_note"]
        == "已人工审阅"
    )
    restore_version(session_id, "prd", original["id"])
    history = list_versions(session_id, "prd")
    assert len(history["versions"]) == 3
    assert get_current_version(session_id, "prd")["content"] == "# 原始需求"
    archive, filename = build_delivery_zip(session_id)
    assert filename == "完整项目-delivery.zip"
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        assert bundle.read("PRD.md").decode() == "# 原始需求"
        readme = bundle.read("README.md").decode()
        assert "文档清单" in readme
        assert "版本" not in readme
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["documents"]["prd"]["record_id"]
        assert "version_no" not in manifest["documents"]["prd"]


def test_application_starts_and_serves_project_routes(isolated_database):
    from fastapi.testclient import TestClient
    from apps.main import create_app
    from apps.core.config import Settings

    app = create_app(settings=Settings(_env_file=None, database_path=isolated_database.path))

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "healthy"}
        assert client.get("/").json() == {"message": "Vibe Coding API 运行中"}
        assert "/api/sessions" in client.get("/openapi.json").json()["paths"]
        response = client.post(
            "/api/session/save",
            json={
                "session_data": {
                    "formData": {"product_name": "完整项目", "features": [{"name": "历史记录"}]}
                }
            },
        )
        assert response.status_code == 200
        session_id = response.json()["id"]
        assert client.get(f"/api/session/{session_id}").json()["title"] == "完整项目"
