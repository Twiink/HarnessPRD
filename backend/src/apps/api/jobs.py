"""任务资源 API：提交持久化队列、取消、状态和事件续传。"""

from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from apps.api.deps import get_resources
from apps.core.errors import DomainError
from apps.domain.jobs import Artifact, JobStatus

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=200)
    artifact: Artifact
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class CreateJobResponse(BaseModel):
    job_id: str


class JobDetailResponse(BaseModel):
    id: str
    session_id: str
    artifact: Artifact
    status: JobStatus
    phase: str
    draft_content: str = ""
    review: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None
    attempt_count: int
    cancel_requested: bool
    started_at: str | None = None
    finished_at: str | None = None


@router.post("", response_model=CreateJobResponse, status_code=202)
async def create_job(
    body: CreateJobRequest,
    resources=Depends(get_resources),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if body.idempotency_key and idempotency_header and body.idempotency_key != idempotency_header:
        raise DomainError("请求中的幂等键不一致", code="INVALID_IDEMPOTENCY_KEY", status_code=422)
    job_id = await resources.job_manager.submit(
        body.session_id,
        body.artifact.value,
        body.payload,
        body.idempotency_key or idempotency_header,
    )
    return CreateJobResponse(job_id=job_id)


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: str, resources=Depends(get_resources)):
    return resources.job_manager.jobs.get(job_id)


@router.post("/{job_id}/cancel", response_model=JobDetailResponse)
async def cancel_job(job_id: str, resources=Depends(get_resources)):
    return await resources.job_manager.cancel(job_id)


@router.get("/{job_id}/events")
def get_events(
    job_id: str,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=1000),
    resources=Depends(get_resources),
):
    resources.job_manager.jobs.get(job_id)
    items = resources.events.repository.list(job_id, after, limit)
    return {"items": items, "next_after": items[-1]["sequence"] if items else after}


@router.get("/{job_id}/stream")
async def stream_job(
    job_id: str,
    after: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    resources=Depends(get_resources),
):
    resources.job_manager.jobs.get(job_id)
    if last_event_id is not None:
        if not last_event_id.isascii() or not last_event_id.isdigit() or len(last_event_id) > 18:
            raise DomainError("无效的事件 ID", code="INVALID_EVENT_ID", status_code=422)
        after = max(after, int(last_event_id))
    return StreamingResponse(
        resources.events.stream(job_id, after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
