"""应用级资源装配，启动迁移/恢复，关闭时等待后台任务。"""

from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI

from apps.core.config import Settings, get_settings, settings_context
from apps.core.logging import configure_logging
from apps.db.connection import Database, database_context
from apps.runtime.events import EventBroker
from apps.runtime.job_executor import Executor, JobExecutor
from apps.runtime.job_manager import JobManager
from apps.services.conversation_service import ConversationService
from apps.services.document_service import DocumentService


@dataclass
class Resources:
    settings: Settings
    database: Database
    job_manager: JobManager
    events: EventBroker
    document_service: DocumentService
    conversation_service: ConversationService
    ready: bool = False


def application_lifespan(config: Settings | None = None, executor: Executor | None = None):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings = config if config is not None else get_settings()
        configure_logging(settings)
        database = Database(settings.database_path, settings.sqlite_busy_timeout_ms)
        with settings_context(settings), database_context(database):
            database.migrate()
            documents = DocumentService()
            conversations = ConversationService()
            manager = JobManager(database, settings, executor or JobExecutor(documents))
            resources = Resources(
                settings, database, manager, manager.events, documents, conversations
            )
            app.state.resources = resources
            try:
                await manager.start()
                resources.ready = True
                yield
            finally:
                resources.ready = False
                await manager.close()

    return lifespan
