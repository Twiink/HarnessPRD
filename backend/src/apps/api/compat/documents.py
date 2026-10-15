"""历史文档路径适配，复用正式资源用例和响应合同。"""

from fastapi import APIRouter, Depends
from apps.api.deps import get_resources
from apps.api.documents import (
    DocumentType,
    DocumentListResponse,
    VersionListResponse,
    VersionDetailResponse,
    CheckpointResponse,
    RestoreRequest,
    RestoreResponse,
    UpdateVersionNoteResponse,
    api_list_documents,
    api_list_versions,
    api_get_version,
    api_checkpoint,
    api_restore_version,
    api_update_version_note,
)

router = APIRouter(prefix="/api/session", tags=["documents"], include_in_schema=False)


def legacy_restore_version(
    session_id: str, doc_type: DocumentType, version_id: str, resources=Depends(get_resources)
):
    return api_restore_version(
        session_id, doc_type, RestoreRequest(version_id=version_id), resources
    )


router.add_api_route(
    "/{session_id}/documents",
    api_list_documents,
    methods=["GET"],
    response_model=DocumentListResponse,
)
router.add_api_route(
    "/{session_id}/documents/{doc_type}/versions",
    api_list_versions,
    methods=["GET"],
    response_model=VersionListResponse,
)
router.add_api_route(
    "/{session_id}/documents/{doc_type}/versions/{version_id}",
    api_get_version,
    methods=["GET"],
    response_model=VersionDetailResponse,
)
router.add_api_route(
    "/{session_id}/documents/{doc_type}/versions/checkpoint",
    api_checkpoint,
    methods=["POST"],
    response_model=CheckpointResponse,
)
router.add_api_route(
    "/{session_id}/documents/{doc_type}/versions/{version_id}/restore",
    legacy_restore_version,
    methods=["POST"],
    response_model=RestoreResponse,
)
router.add_api_route(
    "/{session_id}/documents/{doc_type}/versions/{version_id}/note",
    api_update_version_note,
    methods=["PATCH"],
    response_model=UpdateVersionNoteResponse,
)
