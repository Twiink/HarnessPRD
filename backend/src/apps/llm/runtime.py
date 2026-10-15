"""Application-owned capacity shared by jobs and interactive model calls."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator
from weakref import WeakKeyDictionary

from apps.core.errors import DomainError

logger = logging.getLogger(__name__)


def _busy() -> DomainError:
    return DomainError("模型服务繁忙，请稍后重试", code="LLM_BUSY", status_code=503, retryable=True)


class LLMRuntime:
    def __init__(self, max_concurrency: int = 2):
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self.capacity = asyncio.Semaphore(max_concurrency)
        self._tasks: set[asyncio.Future[Any]] = set()
        self._closing = False
        self._closed = asyncio.Event()

    async def start(
        self, factory: Callable[[], Awaitable[Any]], *, capacity_timeout: float
    ) -> asyncio.Future[Any]:
        """Own the permit until provider work and its cleanup actually finish."""
        if self._closing:
            raise _busy()
        acquire = asyncio.create_task(self.capacity.acquire())
        closing = asyncio.create_task(self._closed.wait())
        accepted = False
        try:
            done, _ = await asyncio.wait(
                {acquire, closing}, timeout=capacity_timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if acquire not in done or self._closing:
                raise _busy()
            acquire.result()
            accepted = True
        finally:
            closing.cancel()
            if not acquire.done():
                acquire.cancel()
            elif not accepted and not acquire.cancelled() and acquire.exception() is None:
                self.capacity.release()
        try:
            task = asyncio.ensure_future(factory())
        except BaseException:
            self.capacity.release()
            raise
        self._tasks.add(task)

        def finished(completed: asyncio.Future[Any]) -> None:
            self._tasks.discard(completed)
            self.capacity.release()
            if not completed.cancelled():
                completed.exception()

        task.add_done_callback(finished)
        return task

    async def close(self, timeout: float) -> int:
        """Cancel providers, wait within the shutdown budget, and report stragglers."""
        self._closing = True
        self._closed.set()
        active = {task for task in self._tasks if not task.done()}
        for task in active:
            task.cancel()
        if active:
            await asyncio.wait(active, timeout=timeout)
        remaining = sum(not task.done() for task in self._tasks)
        if remaining:
            logger.error("LLM runtime shutdown has %d unfinished provider tasks", remaining)
        return remaining


_runtime: ContextVar[LLMRuntime | None] = ContextVar("llm_runtime", default=None)
_fallback_runtimes: WeakKeyDictionary[asyncio.AbstractEventLoop, dict[int, LLMRuntime]] = (
    WeakKeyDictionary()
)


def get_llm_runtime(max_concurrency: int = 2) -> LLMRuntime:
    """Prefer explicit application ownership; keep standalone callers compatible."""
    runtime = _runtime.get()
    if runtime is not None:
        return runtime
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Standalone synchronous construction has no loop to share yet. The
        # wrapper resolves its fallback on first use instead.
        raise RuntimeError("Bind llm_runtime_context or resolve runtime inside an async call")
    by_capacity = _fallback_runtimes.setdefault(loop, {})
    return by_capacity.setdefault(max_concurrency, LLMRuntime(max_concurrency))


def current_llm_runtime() -> LLMRuntime | None:
    return _runtime.get()


@contextmanager
def llm_runtime_context(runtime: LLMRuntime) -> Iterator[LLMRuntime]:
    token = _runtime.set(runtime)
    try:
        yield runtime
    finally:
        _runtime.reset(token)
