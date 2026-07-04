"""Request ID 中间件 — 生成/回传 X-Request-ID"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.request_context import set_request_id, set_session_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        set_request_id(request_id)

        session_id = request.headers.get("X-Session-ID")
        if session_id:
            set_session_id(session_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
