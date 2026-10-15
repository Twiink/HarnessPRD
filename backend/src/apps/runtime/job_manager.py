"""单机任务管理器：持久化队列、租约、恢复、取消和原子最终化。"""

import asyncio
import json
import logging
import sqlite3

import httpx
import uuid
import time
from typing import Any

from pydantic import ValidationError

from apps.core.config import Settings
from apps.core.errors import DomainError
from apps.core.request_context import get_request_id, request_id_var, session_id_var
from apps.db.connection import Database, database_context
from apps.db.repositories.events import EventRepository
from apps.db.repositories.jobs import JobRepository, submission_hash
from apps.domain.jobs import Artifact, JobOutcome, LeaseLostError, TERMINAL_STATUSES
from apps.domain.inputs import RequirementsInput, input_dict
from apps.runtime.events import EventBroker
from apps.runtime.job_executor import Executor
from apps.runtime.recovery import recover_expired
from apps.runtime.progress import JobProgress
from apps.services.generation.guards import assert_can_create_job
from apps.services.documents.versions import (
    ARTIFACT_TO_DOC_TYPE,
    DOC_TYPE_TO_SESSION_FIELD,
    build_source_snapshot,
    sync_from_job,
)
from apps.domain.documents.quality import build_gate_context_from_job, run_quality_gate
from apps.services.sessions.state import (
    load_session_data_raw,
    sync_session_active_job,
    sync_session_active_optimize_job,
    sync_session_on_job_complete,
    sync_session_on_optimize_complete,
    sync_session_on_job_failed,
    sync_session_on_optimize_failed,
)

logger = logging.getLogger(__name__)

PAYLOAD_FIELDS = {
    "prd": {"requirements_summary", "conversation_messages"},
    "api-docs": {"prd_content", "conversation_messages"},
    "prompts": {"prd_content", "api_docs_content"},
    "optimize-prd": {"doc_type", "current_content", "instruction", "context"},
    "optimize-api-docs": {"doc_type", "current_content", "instruction", "context"},
    "optimize-prompts": {"doc_type", "current_content", "instruction", "context"},
}


def prepare_payload(
    session: dict, artifact: str, payload: dict, session_id: str | None = None
) -> dict:
    if set(payload) - PAYLOAD_FIELDS[artifact]:
        raise DomainError("任务包含未知输入字段", code="INVALID_JOB_PAYLOAD", status_code=422)
    prepared = dict(payload)
    if artifact == "prd":
        prepared.setdefault("requirements_summary", session.get("requirementsSummary"))
        if (
            not isinstance(prepared.get("requirements_summary"), dict)
            or not prepared["requirements_summary"]
        ):
            raise DomainError("缺少结构化需求摘要", code="INVALID_JOB_PAYLOAD")
        try:
            prepared["requirements_summary"] = input_dict(
                RequirementsInput.model_validate(prepared["requirements_summary"])
            )
        except ValidationError as exc:
            raise DomainError(
                "无效的结构化需求摘要", code="INVALID_JOB_PAYLOAD", status_code=422
            ) from exc
    elif artifact in ("api-docs", "prompts"):
        prepared.setdefault("prd_content", session.get("prdContent") or "")
        if not isinstance(prepared["prd_content"], str) or not prepared["prd_content"].strip():
            raise DomainError("PRD 内容为空", code="INVALID_JOB_PAYLOAD")
        if artifact == "prompts":
            prepared.setdefault("api_docs_content", session.get("apiDocsContent") or "")
            if not isinstance(prepared["api_docs_content"], str):
                raise DomainError("接口文档内容必须是字符串", code="INVALID_JOB_PAYLOAD")
    else:
        doc_type = artifact.removeprefix("optimize-")
        if prepared.get("doc_type", doc_type) != doc_type:
            raise DomainError("任务与文档类型不一致", code="INVALID_JOB_PAYLOAD")
        prepared["doc_type"] = doc_type
        prepared.setdefault(
            "current_content", session.get(DOC_TYPE_TO_SESSION_FIELD[doc_type]) or ""
        )
        for field in ("current_content", "instruction"):
            if not isinstance(prepared.get(field), str) or not prepared[field].strip():
                raise DomainError("优化任务需要正文和指令", code="INVALID_JOB_PAYLOAD")
        if "context" in prepared and not isinstance(prepared["context"], str):
            raise DomainError("上下文必须是字符串", code="INVALID_JOB_PAYLOAD")
    if "conversation_messages" in prepared:
        messages = prepared["conversation_messages"]
        if not isinstance(messages, list) or any(
            not isinstance(m, dict)
            or m.get("role") not in ("system", "user", "human", "assistant", "ai")
            or not isinstance(m.get("content"), str)
            for m in messages
        ):
            raise DomainError("无效的对话消息", code="INVALID_JOB_PAYLOAD")
    if session_id is None:
        assert_can_create_job(session, artifact, prepared)
    else:
        assert_can_create_job(session, artifact, prepared, session_id=session_id)
    return prepared


