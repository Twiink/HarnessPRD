"""旧对话路径的隐藏适配层，直接复用资源接口处理函数。"""

from fastapi import APIRouter

from apps.api.conversations import router as resource_router

router = APIRouter(prefix="/api/conversation", tags=["conversation"], include_in_schema=False)
for route in resource_router.routes:
    router.add_api_route(
        route.path.removeprefix(resource_router.prefix),
        route.endpoint,
        methods=route.methods,
        response_model=route.response_model,
        include_in_schema=False,
    )
