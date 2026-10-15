"""任务查询用例，数据访问交给仓储。"""

from apps.db.connection import get_database
from apps.db.repositories.jobs import JobRepository


def get_job(job_id: str) -> dict:
    return JobRepository(get_database()).get(job_id)


def get_conflicting_running_job(session_id: str, artifact: str) -> dict | None:
    return JobRepository(get_database()).active(session_id, artifact)


def get_running_job(session_id: str, artifact: str) -> dict | None:
    return get_conflicting_running_job(session_id, artifact)
