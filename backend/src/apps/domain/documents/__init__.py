"""Document types and errors shared by services and API adapters."""

from enum import Enum

from apps.core.errors import DomainError
from apps.domain.sessions import SessionNotFoundError


class DocumentType(str, Enum):
    PRD = "prd"
    API_DOCS = "api-docs"
    PROMPTS = "prompts"


VALID_DOC_TYPES = tuple(item.value for item in DocumentType)


class VersionSourceKind(str, Enum):
    GENERATE = "generate"
    OPTIMIZE = "optimize"
    AUTO_SAVE = "auto_save"
    CHECKPOINT = "checkpoint"
    RESTORE = "restore"
    IMPORT = "import"


class DocumentVersionError(DomainError):
    pass


class InvalidDocTypeError(DocumentVersionError):
    def __init__(self, doc_type: str):
        super().__init__(
            "无效的文档类型", code="INVALID_DOCUMENT_TYPE", details={"doc_type": doc_type}
        )


class VersionNotFoundError(DocumentVersionError, KeyError):
    def __init__(self, version_id: str):
        super().__init__(
            "历史记录不存在",
            code="VERSION_NOT_FOUND",
            status_code=404,
            details={"version_id": version_id},
        )


class CheckpointError(DocumentVersionError):
    def __init__(self, message: str):
        super().__init__(message, code="CHECKPOINT_INVALID")


class RestoreError(DocumentVersionError):
    def __init__(self, message: str):
        super().__init__(message, code="RESTORE_INVALID")
