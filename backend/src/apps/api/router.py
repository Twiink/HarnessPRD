"""统一注册 /api 资源接口与隐藏的兼容适配层。"""

from fastapi import APIRouter

from apps.api import config, conversations, documents, jobs, sessions
from apps.api.compat import conversation, session
from apps.api.compat import documents as legacy_documents

router = APIRouter()
for resource in (
    sessions.router,
    documents.router,
    conversations.router,
    config.router,
    jobs.router,
    session.router,
    legacy_documents.router,
    conversation.router,
):
    router.include_router(resource)
