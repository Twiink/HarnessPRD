"""方案资源接口及旧路径共用的处理函数。"""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from apps.api.deps import get_resources
from apps.core.errors import DomainError
from apps.services.delivery_export_service import build_delivery_zip
from apps.services.http_headers import build_attachment_content_disposition
from apps.services.session_service import (
    delete_session,
    get_session,
    list_sessions,
    save_session,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_data: dict[str, Any]


class SaveSessionRequest(SessionRequest):
    id: str | None = None


class SessionSummary(BaseModel):
    id: str
    title: str
    entry_mode: str | None = None
    current_stage: str | None = None
    status: str | None = None
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    items: list[SessionSummary]


class SaveSessionResponse(BaseModel):
    id: str
    title: str


class SessionDetailResponse(SessionSummary):
    session_data: dict[str, Any]


class OkResponse(BaseModel):
    ok: bool = True


def api_save_session(body: SaveSessionRequest, resources=Depends(get_resources)):
    return save_session(body.session_data, body.id)


@router.post("", response_model=SessionDetailResponse, status_code=201)
def api_create_session(body: SessionRequest, resources=Depends(get_resources)):
    with resources.database.transaction():
        saved = save_session(body.session_data)
        return get_session(saved["id"])


@router.get("", response_model=SessionListResponse)
def api_list_sessions(resources=Depends(get_resources)):
    return {"items": list_sessions()}


@router.get("/{session_id}/export-delivery")
def api_export_delivery(session_id: str, resources=Depends(get_resources)):
    try:
        data, filename = build_delivery_zip(session_id)
    except ValueError as exc:
        raise DomainError("没有可导出的文档内容", code="EXPORT_EMPTY") from exc
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": build_attachment_content_disposition(filename)},
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
def api_get_session(session_id: str, resources=Depends(get_resources)):
    return get_session(session_id)


@router.patch("/{session_id}", response_model=SessionDetailResponse)
def api_patch_session(session_id: str, body: SessionRequest, resources=Depends(get_resources)):
    with resources.database.transaction():
        current = get_session(session_id)
        save_session({**current["session_data"], **body.session_data}, session_id)
        return get_session(session_id)


@router.delete("/{session_id}", response_model=OkResponse)
def api_delete_session(session_id: str, resources=Depends(get_resources)):
    delete_session(session_id)
    return OkResponse()
