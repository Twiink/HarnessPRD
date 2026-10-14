"""统一注册 /api 资源接口与隐藏的兼容适配层。"""

from fastapi import APIRouter

from apps.api import config, conversation, conversations, documents, jobs, session, sessions

router = APIRouter()
for resource in (
    sessions.router,
    documents.router,
    conversations.router,
    config.router,
    jobs.router,
    session.router,
    documents.legacy_router,
    conversation.router,
):
    router.include_router(resource)
