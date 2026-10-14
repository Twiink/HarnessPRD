"""SQLite 连接和可嵌套事务；导入不创建文件。"""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import sqlite3
from typing import Iterator

_database: ContextVar["Database | None"] = ContextVar("database", default=None)
_transaction: ContextVar[tuple["Database", sqlite3.Connection] | None] = ContextVar(
    "transaction", default=None
)


class Database:
    def __init__(self, path: str | Path, busy_timeout_ms: int = 5000):
        self.path = Path(path)
        self.busy_timeout_ms = busy_timeout_ms

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=self.busy_timeout_ms / 1000, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout_ms)}")
        return conn

    def migrate(self) -> None:
        from apps.db.migrations import migrate

        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = self.connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            migrate(conn)
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        current = _transaction.get()
        if current and current[0] is self:
            yield current[1]
            return
        conn = self.connect()
        token = _transaction.set((self, conn))
        try:
            # 获取写锁后才读取版本号/冲突状态，避免检查与写入之间的竞态。
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            _transaction.reset(token)
            conn.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        """独立读取不申请写锁；事务内读取复用外层连接。"""
        current = _transaction.get()
        if current and current[0] is self:
            yield current[1]
            return
        conn = self.connect()
        try:
            conn.execute("PRAGMA query_only = ON")
            yield conn
        finally:
            conn.close()

    def is_ready(self) -> bool:
        from apps.db.migrations import LATEST_VERSION

        try:
            with self.read() as conn:
                version = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
                return version == LATEST_VERSION
        except sqlite3.Error:
            return False


@contextmanager
def database_context(database: Database):
    token = _database.set(database)
    try:
        yield database
    finally:
        _database.reset(token)


def get_database() -> Database:
    database = _database.get()
    if database is None:
        raise RuntimeError("数据库资源未启动，请使用应用 lifespan 或 database_context")
    return database


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    with get_database().transaction() as conn:
        yield conn


transaction = get_connection
