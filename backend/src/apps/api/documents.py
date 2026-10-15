"""文档历史资源接口，兼容旧路径并共享处理函数。"""

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from apps.api.deps import get_resources
from apps.domain.documents import VersionSourceKind
from apps.services.documents.versions import (
    checkpoint,
    get_documents_by_session,
    get_version,
    list_versions,
    restore_version,
    update_version_note,
)

DocumentType = Literal["prd", "api-docs", "prompts"]
router = APIRouter(prefix="/api/sessions", tags=["documents"])


class DocumentSlotItem(BaseModel):
    doc_type: DocumentType
    document_id: str | None = None
    current_version_id: str | None = None
    current_version_no: int | None = None
    updated_at: str | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentSlotItem]


class VersionListItem(BaseModel):
    id: str
    version_no: int
    source_kind: VersionSourceKind
    created_at: str
    content_preview: str
    is_current: bool
    change_note: str | None = None
    restored_from_version_no: int | None = None


class VersionListResponse(BaseModel):
    doc_type: DocumentType
    document_id: str | None = None
    current_version_id: str | None = None
    versions: list[VersionListItem]


class VersionDetailResponse(BaseModel):
    id: str
    version_no: int
    source_kind: VersionSourceKind
    content: str
    source_job_id: str | None = None
    parent_version_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    is_current: bool


class CheckpointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str | None = None
    change_note: str | None = None


class RestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: str = Field(min_length=1, max_length=200)


class CheckpointResponse(BaseModel):
    version_id: str
    version_no: int
    document_id: str


class RestoreResponse(CheckpointResponse):
    content: str


class UpdateVersionNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change_note: str | None = None


class UpdateVersionNoteResponse(BaseModel):
    version_id: str
    version_no: int
    change_note: str | None = None


@router.get("/{session_id}/documents", response_model=DocumentListResponse)
def api_list_documents(session_id: str, resources=Depends(get_resources)):
    return {"items": get_documents_by_session(session_id)}


@router.get("/{session_id}/documents/{doc_type}/versions", response_model=VersionListResponse)
def api_list_versions(session_id: str, doc_type: DocumentType, resources=Depends(get_resources)):
    return list_versions(session_id, doc_type)


@router.get(
    "/{session_id}/documents/{doc_type}/versions/{version_id}", response_model=VersionDetailResponse
)
def api_get_version(
    session_id: str, doc_type: DocumentType, version_id: str, resources=Depends(get_resources)
):
    return get_version(session_id, doc_type, version_id)


@router.post("/{session_id}/documents/{doc_type}/checkpoint", response_model=CheckpointResponse)
def api_checkpoint(
    session_id: str,
    doc_type: DocumentType,
    body: CheckpointRequest,
    resources=Depends(get_resources),
):
    return checkpoint(session_id, doc_type, content=body.content, change_note=body.change_note)


@router.post("/{session_id}/documents/{doc_type}/restore", response_model=RestoreResponse)
def api_restore_version(
    session_id: str, doc_type: DocumentType, body: RestoreRequest, resources=Depends(get_resources)
):
    return restore_version(session_id, doc_type, body.version_id)


@router.patch(
    "/{session_id}/documents/{doc_type}/versions/{version_id}/note",
    response_model=UpdateVersionNoteResponse,
)
def api_update_version_note(
    session_id: str,
    doc_type: DocumentType,
    version_id: str,
    body: UpdateVersionNoteRequest,
    resources=Depends(get_resources),
):
    data = update_version_note(session_id, doc_type, version_id, change_note=body.change_note)
    return {
        "version_id": data["id"],
        "version_no": data["version_no"],
        "change_note": (data.get("metadata") or {}).get("change_note"),
    }
