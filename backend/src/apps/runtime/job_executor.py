"""执行生成用例并归一化流事件；状态、租约和最终写入由 Manager 管理。"""

import json
import asyncio
from typing import Any, Awaitable, Callable, Protocol

from apps.domain.jobs import JobOutcome
from apps.llm.metrics import RunMetricsCollector, log_run_summary
from apps.services.generation.documents import DocumentService
from apps.services.documents.versions import (
    seed_context_documents_from_payload,
)
from apps.core.resources.skill_loader import load_skill_bundle, bundle_to_injected_meta

Emit = Callable[[dict[str, Any]], Awaitable[None]]


class Executor(Protocol):
    async def execute(self, job: dict[str, Any], emit: Emit) -> JobOutcome: ...


class JobExecutor:
    def __init__(self, documents: DocumentService):
        self.documents = documents

    async def execute(self, job: dict[str, Any], emit: Emit) -> JobOutcome:
        payload = json.loads(job["payload_json"])
        artifact = job["artifact"]
        await asyncio.to_thread(
            seed_context_documents_from_payload, job["session_id"], artifact, payload
        )
        if artifact == "prd":
            stream = self.documents.generate_prd_from_summary_stream(
                payload["requirements_summary"], payload.get("conversation_messages") or []
            )
        elif artifact == "api-docs":
            stream = self.documents.generate_api_docs_stream(
                payload["prd_content"], payload.get("conversation_messages") or []
            )
        elif artifact == "prompts":
            stream = self.documents.generate_prompts_stream(
                payload["prd_content"], payload.get("api_docs_content") or ""
            )
        else:
            stream = self.documents.optimize_document_stream(
                artifact.removeprefix("optimize-"),
                payload["current_content"],
                payload["instruction"],
                payload.get("context") or "",
            )
        run = RunMetricsCollector.start(run_type=artifact)
        draft = ""
        review = None
        done = None
        try:
            async for event in stream:
                event = dict(event)
                event_type = event.get("type")
                if event_type in ("chunk", "text_delta"):
                    draft += event.get("content") or ""
                    event["type"] = "text_delta"
                elif event_type == "phase" and event.get("phase") == "rewrite_started":
                    draft = ""
                elif event_type == "review":
                    review = event.get("content")
                elif event_type == "done":
                    done = event
                    draft = event.get("final_prd") or event.get("content") or draft
                    review = event.get("review") or review
                    # done只有在文档与Job终态已提交后才能发布。
                    continue
                elif event_type == "error":
                    raise RuntimeError("生成器报告执行失败")
                await emit(event)
            if done is None:
                raise RuntimeError("生成器未返回完成事件")
            if not draft.strip():
                raise ValueError("生成内容为空")
            run.set_injected_skills(bundle_to_injected_meta(load_skill_bundle(artifact)))
            run_summary = run.finish(revision_applied=done.get("revision_applied"))
            summary = run_summary.to_dict()
            metadata = {"run_summary": summary}
            if artifact in ("api-docs", "prompts", "optimize-api-docs", "optimize-prompts"):
                # Legacy jobs have no trustworthy version snapshot; never infer it at completion.
                metadata["derived_from"] = dict(payload.get("_source_snapshot") or {})
            log_run_summary(run_summary)
            return JobOutcome(draft, review, {**done, "content": draft}, metadata)
        except BaseException:
            run.finish()
            raise
