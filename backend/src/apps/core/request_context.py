"""HTTP 请求上下文 — request_id / session_id"""

from contextvars import ContextVar
from typing import Optional

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)


def get_request_id() -> Optional[str]:
    return request_id_var.get()


def get_session_id() -> Optional[str]:
    return session_id_var.get()


def set_request_id(request_id: str) -> None:
    request_id_var.set(request_id)


def set_session_id(session_id: str) -> None:
    session_id_var.set(session_id)
