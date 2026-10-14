"""业务异常协议，不依赖 HTTP 框架。"""

from typing import Any


class DomainError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "INVALID_REQUEST",
        status_code: int = 400,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.retryable = retryable
        self.details = details
