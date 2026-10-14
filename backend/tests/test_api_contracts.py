"""Resource routes, legacy adapters, safe errors and stream lifecycle contracts."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from apps.core.config import Settings


class FakeExecutor:
    async def execute(self, job, emit):
        raise AssertionError("API contracts must not call an external model")


@pytest.fixture
def client(tmp_path):
    from apps.main import create_app

    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "api.db",
        openai_api_key="contract-private-key",
        openai_base_url="https://user:password@example.com?api_key=contract-private-key",
    )
    with TestClient(create_app(settings=settings, executor=FakeExecutor())) as client:
        yield client


def create_session(client, **data):
    response = client.post("/api/sessions", json={"session_data": data})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def assert_error(response, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert {"code", "message", "request_id", "retryable"} <= body.keys()
    assert body["request_id"]
    assert response.headers["X-Request-ID"] == body["request_id"]
    assert isinstance(body["retryable"], bool)
    return body


def test_sessions_crud_and_legacy_adapters_share_state(client):
    session_id = create_session(client, formData={"product_name": "API contract"}, custom={"x": 1})
    assert client.get("/api/sessions").json()["items"][0]["id"] == session_id
    updated = client.patch(
        f"/api/sessions/{session_id}", json={"session_data": {"custom": {"x": 2}}}
    )
    assert updated.status_code == 200
    detail = client.get(f"/api/sessions/{session_id}").json()
    assert detail["session_data"]["custom"] == {"x": 2}
    assert detail["session_data"]["formData"]["product_name"] == "API contract"
    assert client.get(f"/api/session/{session_id}").json() == detail
    legacy = client.post(
        "/api/session/save", json={"id": session_id, "session_data": detail["session_data"]}
    )
    assert legacy.status_code == 200
    assert client.delete(f"/api/sessions/{session_id}").status_code == 200
    assert_error(client.get(f"/api/session/{session_id}"), 404)


def test_document_checkpoint_restore_history_note_and_legacy_paths(client):
    session_id = create_session(client)
    prefix = f"/api/sessions/{session_id}/documents/prd"
    first = client.post(prefix + "/checkpoint", json={"content": "first", "change_note": "initial"})
    assert first.status_code == 200, first.text
    version_id = first.json()["version_id"]
    second = client.post(prefix + "/checkpoint", json={"content": "second"})
    assert second.status_code == 200
    assert (
        client.get(prefix + "/versions").json()["current_version_id"] == second.json()["version_id"]
    )
    note = client.patch(prefix + f"/versions/{version_id}/note", json={"change_note": "history"})
    assert note.status_code == 200
    assert note.json()["change_note"] == "history"
    assert client.get(prefix + f"/versions/{version_id}").json()["content"] == "first"
    restored = client.post(prefix + "/restore", json={"version_id": version_id})
    assert restored.status_code == 200, restored.text
    assert restored.json()["content"] == "first"
    assert client.get(f"/api/sessions/{session_id}").json()["session_data"]["prdContent"] == "first"
    legacy = f"/api/session/{session_id}/documents/prd"
    assert client.get(legacy + "/versions").json() == client.get(prefix + "/versions").json()
    assert (
        client.post(legacy + "/versions/checkpoint", json={"content": "legacy"}).status_code == 200
    )
    assert client.post(legacy + f"/versions/{version_id}/restore").status_code == 200


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/sessions", {"session_data": {}, "unknown": "contract-private-key"}),
        ("/api/conversations/start-stream", {"unknown": "contract-private-key"}),
        ("/api/conversation/start-stream", {"unknown": "contract-private-key"}),
        (
            "/api/conversations/optimize-document-stream",
            {"doc_type": "invalid", "current_content": "x", "instruction": "x"},
        ),
    ],
)
def test_requests_reject_unknown_fields_without_echoing_input(client, path, body):
    response = client.post(path, json=body)
    assert_error(response, 422)
    assert "contract-private-key" not in response.text
    assert '"input"' not in response.text
    assert '"ctx"' not in response.text


def test_document_types_restore_body_and_missing_resources_are_validated(client):
    session_id = create_session(client)
    assert_error(client.get(f"/api/sessions/{session_id}/documents/not-a-document/versions"), 422)
    prefix = f"/api/sessions/{session_id}/documents/prd"
    assert_error(client.post(prefix + "/restore", json={"version_id": "id", "extra": True}), 422)
    assert_error(client.post(prefix + "/restore", json={}), 422)
    assert_error(client.get("/api/sessions/missing/documents"), 404)
    assert_error(client.get(prefix + "/versions/missing"), 404)


def test_config_is_readonly_redacted_and_registry_driven(client, tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text(
        "models:\n  test-model:\n    provider: openai_compatible\n  alias-model:\n    alias_of: test-model\n  default: {}\n"
    )
    resources = client.app.state.resources
    resources.settings = resources.settings.model_copy(update={"models_config_path": path})
    current = client.get("/api/config/current")
    assert current.status_code == 200
    assert current.json()["has_openai_key"] is True
    assert "contract-private-key" not in current.text
    assert "password" not in current.text
    providers = client.get("/api/config/llm-providers").json()["providers"]
    assert {"test-model", "alias-model"} <= set(
        next(p["models"] for p in providers if p["id"] == "openai")
    )
    assert_error(client.post("/api/config/update", json={"openai_api_key": "new-key"}), 405)
    assert resources.settings.openai_api_key.get_secret_value() == "contract-private-key"


def test_openapi_has_only_resource_routes_and_no_version_segment(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/sessions" in paths
    assert "/api/conversations/start-stream" in paths
    assert "/api/jobs" in paths
    assert all("/v1" not in path for path in paths)
    assert all(not path.startswith(("/api/session/", "/api/conversation/")) for path in paths)
    session_id = create_session(client)
    assert_error(client.get(f"/api/sessions/{session_id}/export-delivery"), 400)
    assert_error(client.get(f"/api/session/{session_id}/export-delivery"), 400)


def test_error_handlers_never_echo_generic_errors_or_validation_secrets(client):
    from apps.core.errors import DomainError

    @client.app.get("/api/test-domain")
    async def domain_failure():
        raise DomainError("failed contract-private-key", details={"secret": "contract-private-key"})

    response = client.get("/api/test-domain")
    assert_error(response, 400)
    assert "contract-private-key" not in response.text

    @client.app.get("/api/test-generic")
    async def generic_failure():
        raise RuntimeError("arbitrary-user-data contract-private-key")

    with TestClient(client.app, raise_server_exceptions=False) as safe_client:
        response = safe_client.get("/api/test-generic")
    assert_error(response, 500)
    assert "arbitrary-user-data" not in response.text
    assert "contract-private-key" not in response.text


def test_conversations_use_app_services_and_safe_sse_errors(client):
    class FakeConversation:
        async def start_conversation_stream(self, *args):
            yield {"type": "chunk", "content": "app-owned"}
            raise RuntimeError("private-upstream-request contract-private-key")

    client.app.state.resources.conversation_service = FakeConversation()
    for prefix in ("/api/conversations", "/api/conversation"):
        response = client.post(prefix + "/start-stream", json={})
        assert response.status_code == 200
        assert "app-owned" in response.text
        assert "private-upstream-request" not in response.text
        events = [
            json.loads(line[6:])
            for line in response.text.splitlines()
            if line.startswith("data: {")
        ]
        error = next(event for event in events if event["type"] == "error")
        assert {"code", "message", "request_id", "retryable"} <= error.keys()
        assert response.text.endswith("data: [DONE]\n\n")


def test_questions_use_configured_resources_path(client, tmp_path):
    (tmp_path / "questions_config.json").write_text('{"questions": ["injected"]}')
    resources = client.app.state.resources
    resources.settings = resources.settings.model_copy(update={"resources_dir": tmp_path})
    assert client.get("/api/conversations/questions").json() == {"questions": ["injected"]}


def test_stream_close_cleans_source_without_yielding_in_finally():
    from apps.api.conversations import _make_sse_generator

    closed = []

    async def source():
        try:
            yield {"type": "chunk", "content": "first"}
            await asyncio.sleep(100)
        finally:
            closed.append(True)

    async def run():
        stream = _make_sse_generator(source(), "test")()
        assert "first" in await anext(stream)
        await stream.aclose()

    asyncio.run(run())
    assert closed == [True]


def test_stream_cancellation_cleans_source_without_emitting_terminal_events():
    from apps.api.conversations import _make_sse_generator

    closed = []

    async def run():
        waiting = asyncio.Event()
        emitted = []

        async def source():
            try:
                yield {"type": "chunk", "content": "first"}
                waiting.set()
                await asyncio.Event().wait()
            finally:
                closed.append(True)

        async def consume():
            async for event in _make_sse_generator(source(), "test_cancel")():
                emitted.append(event)

        task = asyncio.create_task(consume())
        await waiting.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(emitted) == 1
        assert "first" in emitted[0]

    asyncio.run(run())
    assert closed == [True]
