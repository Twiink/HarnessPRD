"""持久化事件为权威来源；内存只用于唤醒，不积累流数据。"""

import asyncio
import json
from contextlib import contextmanager
from typing import Any, AsyncIterator

from apps.db.repositories.events import EventRepository
from apps.db.repositories.jobs import JobRepository
from apps.domain.jobs import TERMINAL_STATUSES


def sse_frame(event: dict[str, Any]) -> str:
    sequence = event["sequence"]
    payload = {
        **event["payload"],
        "job_id": event["job_id"],
        "sequence": sequence,
        "created_at": event["created_at"],
    }
    return f"id: {sequence}\nevent: {event['event_type']}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class EventBroker:
    def __init__(self, repository: EventRepository, jobs: JobRepository):
        self.repository = repository
        self.jobs = jobs
        self._subscribers: dict[str, set[asyncio.Event]] = {}
        self.closed = False

    @contextmanager
    def subscribe(self, job_id: str):
        wakeup = asyncio.Event()
        self._subscribers.setdefault(job_id, set()).add(wakeup)
        try:
            yield wakeup
        finally:
            self._subscribers[job_id].discard(wakeup)
            if not self._subscribers[job_id]:
                del self._subscribers[job_id]

    def notify(self, job_id: str) -> None:
        for wakeup in self._subscribers.get(job_id, ()):
            wakeup.set()

    def close(self) -> None:
        self.closed = True
        for job_id in tuple(self._subscribers):
            self.notify(job_id)

    async def stream(self, job_id: str, after: int = 0) -> AsyncIterator[str]:
        # 先订阅再查询，clear也在查询前；连接期间发生的新事件不会掉在回放与订阅的缝隙。
        with self.subscribe(job_id) as wakeup:
            while not self.closed:
                wakeup.clear()
                batch = await asyncio.to_thread(self.repository.list, job_id, after)
                for event in batch:
                    after = event["sequence"]
                    yield sse_frame(event)
                if batch:
                    continue
                job = await asyncio.to_thread(self.jobs.get, job_id)
                if job["status"] in TERMINAL_STATUSES:
                    # 终态和终态事件同事务写入，再查询一次可覆盖并发提交。
                    while True:
                        final = await asyncio.to_thread(self.repository.list, job_id, after)
                        if not final:
                            break
                        for event in final:
                            after = event["sequence"]
                            yield sse_frame(event)
                    yield "data: [DONE]\n\n"
                    return
                try:
                    await asyncio.wait_for(wakeup.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    # DB轮询同时支持跨进程写入和心跳，不依赖同进程广播。
                    yield ": keep-alive\n\n"
