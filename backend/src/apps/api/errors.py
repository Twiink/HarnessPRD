"""HTTP 边界统一错误协议，响应字段经过脱敏。"""

import logging
import sqlite3
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from apps.core.errors import DomainError
from apps.core.logging import redact
from apps.core.request_context import get_request_id

logger = logging.getLogger(__name__)


def _safe(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {redact(str(key)): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact(str(value))


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details=None,
    headers=None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    body: dict[str, Any] = {
        "code": code,
        "message": redact(message),
        "request_id": request_id,
        "retryable": retryable,
    }
    if details is not None:
        body["details"] = _safe(details)
    response_headers = dict(headers or {})
    if request_id:
        response_headers["X-Request-ID"] = request_id
    return JSONResponse(status_code=status_code, content=body, headers=response_headers)


async def domain_error_handler(request: Request, exc: DomainError):
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        retryable=exc.retryable,
        details=exc.details,
    )


async def http_error_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    message = (
        detail
        if isinstance(detail, str)
        else (detail.get("message", "请求失败") if isinstance(detail, dict) else "请求失败")
    )
    codes = {
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "INVALID_REQUEST",
        503: "NOT_READY",
    }
    return error_response(
        request,
        status_code=exc.status_code,
        code=codes.get(exc.status_code, "HTTP_ERROR"),
        message=message,
        retryable=exc.status_code == 503,
        headers=exc.headers,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError):
    # 自定义校验器可能在 msg 与 ctx 中携带凭据，只返回字段位置、错误类型和固定提示。
    details = [{"loc": error["loc"], "type": error["type"]} for error in exc.errors()]
    return error_response(
        request, status_code=422, code="VALIDATION_ERROR", message="请求字段无效", details=details
    )


async def key_error_handler(request: Request, exc: KeyError):
    return error_response(request, status_code=404, code="NOT_FOUND", message="资源不存在")


async def unexpected_error_handler(request: Request, exc: Exception):
    logger.error(
        "API request failed request_id=%s error_type=%s",
        getattr(request.state, "request_id", None),
        type(exc).__name__,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return error_response(request, status_code=500, code="INTERNAL_ERROR", message="服务内部错误")


async def sqlite_error_handler(request: Request, exc: sqlite3.Error):
    code = getattr(exc, "sqlite_errorcode", 0) or 0
    # SQLite 的主结果码 BUSY=5、LOCKED=6；Python 3.10 尚未导出对应常量。
    if code & 0xFF in (5, 6) or str(exc) in (
        "database is locked",
        "database table is locked",
    ):
        return error_response(
            request,
            status_code=503,
            code="DB_BUSY",
            message="数据库暂时繁忙，请稍后重试",
            retryable=True,
            headers={"Retry-After": "1"},
        )
    return await unexpected_error_handler(request, exc)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(KeyError, key_error_handler)
    app.add_exception_handler(sqlite3.Error, sqlite_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
