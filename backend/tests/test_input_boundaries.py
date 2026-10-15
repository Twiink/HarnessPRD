"""API 在进入业务及流式响应前验证嵌套输入，同时保留扩展字段。"""

import pytest
from fastapi.testclient import TestClient

from apps.core.config import Settings
from apps.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid requests must not enter model execution")

    monkeypatch.setattr(
        "apps.services.conversations.dialogue.ConversationService.continue_conversation_stream",
        forbidden,
    )
    app = create_app(Settings(_env_file=None, database_path=tmp_path / "inputs.db"))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize("prefix", ["/api/sessions", "/api/session/save"])
@pytest.mark.parametrize(
    "data",
    [
        {"prdContent": 123},
        {"manualPrdInput": 123},
        {"formData": "malformed"},
        {"requirementsSummary": {"features": 42}},
        {"requirementsSummary": {"ui_pages": [{"name": "home", "modules": "wrong"}]}},
        {"requirementsSummary": {"design_requirements": {"responsive": "false"}}},
        {"requirementsSummary": {"non_functional_requirements": {"security": 3}}},
        {"prdReviewResult": {"passed": "false"}},
        {"messages": [{}]},
        {"messages": [{"role": "unknown", "content": "text"}]},
    ],
)
def test_nested_session_errors_are_422(client, prefix, data):
    response = client.post(prefix, json={"session_data": data})
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("prefix", ["/api/conversations", "/api/conversation"])
@pytest.mark.parametrize(
    "messages", [[{}], [{"role": "user", "content": 7}], [{"role": "unknown", "content": "x"}]]
)
def test_invalid_messages_rejected_before_stream(client, prefix, messages):
    response = client.post(
        prefix + "/continue-stream",
        json={"conversation_id": "test", "messages": messages, "user_input": "next"},
    )
    assert response.status_code == 422, response.text
    assert "text/event-stream" not in response.headers.get("content-type", "")


def test_nested_extensions_and_legacy_requirements_are_preserved(client):
    response = client.post(
        "/api/sessions",
        json={
            "session_data": {
                "custom": {"x": 1},
                "formData": {"product_name": "demo", "features": "login", "custom": True},
                "messages": [{"role": "ai", "content": "ready", "clarification_meta": {"x": 1}}],
            }
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()["session_data"]
    assert data["custom"] == {"x": 1}
    assert data["formData"]["custom"] is True
    assert data["messages"][0]["clarification_meta"] == {"x": 1}


def test_form_modules_text_and_summary_modules_list_are_compatible(client):
    response = client.post(
        "/api/sessions",
        json={
            "session_data": {
                "formData": {"ui_pages": [{"name": "home", "modules": "a,b"}]},
                "requirementsSummary": {"ui_pages": [{"name": "home", "modules": ["a", "b"]}]},
                "prdReviewResult": {"passed": False, "custom_score": 40},
            }
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()["session_data"]
    assert data["formData"]["ui_pages"][0]["modules"] == "a,b"
    assert data["requirementsSummary"]["ui_pages"][0]["modules"] == ["a", "b"]
