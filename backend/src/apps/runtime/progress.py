"""Coalesce adjacent deltas while persisting phase boundaries in order."""

import asyncio
import json
from collections.abc import Awaitable, Callable

from apps.domain.jobs import LeaseLostError


class JobProgress:
    def __init__(
        self,
        persist: Callable[[dict, list[dict]], Awaitable[None]],
        *,
        flush_bytes: int,
    ):
        self.persist = persist
        self.flush_bytes = flush_bytes
        self.revoked = False
        self._lock = asyncio.Lock()
        self._draft = ""
        self._parts: list[str] = []
        self._bytes = 0
        self._first_delta = True
        self._delta_type = "text_delta"

    async def _flush_locked(self) -> None:
        if not self._parts:
            return
        content = "".join(self._parts)
        draft = self._draft + content
        await self.persist(
            {"draft_content": draft}, [{"type": self._delta_type, "content": content}]
        )
        self._draft = draft
        self._parts.clear()
        self._bytes = 0

    async def flush(self) -> None:
        async with self._lock:
            if self.revoked:
                raise LeaseLostError()
            await self._flush_locked()

    async def flush_and_fence(self, revoke: Callable[[], Awaitable[None]]) -> None:
        async with self._lock:
            if not self.revoked:
                await self._flush_locked()
            await revoke()
            self.revoked = True

    async def emit(self, event: dict) -> None:
        async with self._lock:
            if self.revoked:
                raise LeaseLostError()
            event_type = event["type"]
            if event_type in ("done", "run_summary"):
                return
            if event_type in ("chunk", "text_delta"):
                if self._parts and self._delta_type != event_type:
                    await self._flush_locked()
                self._delta_type = event_type
                content = event.get("content") or ""
                self._parts.append(content)
                self._bytes += len(content.encode("utf-8"))
                # Persist the first visible output immediately; later deltas are bounded batches.
                if self._first_delta or self._bytes >= self.flush_bytes:
                    await self._flush_locked()
                    self._first_delta = False
                return
            await self._flush_locked()
            fields = {}
            if event_type == "phase":
                phase = str(event.get("phase") or "")
                fields["phase"] = {
                    "writer_started": "writing",
                    "review_started": "reviewing",
                    "rewrite_started": "rewriting",
                }.get(phase, phase or "generating")
                if phase == "rewrite_started":
                    fields.update(previous_draft=self._draft, draft_content="")
            elif event_type == "review":
                fields["review_json"] = json.dumps(event.get("content"), ensure_ascii=False)
            await self.persist(fields, [event])
            if event_type == "phase" and event.get("phase") == "rewrite_started":
                self._draft = ""
