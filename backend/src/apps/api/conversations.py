"""对话资源请求模型，使用应用资源执行流式用例。"""

import json
import logging
import asyncio
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from apps.api.deps import get_resources
from apps.api.documents import DocumentType
from apps.core.config import get_settings
from apps.core.errors import DomainError
from apps.core.logging import redact
from apps.core.request_context import get_request_id
from apps.domain.inputs import (
    ConversationMessage,
    FormInput,
    RequirementsInput,
    input_dict,
    message_dicts,
)
from apps.llm.metrics import RunMetricsCollector, log_run_summary
from apps.llm.token_budget import BudgetExceededError, BudgetCheckResult

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
logger = logging.getLogger(__name__)
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


class ConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartConversationRequest(ConversationRequest):
    initial_input: str | None = ""
    form_data: FormInput | None = None
    system_prompt_override: str | None = None


class ContinueConversationRequest(ConversationRequest):
    conversation_id: str
    messages: list[ConversationMessage]
    user_input: str


class ConversationMessagesRequest(ConversationRequest):
    conversation_messages: list[ConversationMessage]


class GeneratePrdFromSummaryRequest(ConversationRequest):
    requirements_summary: RequirementsInput
    conversation_messages: list[ConversationMessage] | None = None


class SyncSummaryFromConversationRequest(ConversationRequest):
    requirements_summary: RequirementsInput
    conversation_messages: list[ConversationMessage]


class GenerateApiDocsRequest(ConversationRequest):
    prd_content: str
    conversation_messages: list[ConversationMessage]


class GeneratePromptsRequest(ConversationRequest):
    prd_content: str
    api_docs_content: str


class OptimizeDocumentRequest(ConversationRequest):
    doc_type: DocumentType
    current_content: str
    instruction: str
    context: str | None = ""


def _error_event(
    message: str = "请求处理失败，请检查服务配置后重试",
    *,
    code: str = "STREAM_FAILED",
    retryable: bool = False,
) -> dict[str, Any]:
    return {
        "type": "error",
        "code": code,
        "message": redact(message),
        "request_id": get_request_id(),
        "retryable": retryable,
    }


def _budget_exceeded_event(check: BudgetCheckResult) -> dict[str, Any]:
    return {
        **_error_event(check.message, code="TOKEN_BUDGET_EXCEEDED"),
        "context_usage": check.to_context_usage(),
    }


def _sse_line(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _make_sse_generator(async_gen, run_type: str):
    """统一流包装；取消时仅清理资源，finally 不输出事件。"""

    async def generate():
        run = RunMetricsCollector.start(run_type=run_type)
        revision_applied = None
        iterator = async_gen.__aiter__()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + get_settings().job_run_timeout
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise asyncio.TimeoutError()
                try:
                    event = await asyncio.wait_for(iterator.__anext__(), timeout=remaining)
                except StopAsyncIteration:
                    break
                if event.get("type") == "done" and "revision_applied" in event:
                    revision_applied = event["revision_applied"]
                if event.get("type") == "error":
                    # 上游错误可能包含凭据或用户输入，只输出稳定提示。
                    event = _error_event()
                yield _sse_line(event)
        except asyncio.TimeoutError:
            yield _sse_line(
                _error_event("生成超过执行时限，请重试", code="RUN_TIMEOUT", retryable=True)
            )
        except BudgetExceededError as exc:
            run.set_budget(exc.check)
            yield _sse_line(_budget_exceeded_event(exc.check))
        except DomainError as exc:
            yield _sse_line(_error_event(exc.message, code=exc.code, retryable=exc.retryable))
        except Exception as exc:
            logger.error("SSE failed run_type=%s error_type=%s", run_type, type(exc).__name__)
            yield _sse_line(_error_event())
        finally:
            try:
                close = getattr(async_gen, "aclose", None)
                if close is not None:
                    await close()
            finally:
                summary = run.finish(revision_applied=revision_applied)
                log_run_summary(summary)
        yield _sse_line({"type": "run_summary", **summary.to_dict()})
        yield "data: [DONE]\n\n"

    return generate


def _stream(source, run_type: str) -> StreamingResponse:
    return StreamingResponse(
        _make_sse_generator(source, run_type)(), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.get("/questions")
async def get_questions(resources=Depends(get_resources)):
    with (resources.settings.resources_dir / "questions_config.json").open(
        encoding="utf-8"
    ) as file:
        return json.load(file)


@router.post("/start-stream")
async def start_conversation_stream(
    body: StartConversationRequest, resources=Depends(get_resources)
):
    return _stream(
        resources.conversation_service.start_conversation_stream(
            body.initial_input or "",
            input_dict(body.form_data) if body.form_data is not None else None,
            body.system_prompt_override,
        ),
        "chat_start",
    )


@router.post("/continue-stream")
async def continue_conversation_stream(
    body: ContinueConversationRequest, resources=Depends(get_resources)
):
    return _stream(
        resources.conversation_service.continue_conversation_stream(
            body.conversation_id, message_dicts(body.messages), body.user_input
        ),
        "chat_continue",
    )


@router.post("/generate-prd-stream")
async def generate_prd_stream(body: ConversationMessagesRequest, resources=Depends(get_resources)):
    return _stream(
        resources.document_service.generate_prd_stream(message_dicts(body.conversation_messages)),
        "generate_prd",
    )


@router.post("/generate-prd-from-summary-stream")
async def generate_prd_from_summary_stream(
    body: GeneratePrdFromSummaryRequest, resources=Depends(get_resources)
):
    return _stream(
        resources.document_service.generate_prd_from_summary_stream(
            input_dict(body.requirements_summary), message_dicts(body.conversation_messages or [])
        ),
        "generate_prd_from_summary",
    )


@router.post("/sync-summary-from-conversation")
async def sync_summary_from_conversation(
    body: SyncSummaryFromConversationRequest, resources=Depends(get_resources)
):
    run = RunMetricsCollector.start(run_type="summary_sync")
    try:
        result = await resources.document_service.sync_summary_from_conversation(
            input_dict(body.requirements_summary), message_dicts(body.conversation_messages)
        )
    except BudgetExceededError as exc:
        run.set_budget(exc.check)
        raise DomainError(
            exc.check.message,
            code="TOKEN_BUDGET_EXCEEDED",
            status_code=422,
            details={"context_usage": exc.check.to_context_usage()},
        ) from exc
    except ValueError as exc:
        raise DomainError("需求摘要格式无效", code="INVALID_SUMMARY", status_code=422) from exc
    finally:
        summary = run.finish()
        log_run_summary(summary)
    result["run_summary"] = summary.to_dict()
    return result


@router.post("/generate-api-docs-stream")
async def generate_api_docs_stream(body: GenerateApiDocsRequest, resources=Depends(get_resources)):
    return _stream(
        resources.document_service.generate_api_docs_stream(
            body.prd_content, message_dicts(body.conversation_messages)
        ),
        "generate_api_docs",
    )


@router.post("/generate-prompts-stream")
async def generate_prompts_stream(body: GeneratePromptsRequest, resources=Depends(get_resources)):
    return _stream(
        resources.document_service.generate_prompts_stream(body.prd_content, body.api_docs_content),
        "generate_prompts",
    )


@router.post("/optimize-document-stream")
async def optimize_document_stream(body: OptimizeDocumentRequest, resources=Depends(get_resources)):
    return _stream(
        resources.document_service.optimize_document_stream(
            body.doc_type, body.current_content, body.instruction, body.context or ""
        ),
        "optimize_document",
    )
