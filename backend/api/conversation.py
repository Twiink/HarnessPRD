"""对话相关路由"""

import json
import logging
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional

from api.schemas import (
    StartConversationRequest,
    ContinueConversationRequest,
    ConversationMessagesRequest,
    GeneratePrdFromSummaryRequest,
    SyncSummaryFromConversationRequest,
    GenerateApiDocsRequest,
    GeneratePromptsRequest,
    OptimizeDocumentRequest,
)
from core.request_context import get_request_id
from services.conversation_service import ConversationService
from services.document_service import DocumentService
from services.llm_metrics import RunMetricsCollector, log_run_summary
from services.token_estimator import BudgetExceededError, BudgetCheckResult

router = APIRouter(prefix="/api/conversation", tags=["conversation"])
conversation_service = ConversationService()
document_service = DocumentService()
logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


def _error_event(message: str) -> Dict[str, Any]:
    return {"type": "error", "message": message, "request_id": get_request_id()}


def _budget_exceeded_event(check: BudgetCheckResult) -> Dict[str, Any]:
    return {
        "type": "error",
        "code": "TOKEN_BUDGET_EXCEEDED",
        "message": check.message,
        "request_id": get_request_id(),
        "context_usage": check.to_context_usage(),
    }


def _make_sse_generator(async_gen, run_type: str):
    """通用 SSE 生成器包装器 — 统一 emit run_summary"""
    async def generate():
        run = RunMetricsCollector.start(run_type=run_type)
        revision_applied: Optional[bool] = None
        try:
            async for event in async_gen:
                if event.get("type") == "done" and "revision_applied" in event:
                    revision_applied = event["revision_applied"]
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except BudgetExceededError as e:
            run.set_budget(e.check)
            yield f"data: {json.dumps(_budget_exceeded_event(e.check), ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("SSE stream failed in conversation API")
            yield f"data: {json.dumps(_error_event(str(e)), ensure_ascii=False)}\n\n"
        finally:
            summary = run.finish(revision_applied=revision_applied)
            summary_event = {"type": "run_summary", **summary.to_dict()}
            yield f"data: {json.dumps(summary_event, ensure_ascii=False)}\n\n"
            log_run_summary(summary)
            yield "data: [DONE]\n\n"
    return generate


def _make_handwritten_sse_generator(service_gen, run_type: str):
    """手写 SSE generator 包装 — start/continue-stream 等"""
    async def generate():
        run = RunMetricsCollector.start(run_type=run_type)
        revision_applied: Optional[bool] = None
        try:
            async for event in service_gen:
                if event.get("type") == "done" and "revision_applied" in event:
                    revision_applied = event["revision_applied"]
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except BudgetExceededError as e:
            run.set_budget(e.check)
            yield f"data: {json.dumps(_budget_exceeded_event(e.check), ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("SSE stream failed in conversation API")
            yield f"data: {json.dumps(_error_event(str(e)), ensure_ascii=False)}\n\n"
        finally:
            summary = run.finish(revision_applied=revision_applied)
            summary_event = {"type": "run_summary", **summary.to_dict()}
            yield f"data: {json.dumps(summary_event, ensure_ascii=False)}\n\n"
            log_run_summary(summary)
            yield "data: [DONE]\n\n"
    return generate


# ── 配置 ────────────────────────────────────────────────────────────────────

@router.get("/questions")
async def get_questions() -> Dict[str, Any]:
    config_path = os.path.join(os.path.dirname(__file__), "..", "core", "questions_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 对话流式接口 ─────────────────────────────────────────────────────────────

@router.post("/start-stream")
async def start_conversation_stream(request: StartConversationRequest):
    """开始对话 — 流式返回"""
    gen = _make_handwritten_sse_generator(
        conversation_service.start_conversation_stream(
            request.initial_input, request.form_data, request.system_prompt_override
        ),
        run_type="chat_start",
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/continue-stream")
async def continue_conversation_stream(request: ContinueConversationRequest):
    """继续对话 — 流式返回"""
    gen = _make_handwritten_sse_generator(
        conversation_service.continue_conversation_stream(
            request.conversation_id, request.messages, request.user_input
        ),
        run_type="chat_continue",
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


# ── 文档生成流式接口 ──────────────────────────────────────────────────────────

@router.post("/generate-prd-stream")
async def generate_prd_stream(request: ConversationMessagesRequest):
    """生成 PRD — 流式返回"""
    gen = _make_sse_generator(
        document_service.generate_prd_stream(request.conversation_messages),
        run_type="generate_prd",
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/generate-prd-from-summary-stream")
async def generate_prd_from_summary_stream(request: GeneratePrdFromSummaryRequest):
    """基于结构化需求摘要生成 PRD — 流式返回"""
    gen = _make_sse_generator(
        document_service.generate_prd_from_summary_stream(
            request.requirements_summary,
            request.conversation_messages or [],
        ),
        run_type="generate_prd_from_summary",
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/sync-summary-from-conversation")
async def sync_summary_from_conversation(request: SyncSummaryFromConversationRequest):
    """基于澄清对话更新结构化需求摘要"""
    run = RunMetricsCollector.start(run_type="summary_sync")
    try:
        result = await document_service.sync_summary_from_conversation(
            request.requirements_summary,
            request.conversation_messages,
        )
        summary = run.finish()
        result["run_summary"] = summary.to_dict()
        log_run_summary(summary)
        return result
    except BudgetExceededError as e:
        run.set_budget(e.check)
        run.finish()
        raise HTTPException(
            status_code=422,
            detail={
                "message": e.check.message,
                "context_usage": e.check.to_context_usage(),
            },
        ) from e
    except ValueError as e:
        run.finish()
        logger.exception("sync_summary_from_conversation failed with validation error")
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception:
        run.finish()
        raise


@router.post("/generate-api-docs-stream")
async def generate_api_docs_stream(request: GenerateApiDocsRequest):
    """生成接口文档 — 流式返回"""
    gen = _make_sse_generator(
        document_service.generate_api_docs_stream(
            request.prd_content, request.conversation_messages
        ),
        run_type="generate_api_docs",
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/generate-prompts-stream")
async def generate_prompts_stream(request: GeneratePromptsRequest):
    """生成 AI 提示词套件 — 流式返回"""
    gen = _make_sse_generator(
        document_service.generate_prompts_stream(
            request.prd_content, request.api_docs_content
        ),
        run_type="generate_prompts",
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/optimize-document-stream")
async def optimize_document_stream(request: OptimizeDocumentRequest):
    """优化文档内容 — 流式返回"""
    gen = _make_sse_generator(
        document_service.optimize_document_stream(
            request.doc_type,
            request.current_content,
            request.instruction,
            request.context or "",
        ),
        run_type="optimize_document",
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)
