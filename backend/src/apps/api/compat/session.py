"""隐藏的旧方案路径，复用方案资源处理函数。"""

from fastapi import APIRouter

from apps.api.sessions import (
    OkResponse,
    SaveSessionResponse,
    SessionDetailResponse,
    SessionListResponse,
    api_delete_session,
    api_export_delivery,
    api_get_session,
    api_list_sessions,
    api_save_session,
)

router = APIRouter(prefix="/api/session", tags=["session"], include_in_schema=False)
router.add_api_route(
    "/list", api_list_sessions, methods=["GET"], response_model=SessionListResponse
)
router.add_api_route(
    "/save", api_save_session, methods=["POST"], response_model=SaveSessionResponse
)
router.add_api_route("/{session_id}/export-delivery", api_export_delivery, methods=["GET"])
router.add_api_route(
    "/{session_id}", api_get_session, methods=["GET"], response_model=SessionDetailResponse
)
router.add_api_route(
    "/{session_id}", api_delete_session, methods=["DELETE"], response_model=OkResponse
)
