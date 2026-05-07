"""对话相关路由"""

import json
import logging
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any

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
from services.conversation_service import ConversationService
from services.document_service import DocumentService

router = APIRouter(prefix="/api/conversation", tags=["conversation"])
conversation_service = ConversationService()
document_service = DocumentService()
logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


def _make_sse_generator(async_gen):
    """通用 SSE 生成器包装器"""
    async def generate():
        try:
            async for event in async_gen:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("SSE stream failed in conversation API")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
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
    async def generate():
        try:
            async for event in conversation_service.start_conversation_stream(
                request.initial_input, request.form_data, request.system_prompt_override
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("start_conversation_stream failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/continue-stream")
async def continue_conversation_stream(request: ContinueConversationRequest):
    """继续对话 — 流式返回"""
    async def generate():
        try:
            async for event in conversation_service.continue_conversation_stream(
                request.conversation_id, request.messages, request.user_input
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("continue_conversation_stream failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers=SSE_HEADERS)


# ── 文档生成流式接口 ──────────────────────────────────────────────────────────

@router.post("/generate-prd-stream")
async def generate_prd_stream(request: ConversationMessagesRequest):
    """生成 PRD — 流式返回"""
    gen = _make_sse_generator(
        document_service.generate_prd_stream(request.conversation_messages)
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/generate-prd-from-summary-stream")
async def generate_prd_from_summary_stream(request: GeneratePrdFromSummaryRequest):
    """基于结构化需求摘要生成 PRD — 流式返回"""
    gen = _make_sse_generator(
        document_service.generate_prd_from_summary_stream(
            request.requirements_summary,
            request.conversation_messages or [],
        )
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/sync-summary-from-conversation")
async def sync_summary_from_conversation(request: SyncSummaryFromConversationRequest):
    """基于澄清对话更新结构化需求摘要"""
    try:
        return await document_service.sync_summary_from_conversation(
            request.requirements_summary,
            request.conversation_messages,
        )
    except ValueError as e:
        logger.exception("sync_summary_from_conversation failed with validation error")
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/generate-api-docs-stream")
async def generate_api_docs_stream(request: GenerateApiDocsRequest):
    """生成接口文档 — 流式返回"""
    gen = _make_sse_generator(
        document_service.generate_api_docs_stream(
            request.prd_content, request.conversation_messages
        )
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/retrieve-api-docs-rag")
async def retrieve_api_docs_rag(request: GenerateApiDocsRequest):
    """生成接口文档前，检索团队规范和历史接口示例"""
    return await document_service.retrieve_api_docs_rag_hits(
        request.prd_content,
        request.conversation_messages,
    )


@router.post("/generate-prompts-stream")
async def generate_prompts_stream(request: GeneratePromptsRequest):
    """生成 AI 提示词套件 — 流式返回"""
    gen = _make_sse_generator(
        document_service.generate_prompts_stream(
            request.prd_content, request.api_docs_content
        )
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
        )
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)