class JobManager:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        executor: Executor,
        events: EventBroker | None = None,
    ):
        self.database = database
        self.settings = settings
        self.executor = executor
        self.jobs = JobRepository(database)
        self.event_repository = EventRepository(database)
        self.events = events or EventBroker(self.event_repository, self.jobs)
        self.worker_id = str(uuid.uuid4())
        self._tasks: dict[str, asyncio.Task] = {}
        self._attempts: dict[str, int] = {}
        self._poller: asyncio.Task | None = None
        self._closing = False
        self._wakeup = asyncio.Event()
        self._last_success: float | None = None
        self._failure_since: float | None = None
        self._consecutive_failures = 0
        self._last_error_type: str | None = None
        self._timed_out_tasks: set[str] = set()
        self._cancellation_requested: set[str] = set()
        self._progress: dict[str, JobProgress] = {}

    @property
    def healthy(self) -> bool:
        now = time.monotonic()
        return (
            self.running
            and self._last_success is not None
            and now - self._last_success < self.settings.job_health_failure_seconds
            and (
                self._failure_since is None
                or now - self._failure_since < self.settings.job_health_failure_seconds
            )
        )

    @property
    def health(self) -> dict[str, Any]:
        now = time.monotonic()
        return {
            "last_success_age_seconds": now - self._last_success
            if self._last_success is not None
            else None,
            "failure_seconds": now - self._failure_since if self._failure_since is not None else 0,
            "consecutive_failures": self._consecutive_failures,
            "last_error_type": self._last_error_type,
            "timed_out_tasks": sorted(self._timed_out_tasks),
        }

    @property
    def running(self) -> bool:
        return self._poller is not None and not self._poller.done() and not self._closing

    @property
    def active_count(self) -> int:
        return len(self._tasks)

    async def start(self) -> None:
        if self.running:
            return
        self._closing = False
        with database_context(self.database):
            await asyncio.to_thread(self._recover)
        self._last_success = time.monotonic()
        self._failure_since = None
        self._consecutive_failures = 0
        self._last_error_type = None
        self._poller = asyncio.create_task(self._serve(), name="harnessprd-job-manager")

    async def _drain(self, tasks: list[asyncio.Task], *, cancel: bool = True) -> None:
        pending = {task for task in tasks if not task.done()}
        deadline = asyncio.get_running_loop().time() + self.settings.job_shutdown_timeout
        while pending:
            if cancel:
                for task in pending:
                    task.cancel()
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise DomainError(
                    "后台执行器未响应停止请求",
                    code="JOB_STOP_TIMEOUT",
                    status_code=503,
                    retryable=True,
                )
            done, pending = await asyncio.wait(pending, timeout=min(0.1, remaining))
            for task in done:
                if not task.cancelled():
                    task.exception()

    def _fence_shutdown(self) -> None:
        with database_context(self.database), self.database.transaction():
            for job in self.jobs.owned_running(self.worker_id):
                self.jobs.interrupt(job["id"], self.worker_id, job["attempt_count"])

    async def close(self) -> None:
        self._closing = True
        self._wakeup.set()
        try:
            # 先停止投递并等待正在执行的数据库操作，再撤销所有权并取消执行器。
            if self._poller:
                await self._drain([self._poller], cancel=False)
            try:
                await asyncio.to_thread(self._fence_shutdown)
            except sqlite3.Error:
                logger.exception("关闭时无法写入中断状态，任务将在租约到期后恢复")
            await self._drain(list(self._tasks.values()))
            self._tasks.clear()
            self._attempts.clear()
            self._timed_out_tasks.clear()
            self._cancellation_requested.clear()
        finally:
            self.events.close()

    async def submit(
        self, session_id: str, artifact: str, payload: dict, idempotency_key: str | None = None
    ) -> str:
        if self._closing or not self.healthy:
            raise DomainError("任务服务未就绪", code="NOT_READY", status_code=503, retryable=True)
        if artifact not in {entry.value for entry in Artifact}:
            raise DomainError("无效的任务类型", code="INVALID_ARTIFACT", status_code=422)
        if idempotency_key is not None and (
            not idempotency_key.strip() or len(idempotency_key) > 200
        ):
            raise DomainError(
                "幂等键必须为 1 到 200 个字符", code="INVALID_IDEMPOTENCY_KEY", status_code=422
            )
        digest = submission_hash(artifact, payload)
        job_id = await asyncio.to_thread(
            self._persist_submission, session_id, artifact, payload, idempotency_key, digest
        )
        self.events.notify(job_id)
        self._wakeup.set()
        return job_id

    def _persist_submission(
        self,
        session_id: str,
        artifact: str,
        payload: dict,
        idempotency_key: str | None,
        digest: str,
    ) -> str:
        with database_context(self.database), self.database.transaction():
            replay = self.jobs.replay(session_id, idempotency_key, digest)
            if replay:
                return replay
            session = load_session_data_raw(session_id)
            prepared = prepare_payload(session, artifact, payload, session_id)
            prepared["_source_snapshot"] = build_source_snapshot(session_id, artifact, prepared)
            job_id = self.jobs.create(
                session_id,
                artifact,
                prepared,
                idempotency_key,
                digest,
                get_request_id(),
                max_queued=self.settings.job_max_queued,
            )
            if artifact.startswith("optimize-"):
                sync_session_active_optimize_job(session_id, job_id)
            else:
                sync_session_active_job(session_id, job_id, artifact)
        return job_id

    def _persist_cancel(self, job_id: str) -> None:
        with database_context(self.database), self.database.transaction():
            job = self.jobs.request_cancel(job_id)
            if job["status"] not in TERMINAL_STATUSES:
                self._cancel_finalize(job_id)

    async def cancel(self, job_id: str) -> dict[str, Any]:
        progress = self._progress.get(job_id)

        async def persist_cancel() -> None:
            await asyncio.to_thread(self._persist_cancel, job_id)

        if progress:
            try:
                await progress.flush_and_fence(persist_cancel)
            except LeaseLostError:
                await persist_cancel()
        else:
            await persist_cancel()
        self.events.notify(job_id)
        task = self._tasks.get(job_id)
        if task:
            await self._drain([task])
        return await asyncio.to_thread(self.jobs.get, job_id)

    def _recover(self) -> None:
        with self.database.transaction():
            for job in self.jobs.recoverable(self.settings.job_max_attempts):
                if job["cancel_requested"]:
                    self._cancel_finalize(job["id"])
                elif (
                    job["status"] != "running"
                    and job["attempt_count"] >= self.settings.job_max_attempts
                ):
                    self._fail_finalize(job["id"], "ATTEMPTS_EXHAUSTED", "任务重试次数已耗尽")
                elif job["status"] == "interrupted":
                    self.jobs.requeue(job["id"])
            recover_expired(
                self.jobs,
                self.settings.job_max_attempts,
                self._fail_finalize,
                self._cancel_finalize,
            )

    async def _serve(self) -> None:
        from apps.core.config import settings_context

        with database_context(self.database), settings_context(self.settings):
            while not self._closing:
                self._wakeup.clear()
                try:
                    # 已取消/已回收的本地任务先停止，写入仍由租约和attempt二次约束。
                    for job_id, task in list(self._tasks.items()):
                        if task.done():
                            self._tasks.pop(job_id, None)
                            self._attempts.pop(job_id, None)
                            self._timed_out_tasks.discard(job_id)
                            self._cancellation_requested.discard(job_id)
                            if not task.cancelled():
                                task.exception()
                        else:
                            try:
                                current = await asyncio.to_thread(self.jobs.get, job_id)
                                still_owned = (
                                    current["status"] == "running"
                                    and current["worker_id"] == self.worker_id
                                    and current["attempt_count"] == self._attempts[job_id]
                                    and not current["cancel_requested"]
                                )
                            except DomainError as exc:
                                if exc.status_code != 404:
                                    raise
                                still_owned = False
                            if not still_owned and job_id not in self._cancellation_requested:
                                self._cancellation_requested.add(job_id)
                                task.cancel()
                    await asyncio.to_thread(self._recover)
                    while len(self._tasks) < self.settings.job_max_concurrency:
                        job = await asyncio.to_thread(
                            self.jobs.claim,
                            self.worker_id,
                            self.settings.job_lease_seconds,
                            self.settings.job_max_attempts,
                            tuple(self._tasks),
                        )
                        if job is None:
                            break
                        if self._closing:
                            await asyncio.to_thread(
                                self.jobs.interrupt, job["id"], self.worker_id, job["attempt_count"]
                            )
                            break
                        self.events.notify(job["id"])
                        task = asyncio.create_task(self._run(job), name=f"job:{job['id']}")
                        self._tasks[job["id"]] = task
                        self._attempts[job["id"]] = job["attempt_count"]
                        task.add_done_callback(lambda _: self._wakeup.set())
                    self._last_success = time.monotonic()
                    self._failure_since = None
                    self._consecutive_failures = 0
                    self._last_error_type = None
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if self._failure_since is None:
                        self._failure_since = time.monotonic()
                    self._consecutive_failures += 1
                    self._last_error_type = type(exc).__name__
                    logger.exception("任务队列轮询失败 worker_id=%s", self.worker_id)
                try:
                    await asyncio.wait_for(
                        self._wakeup.wait(), timeout=self.settings.job_poll_interval
                    )
                except asyncio.TimeoutError:
                    pass

    async def _heartbeat(self, job: dict, execution: asyncio.Task) -> None:
        while not self._closing:
            await asyncio.sleep(self.settings.job_lease_seconds / 3)
            if self._closing:
                return
            try:
                renewed = await asyncio.to_thread(
                    self.jobs.renew,
                    job["id"],
                    self.worker_id,
                    job["attempt_count"],
                    self.settings.job_lease_seconds,
                )
            except Exception:
                logger.exception("任务续租失败 job_id=%s", job["id"])
                renewed = False
            if not renewed:
                self._cancellation_requested.add(job["id"])
                execution.cancel()
                return

    async def _run(self, job: dict) -> None:
        job_id = job["id"]
        attempt = job["attempt_count"]
        request_token = request_id_var.set(job.get("request_id") or f"job_{job_id}")
        session_token = session_id_var.set(job["session_id"])
        execution = asyncio.current_task()
        assert execution is not None
        heartbeat = asyncio.create_task(self._heartbeat(job, execution), name=f"lease:{job_id}")

        async def persist(fields: dict, batch: list[dict]) -> None:
            def persist_batch():
                with self.database.transaction():
                    if self._closing or not self.jobs.progress(
                        job_id, self.worker_id, attempt, **fields
                    ):
                        raise LeaseLostError()
                    for event in batch:
                        self.event_repository.append(job_id, event)

            await asyncio.to_thread(persist_batch)
            self.events.notify(job_id)

        progress = JobProgress(persist, flush_bytes=self.settings.job_progress_flush_bytes)
        self._progress[job_id] = progress

        async def flush_periodically() -> None:
            try:
                while True:
                    await asyncio.sleep(self.settings.job_progress_flush_interval)
                    await progress.flush()
            except LeaseLostError:
                execution.cancel()
            except Exception:
                logger.exception("任务进度刷新失败 job_id=%s", job_id)
                execution.cancel()

        flusher = asyncio.create_task(flush_periodically(), name=f"progress:{job_id}")
        watchdog = asyncio.create_task(
            self._watch_timeout(job, execution, progress), name=f"timeout:{job_id}"
        )
        try:
            outcome = await self.executor.execute(job, progress.emit)
            await progress.flush()
            await asyncio.to_thread(self._complete, job, outcome)
        except asyncio.CancelledError:
            try:
                await asyncio.to_thread(self._interrupt_execution, job_id, attempt)
            except (sqlite3.Error, DomainError):
                logger.error("任务停止时未能写入状态 job_id=%s", job_id)
            raise
        except LeaseLostError:
            pass
        except Exception as exc:
            try:
                await progress.flush()
            except LeaseLostError:
                pass
            except sqlite3.Error:
                logger.exception("任务失败前无法刷新草稿 job_id=%s", job_id)
            try:
                await asyncio.to_thread(self._execution_failed, job_id, attempt, exc)
            except (sqlite3.Error, DomainError):
                logger.error("任务失败状态未写入，等待租约恢复 job_id=%s", job_id)
            logger.error("任务失败 job_id=%s error_type=%s", job_id, type(exc).__name__)
        finally:
            progress.revoked = True
            for child in (heartbeat, flusher, watchdog):
                child.cancel()
            await asyncio.gather(heartbeat, flusher, watchdog, return_exceptions=True)
            self._progress.pop(job_id, None)
            request_id_var.reset(request_token)
            session_id_var.reset(session_token)
            self.events.notify(job_id)

    async def _watch_timeout(
        self, job: dict, execution: asyncio.Task, progress: JobProgress
    ) -> None:
        await asyncio.sleep(self.settings.job_run_timeout)
        # Fence durably before cancellation. A stubborn executor stays in _tasks and retains its slot.
        while not self._closing:
            try:
                fenced = False

                async def revoke() -> None:
                    nonlocal fenced
                    fenced = await asyncio.to_thread(self._timeout_execution, job)

                await progress.flush_and_fence(revoke)
                if fenced:
                    self._timed_out_tasks.add(job["id"])
                    self._cancellation_requested.add(job["id"])
                    self.events.notify(job["id"])
                    execution.cancel()
                return
            except LeaseLostError:
                return
            except sqlite3.Error:
                logger.exception("任务超时撤销所有权失败 job_id=%s", job["id"])
                await asyncio.sleep(self.settings.job_poll_interval)

    def _timeout_execution(self, job: dict) -> bool:
        with self.database.transaction():
            current = self.jobs.get(job["id"])
            if not (
                current["status"] == "running"
                and current["worker_id"] == self.worker_id
                and current["attempt_count"] == job["attempt_count"]
            ):
                return False
            message = "任务超过执行时限"
            if current["cancel_requested"]:
                self._cancel_finalize(job["id"])
            elif current["attempt_count"] >= self.settings.job_max_attempts:
                self._fail_finalize(job["id"], "JOB_RUN_TIMEOUT", message)
            else:
                self.jobs.interrupt(
                    job["id"],
                    self.worker_id,
                    job["attempt_count"],
                    code="JOB_RUN_TIMEOUT",
                    message=message,
                )
                self.event_repository.append(
                    job["id"],
                    {
                        "type": "retrying",
                        "code": "JOB_RUN_TIMEOUT",
                        "retryable": True,
                        "attempt_count": job["attempt_count"],
                    },
                )
                self.jobs.requeue(job["id"])
            return True

    def _interrupt_execution(self, job_id: str, attempt: int) -> None:
        with self.database.transaction():
            current = self.jobs.get(job_id)
            if current["cancel_requested"]:
                self._cancel_finalize(job_id)
            else:
                self.jobs.interrupt(job_id, self.worker_id, attempt)

    def _execution_failed(self, job_id: str, attempt: int, exc: Exception) -> None:
        with self.database.transaction():
            if not self._closing and self.jobs.owned(job_id, self.worker_id, attempt):
                code = exc.code if isinstance(exc, DomainError) else "GENERATION_FAILED"
                upstream_status = getattr(exc, "status_code", None)
                retryable = (
                    isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError))
                    or isinstance(exc, DomainError)
                    and exc.retryable
                    or isinstance(upstream_status, int)
                    and (upstream_status == 429 or upstream_status >= 500)
                )
                if retryable and attempt < self.settings.job_max_attempts:
                    self.jobs.interrupt(job_id, self.worker_id, attempt)
                    self.event_repository.append(
                        job_id,
                        {
                            "type": "retrying",
                            "code": code,
                            "retryable": True,
                            "attempt_count": attempt,
                        },
                    )
                    self.jobs.requeue(job_id)
                else:
                    # 上游错误可能含凭据和请求内容，只对外返回稳定信息。
                    self._fail_finalize(job_id, code, "文档生成失败，请检查服务配置后重试")

    def _complete(self, job: dict, outcome: JobOutcome) -> None:
        job_id, attempt = job["id"], job["attempt_count"]
        with self.database.transaction():
            if self._closing or not self.jobs.owned(job_id, self.worker_id, attempt):
                raise LeaseLostError()
            if not outcome.content.strip():
                raise DomainError("生成内容为空", code="EMPTY_DOCUMENT")
            self.jobs.progress(
                job_id,
                self.worker_id,
                attempt,
                draft_content=outcome.content,
                review_json=json.dumps(outcome.review, ensure_ascii=False)
                if outcome.review
                else None,
            )
            final_job = self.jobs.get(job_id)
            session = load_session_data_raw(job["session_id"])
            doc_type = ARTIFACT_TO_DOC_TYPE[job["artifact"]]
            metadata = {
                **outcome.metadata,
                "quality_gate": run_quality_gate(
                    doc_type, outcome.content, build_gate_context_from_job(final_job, session)
                ),
            }
            sync_from_job(
                job["session_id"],
                job["artifact"],
                outcome.content,
                review=outcome.review,
                source_job_id=job_id,
                extra_metadata=metadata,
            )
            if job["artifact"].startswith("optimize-"):
                sync_session_on_optimize_complete(
                    job["session_id"], job["artifact"], outcome.content, job_id=job_id
                )
            else:
                sync_session_on_job_complete(
                    job["session_id"],
                    job["artifact"],
                    outcome.content,
                    outcome.review,
                    job_id=job_id,
                )
            result = {
                **outcome.result,
                "type": "done",
                "content": outcome.content,
                "review": outcome.review,
            }
            self.jobs.finish(job_id, "succeeded", result=result)
            self.event_repository.append(job_id, result)
            if metadata.get("run_summary"):
                self.event_repository.append(
                    job_id, {"type": "run_summary", **metadata["run_summary"]}
                )
            self.event_repository.append(job_id, {"type": "succeeded", "status": "succeeded"})

    def _sync_terminal_session(self, job: dict) -> None:
        # 只清除此任务拥有的active镜像，避免旧执行者污染下一任务。
        try:
            session = load_session_data_raw(job["session_id"])
        except KeyError:
            return
        except DomainError as exc:
            if exc.status_code == 404:
                return
            raise
        if session.get("activeJobId") != job["id"]:
            return
        if job["artifact"].startswith("optimize-"):
            sync_session_on_optimize_failed(
                job["session_id"], job["artifact"], "", job_id=job["id"]
            )
        else:
            sync_session_on_job_failed(job["session_id"], job["artifact"], "", job_id=job["id"])

    def _fail_finalize(self, job_id: str, code: str, message: str) -> None:
        if self.jobs.finish(job_id, "failed", code=code, message=message):
            job = self.jobs.get(job_id)
            self._sync_terminal_session(job)
            self.event_repository.append(
                job_id,
                {
                    "type": "error",
                    "code": code,
                    "message": message,
                    "request_id": job.get("request_id"),
                    "retryable": False,
                },
            )
            self.event_repository.append(job_id, {"type": "failed", "status": "failed"})

    def _cancel_finalize(self, job_id: str) -> None:
        if self.jobs.finish(job_id, "cancelled", code="JOB_CANCELLED", message="任务已取消"):
            self._sync_terminal_session(self.jobs.get(job_id))
            self.event_repository.append(job_id, {"type": "cancelled", "status": "cancelled"})
