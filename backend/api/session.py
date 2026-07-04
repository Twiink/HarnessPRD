"""方案持久化 API"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from services.delivery_export_service import build_delivery_zip
from services.http_headers import build_attachment_content_disposition
from services.session_service import (
    delete_session,
    get_session,
    list_sessions,
    save_session,
)

router = APIRouter(prefix="/api/session", tags=["session"])


class SessionSummary(BaseModel):
    id: str
    title: str
    entry_mode: Optional[str] = None
    current_stage: Optional[str] = None
    status: Optional[str] = None
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    items: List[SessionSummary]


class SaveSessionRequest(BaseModel):
    id: Optional[str] = None
    session_data: Dict[str, Any]


class SaveSessionResponse(BaseModel):
    id: str
    title: str


class SessionDetailResponse(BaseModel):
    id: str
    title: str
    entry_mode: Optional[str] = None
    current_stage: Optional[str] = None
    status: Optional[str] = None
    created_at: str
    updated_at: str
    session_data: Dict[str, Any]


class OkResponse(BaseModel):
    ok: bool = True


@router.get("/list", response_model=SessionListResponse)
async def api_list_sessions():
    items = list_sessions()
    return SessionListResponse(items=items)


@router.get("/{session_id}/export-delivery")
async def api_export_delivery(session_id: str):
    try:
        data, filename = build_delivery_zip(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="方案不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": build_attachment_content_disposition(filename)},
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def api_get_session(session_id: str):
    try:
        return get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="方案不存在")


@router.post("/save", response_model=SaveSessionResponse)
async def api_save_session(request: SaveSessionRequest):
    try:
        return save_session(request.session_data, request.id)
    except KeyError:
        raise HTTPException(status_code=404, detail="方案不存在")


@router.delete("/{session_id}", response_model=OkResponse)
async def api_delete_session(session_id: str):
    try:
        delete_session(session_id)
        return OkResponse()
    except KeyError:
        raise HTTPException(status_code=404, detail="方案不存在")
