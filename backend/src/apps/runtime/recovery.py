"""过期租约回收；有效租约留给原执行者，避免重启时重复执行。"""

from typing import Callable

from apps.db.migrations import now_iso
from apps.db.repositories.jobs import JobRepository


def recover_expired(
    jobs: JobRepository,
    max_attempts: int,
    fail: Callable[[str, str, str], None],
    cancel: Callable[[str], None],
) -> None:
    for expired in jobs.expired():
        with jobs.database.transaction():
            current = jobs.get(expired["id"])
            if current["status"] != "running" or (
                current["lease_until"] and current["lease_until"] > now_iso()
            ):
                continue
            if current["cancel_requested"]:
                cancel(current["id"])
            elif current["attempt_count"] >= max_attempts:
                fail(current["id"], "ATTEMPTS_EXHAUSTED", "任务中断且重试次数已耗尽")
            else:
                jobs.interrupt(current["id"], current["worker_id"], current["attempt_count"])
                jobs.requeue(current["id"])
