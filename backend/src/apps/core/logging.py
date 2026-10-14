"""日志到达应用或 SDK 的处理器前，统一脱敏凭证。"""

import logging
import re
import traceback
from collections.abc import Callable

from apps.core.config import Settings, get_settings

_configured_secrets: set[str] = set()
_REDACTED = "[REDACTED]"
_bearer = re.compile(r"(?i)(\bbearer\s+)[^\s\"'<>;,]+")
_url_credentials = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^/\s@]+@")
_secret_assignment = re.compile(
    r"(?i)([\"']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)"
    r"[\"']?\s*[:=]\s*[\"']?)([^\s\"'&,;{}]+)"
)
_provider_key = re.compile(r"\bsk-(?:ant-)?[a-zA-Z0-9_-]+")


def _secrets(value: Settings) -> set[str]:
    return {
        secret.get_secret_value()
        for secret in (value.anthropic_api_key, value.anthropic_auth_token, value.openai_api_key)
        if secret.get_secret_value()
    }


def redact(value: str) -> str:
    secrets = _configured_secrets | _secrets(get_settings())
    for secret in sorted(secrets, key=len, reverse=True):
        value = value.replace(secret, _REDACTED)
    value = _url_credentials.sub(lambda match: match[1] + _REDACTED + "@", value)
    value = _bearer.sub(lambda match: match[1] + _REDACTED, value)
    value = _secret_assignment.sub(lambda match: match[1] + _REDACTED, value)
    return _provider_key.sub(_REDACTED, value)


class _RedactingRecordFactory:
    def __init__(self, wrapped: Callable[..., logging.LogRecord]):
        self.wrapped = wrapped

    def __call__(self, *args, **kwargs) -> logging.LogRecord:
        record = self.wrapped(*args, **kwargs)
        record.msg = redact(record.getMessage())
        record.args = ()
        if record.exc_info:
            record.exc_text = redact("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        if record.stack_info:
            record.stack_info = redact(record.stack_info)
        return record


def configure_logging(settings: Settings) -> None:
    """幂等配置日志；记录工厂同时保护后续添加的日志处理器。"""
    _configured_secrets.update(_secrets(settings))
    factory = logging.getLogRecordFactory()
    if not isinstance(factory, _RedactingRecordFactory):
        logging.setLogRecordFactory(_RedactingRecordFactory(factory))
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger().setLevel(settings.log_level)
