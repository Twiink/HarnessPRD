"""Generation Job API"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.schemas import CreateJobRequest, JobDetailResponse, CreateJobResponse
from services.job_bus import subscribe, unsubscribe
from services.job_service import JobConflictError, create_job, get_job
from services.job_runner import schedule_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


def _job_to_response(job: Dict[str, Any]) -> JobDetailResponse:
    return JobDetailResponse(
        id=job["id"],
        session_id=job["session_id"],
        artifact=job["artifact"],
        status=job["status"],
        phase=job["phase"],
        draft_content=job.get("draft_content") or "",
        review=job.get("review"),
        result=job.get("result"),
        error=job.get("error"),
    )


def _build_snapshot_event(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "snapshot",
        "status": job["status"],
        "phase": job["phase"],
        "artifact": job["artifact"],
        "draft_content": job.get("draft_content") or "",
        "review": job.get("review"),
    }


def _sse_line(event: Dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("", response_model=CreateJobResponse)
async def api_create_job(request: CreateJobRequest):
    from services.delivery_guards import assert_can_create_job
    from services.session_service import load_session_data_raw

    try:
        session_data = load_session_data_raw(request.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="方案不存在") from exc

    assert_can_create_job(session_data, request.artifact, request.payload)

    try:
        job_id = create_job(request.session_id, request.artifact, request.payload)
    except JobConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": "该方案已有进行中的任务", "job_id": exc.job_id},
        ) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="方案不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    schedule_job(job_id, request.artifact)
    return CreateJobResponse(job_id=job_id)


@router.get("/{job_id}", response_model=JobDetailResponse)
async def api_get_job(job_id: str):
    try:
        return _job_to_response(get_job(job_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc


@router.get("/{job_id}/stream")
async def api_stream_job(job_id: str):
    try:
        job = get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc

    async def generate():
        current = get_job(job_id)
        yield _sse_line(_build_snapshot_event(current))

        if current["status"] == "completed":
            if current.get("result_json"):
                try:
                    yield _sse_line(json.loads(current["result_json"]))
                except json.JSONDecodeError:
                    yield _sse_line({"type": "done", "content": current.get("draft_content") or ""})
            else:
                yield _sse_line({"type": "done", "content": current.get("draft_content") or ""})
            yield "data: [DONE]\n\n"
            return

        if current["status"] == "failed":
            yield _sse_line(
                {
                    "type": "error",
                    "message": current.get("error") or "生成失败",
                }
            )
            yield "data: [DONE]\n\n"
            return

        queue = subscribe(job_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300.0)
                except asyncio.TimeoutError:
                    refreshed = get_job(job_id)
                    if refreshed["status"] in ("completed", "failed"):
                        break
                    continue

                yield _sse_line(event)
                if event.get("type") == "error":
                    break
                if event.get("type") == "run_summary":
                    break

            final = get_job(job_id)
            if final["status"] == "completed" and final.get("result_json"):
                # done / run_summary 可能已由 runner 推送
                pass
        finally:
            unsubscribe(job_id, queue)

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers=SSE_HEADERS)
