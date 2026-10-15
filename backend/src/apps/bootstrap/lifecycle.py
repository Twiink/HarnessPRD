"""应用级资源装配，启动迁移/恢复，关闭时等待后台任务。"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging

from fastapi import FastAPI

from apps.core.config import Settings, get_settings, settings_context
from apps.core.errors import DomainError
from apps.core.logging import configure_logging
from apps.bootstrap.validation import validate_resources
from apps.db.connection import Database, database_context
from apps.runtime.events import EventBroker
from apps.runtime.job_executor import Executor, JobExecutor
from apps.runtime.job_manager import JobManager
from apps.services.conversations.dialogue import ConversationService
from apps.services.generation.documents import DocumentService
from apps.llm.factory import get_tracked_llm
from apps.llm.runtime import LLMRuntime, llm_runtime_context

logger = logging.getLogger(__name__)


@dataclass
class Resources:
    settings: Settings
    database: Database
    job_manager: JobManager
    events: EventBroker
    document_service: DocumentService
    conversation_service: ConversationService
    llm_runtime: LLMRuntime
    ready: bool = False


def application_lifespan(config: Settings | None = None, executor: Executor | None = None):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings = config if config is not None else get_settings()
        configure_logging(settings)
        database = Database(settings.database_path, settings.sqlite_busy_timeout_ms)
        llm_runtime = LLMRuntime(settings.job_max_concurrency)
        with (
            settings_context(settings),
            database_context(database),
            llm_runtime_context(llm_runtime),
        ):
            validate_resources(settings)
            database.migrate()
            documents = DocumentService(llm_factory=get_tracked_llm)
            conversations = ConversationService(llm_factory=get_tracked_llm)
            manager = JobManager(database, settings, executor or JobExecutor(documents))
            resources = Resources(
                settings, database, manager, manager.events, documents, conversations, llm_runtime
            )
            app.state.resources = resources
            try:
                await manager.start()
                resources.ready = True
                yield
            finally:
                resources.ready = False
                manager_error = None
                try:
                    await manager.close()
                except BaseException as exc:
                    manager_error = exc
                remaining = await llm_runtime.close(timeout=settings.job_shutdown_timeout)
                if remaining:
                    logger.error("模型调用未响应停止请求 remaining=%s", remaining)
                if manager_error is not None:
                    raise manager_error
                if remaining:
                    raise DomainError(
                        "模型调用未响应停止请求",
                        code="LLM_STOP_TIMEOUT",
                        status_code=503,
                        retryable=True,
                    )

    return lifespan
