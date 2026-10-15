"""纯 ASGI 请求上下文，覆盖 SSE 生命周期并在请求结束后恢复上下文。"""

import re
import uuid

from starlette.middleware.cors import CORSMiddleware

from apps.core.config import settings_context
from apps.core.request_context import request_id_var, session_id_var
from apps.db.connection import database_context
from apps.llm.runtime import llm_runtime_context


class RequestIdMiddleware:
    def __init__(self, app, fastapi_app):
        self.app = app
        self.fastapi_app = fastapi_app
        self._cors = None
        self._settings = None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        candidate = headers.get(b"x-request-id", b"").decode("latin-1")
        request_id = (
            candidate
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", candidate)
            else f"req_{uuid.uuid4().hex[:12]}"
        )
        request_token = request_id_var.set(request_id)
        session_token = session_id_var.set(
            headers.get(b"x-session-id", b"").decode("latin-1") or None
        )
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                response_headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                message = {
                    **message,
                    "headers": response_headers + [(b"x-request-id", request_id.encode())],
                }
            await send(message)

        try:
            resources = getattr(self.fastapi_app.state, "resources", None)
            if resources is None:
                await self.app(scope, receive, send_with_id)
            else:
                if self._settings is not resources.settings:
                    self._settings = resources.settings
                    self._cors = CORSMiddleware(
                        self.app,
                        allow_origins=resources.settings.cors_origins_list,
                        allow_credentials=False,
                        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                        allow_headers=[
                            "Content-Type",
                            "Last-Event-ID",
                            "Idempotency-Key",
                            "X-Request-ID",
                            "X-Session-ID",
                        ],
                        expose_headers=["X-Request-ID"],
                    )
                with (
                    settings_context(resources.settings),
                    database_context(resources.database),
                    llm_runtime_context(resources.llm_runtime),
                ):
                    await self._cors(scope, receive, send_with_id)
        finally:
            request_id_var.reset(request_token)
            session_id_var.reset(session_token)
