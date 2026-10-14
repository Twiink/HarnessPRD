"""从应用状态读取运行时资源，不在模块级创建 Service 或配置。"""

from fastapi import Request

from apps.core.errors import DomainError


def get_resources(request: Request):
    resources = getattr(request.app.state, "resources", None)
    if resources is None or not resources.ready:
        raise DomainError("服务未就绪", code="NOT_READY", status_code=503, retryable=True)
    return resources
