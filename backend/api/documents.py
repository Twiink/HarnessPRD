"""文档版本 API"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.document_version_service import (
    CheckpointError,
    InvalidDocTypeError,
    RestoreError,
    SessionNotFoundError,
    VersionNotFoundError,
    checkpoint,
    get_current_content_for_doc_type,
    get_documents_by_session,
    get_version,
    list_versions,
    restore_version,
    update_version_note,
)
from services.session_service import sync_session_mirror_for_doc_type

router = APIRouter(prefix="/api/session", tags=["documents"])


class DocumentSlotItem(BaseModel):
    doc_type: str
    document_id: Optional[str] = None
    current_version_id: Optional[str] = None
    current_version_no: Optional[int] = None
    updated_at: Optional[str] = None


class DocumentListResponse(BaseModel):
    items: List[DocumentSlotItem]


class VersionListItem(BaseModel):
    id: str
    version_no: int
    source_kind: str
    created_at: str
    content_preview: str
    is_current: bool
    change_note: Optional[str] = None
    restored_from_version_no: Optional[int] = None


class VersionListResponse(BaseModel):
    doc_type: str
    document_id: Optional[str] = None
    current_version_id: Optional[str] = None
    versions: List[VersionListItem]


class VersionDetailResponse(BaseModel):
    id: str
    version_no: int
    source_kind: str
    content: str
    source_job_id: Optional[str] = None
    parent_version_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: str
    is_current: bool


class CheckpointRequest(BaseModel):
    content: Optional[str] = None
    change_note: Optional[str] = None


class CheckpointResponse(BaseModel):
    version_id: str
    version_no: int
    document_id: str


class RestoreResponse(BaseModel):
    version_id: str
    version_no: int
    document_id: str
    content: str


class UpdateVersionNoteRequest(BaseModel):
    change_note: Optional[str] = None


class UpdateVersionNoteResponse(BaseModel):
    version_id: str
    version_no: int
    change_note: Optional[str] = None


@router.get("/{session_id}/documents", response_model=DocumentListResponse)
async def api_list_documents(session_id: str):
    try:
        items = get_documents_by_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="方案不存在")
    return DocumentListResponse(items=items)


@router.get("/{session_id}/documents/{doc_type}/versions", response_model=VersionListResponse)
async def api_list_versions(session_id: str, doc_type: str):
    try:
        return list_versions(session_id, doc_type)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="方案不存在")
    except InvalidDocTypeError:
        raise HTTPException(status_code=400, detail="无效的文档类型")


@router.get(
    "/{session_id}/documents/{doc_type}/versions/{version_id}",
    response_model=VersionDetailResponse,
)
async def api_get_version(session_id: str, doc_type: str, version_id: str):
    try:
        data = get_version(session_id, doc_type, version_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="方案不存在")
    except InvalidDocTypeError:
        raise HTTPException(status_code=400, detail="无效的文档类型")
    except VersionNotFoundError:
        raise HTTPException(status_code=404, detail="版本不存在")
    return VersionDetailResponse(
        id=data["id"],
        version_no=data["version_no"],
        source_kind=data["source_kind"],
        content=data["content"],
        source_job_id=data.get("source_job_id"),
        parent_version_id=data.get("parent_version_id"),
        metadata=data.get("metadata") or {},
        created_at=data["created_at"],
        is_current=data["is_current"],
    )


@router.post(
    "/{session_id}/documents/{doc_type}/versions/checkpoint",
    response_model=CheckpointResponse,
)
async def api_checkpoint(session_id: str, doc_type: str, body: CheckpointRequest):
    try:
        result = checkpoint(
            session_id,
            doc_type,
            content=body.content,
            change_note=body.change_note,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="方案不存在")
    except InvalidDocTypeError:
        raise HTTPException(status_code=400, detail="无效的文档类型")
    except CheckpointError as e:
        raise HTTPException(status_code=400, detail=str(e))
    mirror_content = body.content
    if mirror_content is None:
        mirror_content = get_current_content_for_doc_type(session_id, doc_type) or ""
    sync_session_mirror_for_doc_type(session_id, doc_type, mirror_content)
    return CheckpointResponse(**result)


@router.post(
    "/{session_id}/documents/{doc_type}/versions/{version_id}/restore",
    response_model=RestoreResponse,
)
async def api_restore_version(session_id: str, doc_type: str, version_id: str):
    try:
        result = restore_version(session_id, doc_type, version_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="方案不存在")
    except InvalidDocTypeError:
        raise HTTPException(status_code=400, detail="无效的文档类型")
    except VersionNotFoundError:
        raise HTTPException(status_code=404, detail="版本不存在")
    except RestoreError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sync_session_mirror_for_doc_type(session_id, doc_type, result["content"])
    return RestoreResponse(**result)


@router.patch(
    "/{session_id}/documents/{doc_type}/versions/{version_id}/note",
    response_model=UpdateVersionNoteResponse,
)
async def api_update_version_note(
    session_id: str,
    doc_type: str,
    version_id: str,
    body: UpdateVersionNoteRequest,
):
    try:
        data = update_version_note(
            session_id,
            doc_type,
            version_id,
            change_note=body.change_note,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="方案不存在")
    except InvalidDocTypeError:
        raise HTTPException(status_code=400, detail="无效的文档类型")
    except VersionNotFoundError:
        raise HTTPException(status_code=404, detail="版本不存在")
    meta = data.get("metadata") or {}
    return UpdateVersionNoteResponse(
        version_id=data["id"],
        version_no=data["version_no"],
        change_note=meta.get("change_note"),
    )
