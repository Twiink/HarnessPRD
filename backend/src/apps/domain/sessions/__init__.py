"""Session domain errors, independent of transport and persistence."""

from apps.core.errors import DomainError


class SessionNotFoundError(DomainError, KeyError):
    def __init__(self, session_id: str):
        super().__init__(
            "方案不存在",
            code="SESSION_NOT_FOUND",
            status_code=404,
            details={"session_id": session_id},
        )


class SessionJobConflictError(DomainError):
    def __init__(self, job_id: str):
        super().__init__(
            "方案仍有进行中的任务，请先取消并等待任务结束",
            code="JOB_CONFLICT",
            status_code=409,
            details={"job_id": job_id},
        )
