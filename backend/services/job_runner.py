"""Generation Job 后台执行 — 复用 document_service generator"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from core.request_context import get_request_id
from services.document_service import DocumentService
from services.job_bus import publish
from services.job_service import get_job, set_draft_content, update_job
from services.llm_metrics import RunMetricsCollector, log_run_summary
from services.skill_loader import bundle_to_injected_meta, load_skill_bundle
from services.document_version_service import (
    ARTIFACT_TO_DOC_TYPE,
    build_metadata_from_job,
    get_current_version,
    patch_current_metadata,
    seed_context_documents_from_payload,
    sync_from_job,
)
from services.session_service import (
    sync_session_active_job,
    sync_session_active_optimize_job,
    sync_session_on_job_complete,
    sync_session_on_job_failed,
    sync_session_on_optimize_complete,
    sync_session_on_optimize_failed,
)

logger = logging.getLogger(__name__)

document_service = DocumentService()

PHASE_FROM_EVENT = {
    "writer_started": "writing",
    "review_started": "reviewing",
    "rewrite_started": "rewriting",
}

PERSIST_INTERVAL_SEC = 0.5


def _map_run_type(artifact: str) -> str:
    return {
        "prd": "generate_prd_from_summary_stream",
        "api-docs": "generate_api_docs_stream",
        "prompts": "generate_prompts_stream",
        "optimize-prd": "optimize_document",
        "optimize-api-docs": "optimize_document",
        "optimize-prompts": "optimize_document",
    }.get(artifact, f"job_{artifact}")


async def _maybe_persist_draft(
    job_id: str,
    draft: str,
    last_persist_at: float,
    force: bool = False,
) -> float:
    now = time.monotonic()
    if force or (now - last_persist_at) >= PERSIST_INTERVAL_SEC:
        set_draft_content(job_id, draft)
        return now
    return last_persist_at


async def _finalize_document_for_job(job_id: str, run_summary: Optional[Dict[str, Any]] = None) -> None:
    """正文已在 done / failed 时写入；此处仅把 run_summary、review、quality_gate 等补到 current metadata。"""
    from services.quality_gate import build_gate_context_from_job, run_quality_gate
    from services.session_service import load_session_data_raw

    job = get_job(job_id)
    artifact = job["artifact"]
    doc_type = ARTIFACT_TO_DOC_TYPE.get(artifact)
    if not doc_type:
        return
    content = job.get("draft_content") or ""
    if not content.strip():
        return
    try:
        session_data = load_session_data_raw(job["session_id"])
    except KeyError:
        session_data = {}
    gate_context = build_gate_context_from_job(job, session_data)
    quality_gate = run_quality_gate(doc_type, content, gate_context)
    job_row = {
        "review": job.get("review"),
        "review_json": json.dumps(job["review"], ensure_ascii=False) if job.get("review") else None,
    }
    metadata = build_metadata_from_job(
        job_row,
        run_summary=run_summary,
        failed=job.get("status") == "failed",
    )
    metadata["quality_gate"] = quality_gate
    patch_current_metadata(job["session_id"], doc_type, metadata)


def _sync_document_before_session(
    session_id: str,
    artifact: str,
    content: str,
    review: Optional[Dict[str, Any]] = None,
    failed: bool = False,
    job_id: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    if not content.strip():
        return
    sync_from_job(
        session_id,
        artifact,
        content,
        review=review,
        failed=failed,
        source_job_id=job_id,
        extra_metadata=extra_metadata,
    )


def _build_derived_from(
    session_id: str,
    artifact: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    derived: Dict[str, Any] = {}
    prd_current = get_current_version(session_id, "prd")
    if prd_current:
        derived["prd_version_id"] = prd_current["id"]
        derived["prd_version_no"] = prd_current["version_no"]
    if artifact == "prompts":
        api_docs_content = (payload.get("api_docs_content") or "").strip()
        if not api_docs_content:
            derived["api_docs_skipped"] = True
        else:
            api_current = get_current_version(session_id, "api-docs")
            if api_current:
                derived["api_docs_version_id"] = api_current["id"]
                derived["api_docs_version_no"] = api_current["version_no"]
    return derived


async def _finish_run_summary(
    job_id: str,
    run: RunMetricsCollector,
    revision_applied: Optional[bool],
    artifact: Optional[str] = None,
) -> None:
    if artifact:
        try:
            bundle = load_skill_bundle(artifact)
            meta = bundle_to_injected_meta(bundle)
            if meta:
                run.set_injected_skills(meta)
        except Exception as exc:
            logger.warning("加载 injected_skills 失败 (%s): %s", artifact, exc)
    summary = run.finish(revision_applied=revision_applied)
    event = {"type": "run_summary", **summary.to_dict()}
    await publish(job_id, event)
    log_run_summary(summary)
    await _finalize_document_for_job(job_id, run_summary=summary.to_dict())


async def run_prd_job(job_id: str) -> None:
    job = get_job(job_id)
    payload = json.loads(job["payload_json"])
    session_id = job["session_id"]
    update_job(job_id, status="running", phase="writing")
    sync_session_active_job(session_id, job_id, "prd")

    run = RunMetricsCollector.start(run_type=_map_run_type("prd"))
    revision_applied: Optional[bool] = None
    draft = ""
    last_persist = 0.0

    try:
        async for event in document_service.generate_prd_from_summary_stream(
            payload["requirements_summary"],
            payload.get("conversation_messages"),
        ):
            et = event.get("type")

            if et == "text_delta":
                draft += event.get("content") or ""
                last_persist = await _maybe_persist_draft(job_id, draft, last_persist)

            elif et == "phase":
                phase_name = event.get("phase") or ""
                if phase_name == "rewrite_started":
                    current = get_job(job_id)
                    update_job(
                        job_id,
                        phase="rewriting",
                        previous_draft=current["draft_content"],
                        draft_content="",
                    )
                    draft = ""
                    last_persist = 0.0
                elif phase_name in PHASE_FROM_EVENT:
                    update_job(job_id, phase=PHASE_FROM_EVENT[phase_name])
                last_persist = await _maybe_persist_draft(job_id, draft, last_persist, force=True)

            elif et == "review":
                review_content = event.get("content")
                update_job(
                    job_id,
                    phase="reviewing",
                    review_json=json.dumps(review_content, ensure_ascii=False),
                )
                last_persist = await _maybe_persist_draft(job_id, draft, last_persist, force=True)

            elif et == "done":
                final_prd = event.get("final_prd") or draft
                review = event.get("review")
                revision_applied = event.get("revision_applied")
                update_job(
                    job_id,
                    status="completed",
                    phase="done",
                    draft_content=final_prd,
                    result_json=json.dumps(event, ensure_ascii=False),
                    review_json=json.dumps(review, ensure_ascii=False) if review else None,
                )
                _sync_document_before_session(
                    session_id, "prd", final_prd, review=review, job_id=job_id
                )
                sync_session_on_job_complete(session_id, "prd", final_prd, review)
                draft = final_prd

            await publish(job_id, event)

        job_after = get_job(job_id)
        if job_after["status"] == "running":
            update_job(job_id, status="completed", phase="done", draft_content=draft)
            _sync_document_before_session(session_id, "prd", draft, job_id=job_id)
            sync_session_on_job_complete(session_id, "prd", draft)

    except Exception as exc:
        logger.exception("PRD job failed: %s", job_id)
        await _maybe_persist_draft(job_id, draft, last_persist, force=True)
        update_job(job_id, status="failed", error=str(exc))
        _sync_document_before_session(session_id, "prd", draft, failed=True, job_id=job_id)
        sync_session_on_job_failed(session_id, "prd", draft)
        await publish(
            job_id,
            {
                "type": "error",
                "message": str(exc),
                "request_id": get_request_id(),
            },
        )
    finally:
        job_final = get_job(job_id)
        if job_final.get("result_json"):
            try:
                done_event = json.loads(job_final["result_json"])
                revision_applied = done_event.get("revision_applied")
            except json.JSONDecodeError:
                pass
        await _finish_run_summary(job_id, run, revision_applied, artifact="prd")


async def run_api_docs_job(job_id: str) -> None:
    await _run_chunk_job(
        job_id,
        "api-docs",
        lambda payload: document_service.generate_api_docs_stream(
            payload["prd_content"],
            payload.get("conversation_messages") or [],
        ),
    )


async def run_prompts_job(job_id: str) -> None:
    await _run_chunk_job(
        job_id,
        "prompts",
        lambda payload: document_service.generate_prompts_stream(
            payload["prd_content"],
            payload.get("api_docs_content") or "",
        ),
    )


async def run_optimize_job(job_id: str) -> None:
    job = get_job(job_id)
    artifact = job["artifact"]
    payload = json.loads(job["payload_json"])
    session_id = job["session_id"]
    update_job(job_id, status="running", phase="generating")
    sync_session_active_optimize_job(session_id, job_id)

    run = RunMetricsCollector.start(run_type=_map_run_type(artifact))
    draft = ""
    last_persist = 0.0

    try:
        async for event in document_service.optimize_document_stream(
            payload["doc_type"],
            payload["current_content"],
            payload["instruction"],
            payload.get("context") or "",
        ):
            et = event.get("type")
            if et in ("chunk", "text_delta"):
                draft += event.get("content") or ""
                last_persist = await _maybe_persist_draft(job_id, draft, last_persist)
                await publish(job_id, {"type": "text_delta", "content": event.get("content") or ""})
            elif et == "done":
                update_job(
                    job_id,
                    status="completed",
                    phase="done",
                    draft_content=draft,
                    result_json=json.dumps({"type": "done", "content": draft}, ensure_ascii=False),
                )
                _sync_document_before_session(session_id, artifact, draft, job_id=job_id)
                sync_session_on_optimize_complete(session_id, artifact, draft)
                await publish(job_id, {"type": "done", "content": draft})
            else:
                await publish(job_id, event)

        job_after = get_job(job_id)
        if job_after["status"] == "running":
            update_job(job_id, status="completed", phase="done", draft_content=draft)
            _sync_document_before_session(session_id, artifact, draft, job_id=job_id)
            sync_session_on_optimize_complete(session_id, artifact, draft)
            await publish(job_id, {"type": "done", "content": draft})

    except Exception as exc:
        logger.exception("%s job failed: %s", artifact, job_id)
        await _maybe_persist_draft(job_id, draft, last_persist, force=True)
        update_job(job_id, status="failed", error=str(exc))
        _sync_document_before_session(session_id, artifact, draft, failed=True, job_id=job_id)
        sync_session_on_optimize_failed(session_id, artifact, draft)
        await publish(
            job_id,
            {"type": "error", "message": str(exc), "request_id": get_request_id()},
        )
    finally:
        await _finish_run_summary(job_id, run, None, artifact=artifact)


async def _run_chunk_job(job_id: str, artifact: str, stream_factory) -> None:
    job = get_job(job_id)
    payload = json.loads(job["payload_json"])
    session_id = job["session_id"]
    seed_context_documents_from_payload(session_id, artifact, payload)
    update_job(job_id, status="running", phase="generating")
    sync_session_active_job(session_id, job_id, artifact)

    run = RunMetricsCollector.start(run_type=_map_run_type(artifact))
    draft = ""
    last_persist = 0.0
    review: Optional[Dict[str, Any]] = None

    try:
        async for event in stream_factory(payload):
            et = event.get("type")
            if et in ("chunk", "text_delta"):
                draft += event.get("content") or ""
                last_persist = await _maybe_persist_draft(job_id, draft, last_persist)
                await publish(job_id, {"type": "text_delta", "content": event.get("content") or ""})
            elif et == "phase":
                phase_name = event.get("phase") or ""
                if phase_name in PHASE_FROM_EVENT:
                    update_job(job_id, phase=PHASE_FROM_EVENT[phase_name])
                await publish(job_id, event)
            elif et == "review":
                review = event.get("content")
                update_job(
                    job_id,
                    phase="reviewing",
                    review_json=json.dumps(review, ensure_ascii=False) if review else None,
                )
                await publish(job_id, {"type": "review", "content": review})
            elif et == "done":
                final_content = event.get("content") or draft
                review = event.get("review") or review
                derived_from = _build_derived_from(session_id, artifact, payload)
                extra_metadata = {"derived_from": derived_from} if derived_from else None
                update_job(
                    job_id,
                    status="completed",
                    phase="done",
                    draft_content=final_content,
                    result_json=json.dumps(event, ensure_ascii=False),
                    review_json=json.dumps(review, ensure_ascii=False) if review else None,
                )
                _sync_document_before_session(
                    session_id,
                    artifact,
                    final_content,
                    review=review,
                    job_id=job_id,
                    extra_metadata=extra_metadata,
                )
                sync_session_on_job_complete(session_id, artifact, final_content, review)
                draft = final_content
                await publish(job_id, {"type": "done", "content": final_content, "review": review})
            else:
                await publish(job_id, event)

        job_after = get_job(job_id)
        if job_after["status"] == "running":
            derived_from = _build_derived_from(session_id, artifact, payload)
            extra_metadata = {"derived_from": derived_from} if derived_from else None
            update_job(job_id, status="completed", phase="done", draft_content=draft)
            _sync_document_before_session(
                session_id,
                artifact,
                draft,
                review=review,
                job_id=job_id,
                extra_metadata=extra_metadata,
            )
            sync_session_on_job_complete(session_id, artifact, draft, review)
            await publish(job_id, {"type": "done", "content": draft, "review": review})

    except Exception as exc:
        logger.exception("%s job failed: %s", artifact, job_id)
        await _maybe_persist_draft(job_id, draft, last_persist, force=True)
        update_job(job_id, status="failed", error=str(exc))
        _sync_document_before_session(session_id, artifact, draft, failed=True, job_id=job_id)
        sync_session_on_job_failed(session_id, artifact, draft)
        await publish(
            job_id,
            {"type": "error", "message": str(exc), "request_id": get_request_id()},
        )
    finally:
        await _finish_run_summary(job_id, run, None, artifact=artifact)


def schedule_job(job_id: str, artifact: str) -> None:
    if artifact == "prd":
        asyncio.create_task(run_prd_job(job_id))
    elif artifact == "api-docs":
        asyncio.create_task(run_api_docs_job(job_id))
    elif artifact == "prompts":
        asyncio.create_task(run_prompts_job(job_id))
    elif artifact.startswith("optimize-"):
        asyncio.create_task(run_optimize_job(job_id))
    else:
        raise ValueError(f"Unsupported artifact: {artifact}")
