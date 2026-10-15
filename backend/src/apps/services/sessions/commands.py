"""HTTP 与兼容入口共享的会话写用例，集中持有事务。"""

from typing import Any

from apps.db.connection import Database, database_context
from apps.services.sessions.state import get_session, save_session


def create_session(database: Database, data: dict[str, Any]) -> dict[str, Any]:
    with database_context(database), database.transaction():
        saved = save_session(data)
        return get_session(saved["id"])


def patch_session(database: Database, session_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    with database_context(database), database.transaction():
        # 保存用例合并持久化状态，避免把 GET 的运行中草稿叠加层回写。
        save_session(changes, session_id)
        return get_session(session_id)
