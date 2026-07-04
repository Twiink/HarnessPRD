"""同进程 Job 事件广播 — SSE 订阅者与 runner 解耦"""

import asyncio
from typing import Dict, List

_subscribers: Dict[str, List[asyncio.Queue]] = {}


def subscribe(job_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(job_id, []).append(queue)
    return queue


def unsubscribe(job_id: str, queue: asyncio.Queue) -> None:
    queues = _subscribers.get(job_id)
    if not queues:
        return
    try:
        queues.remove(queue)
    except ValueError:
        return
    if not queues:
        _subscribers.pop(job_id, None)


async def publish(job_id: str, event: dict) -> None:
    for queue in list(_subscribers.get(job_id, [])):
        await queue.put(event)
