"""Deterministic model doubles exercise timeout and application capacity limits."""

import asyncio
from types import SimpleNamespace

import pytest

from apps.core.config import Settings, settings_context
from apps.core.errors import DomainError
from apps.llm.tracking import TrackedChatModel


def test_call_timeout_has_stable_retryable_error_and_releases_capacity():
    class SlowModel:
        async def ainvoke(self, messages):
            await asyncio.Event().wait()

    async def run():
        settings = Settings(_env_file=None, llm_call_timeout=0.01)
        with settings_context(settings):
            model = TrackedChatModel(SlowModel(), "test")
            with pytest.raises(DomainError) as caught:
                await model.ainvoke([])
            assert caught.value.code == "LLM_CALL_TIMEOUT"
            assert caught.value.retryable is True

    asyncio.run(run())


def test_stream_idle_timeout_closes_stream_and_resets_between_chunks():
    class SlowStream:
        closed = False

        async def astream(self, messages):
            try:
                yield SimpleNamespace(content="first")
                await asyncio.Event().wait()
            finally:
                self.closed = True

    async def run():
        underlying = SlowStream()
        settings = Settings(_env_file=None, llm_stream_idle_timeout=0.01)
        with settings_context(settings):
            model = TrackedChatModel(underlying, "test")
            chunks = []
            with pytest.raises(DomainError) as caught:
                async for chunk in model.astream([]):
                    chunks.append(chunk.content)
            assert chunks == ["first"]
            assert caught.value.code == "LLM_STREAM_IDLE_TIMEOUT"
            assert caught.value.retryable is True
            assert underlying.closed

    asyncio.run(run())


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("cancel_requested", [False, True])
def test_timeout_discards_late_provider_result_when_cancellation_is_suppressed(
    streaming, cancel_requested
):
    from apps.llm.runtime import LLMRuntime, llm_runtime_context

    class StubbornModel:
        def __init__(self):
            self.release = asyncio.Event()
            self.finished = asyncio.Event()
            self.cancelled = asyncio.Event()
            self.started = asyncio.Event()

        async def ainvoke(self, messages):
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled.set()
                await self.release.wait()
                self.finished.set()
                return SimpleNamespace(content="late")

        async def astream(self, messages):
            yield await self.ainvoke(messages)

    class QuickModel:
        async def ainvoke(self, messages):
            return SimpleNamespace(content="next")

    async def run():
        raw = StubbornModel()
        settings = Settings(_env_file=None, llm_call_timeout=0.01, llm_stream_idle_timeout=0.01)
        with settings_context(settings), llm_runtime_context(LLMRuntime(max_concurrency=1)):
            tracked = TrackedChatModel(raw, "stubborn")

            async def invoke():
                if streaming:
                    return [chunk.content async for chunk in tracked.astream([])]
                return await tracked.ainvoke([])

            task = asyncio.create_task(invoke())
            try:
                await raw.started.wait()
                if cancel_requested:
                    task.cancel()
                done, _ = await asyncio.wait({task}, timeout=0.3)
                assert task in done, "timeout waited for the cancellation-suppressing provider"
                with pytest.raises(asyncio.CancelledError if cancel_requested else DomainError):
                    task.result()
                assert raw.cancelled.is_set()
                assert not raw.finished.is_set()
                with pytest.raises(DomainError) as busy:
                    await TrackedChatModel(QuickModel(), "next").ainvoke([])
                assert busy.value.code == "LLM_BUSY"
                assert busy.value.retryable
            finally:
                raw.release.set()
                await asyncio.wait_for(raw.finished.wait(), timeout=0.3)
                await asyncio.sleep(0)
            assert (await TrackedChatModel(QuickModel(), "next").ainvoke([])).content == "next"

    asyncio.run(run())


def test_stubborn_providers_keep_capacity_until_exit_without_unhandled_errors():
    from apps.llm.runtime import LLMRuntime, llm_runtime_context

    class StubbornProvider:
        def __init__(self):
            self.active = 0
            self.maximum = 0
            self.entered = 0
            self.release = asyncio.Event()

        async def ainvoke(self, messages):
            self.entered += 1
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            try:
                while not self.release.is_set():
                    try:
                        await self.release.wait()
                    except asyncio.CancelledError:
                        pass
                raise RuntimeError("late provider failure")
            finally:
                self.active -= 1

    async def run():
        loop = asyncio.get_running_loop()
        unhandled = []
        loop.set_exception_handler(lambda loop, context: unhandled.append(context))
        raw = StubbornProvider()
        runtime = LLMRuntime(max_concurrency=2)
        settings = Settings(_env_file=None, llm_call_timeout=0.01)
        with settings_context(settings), llm_runtime_context(runtime):
            tracked = TrackedChatModel(raw, "stubborn")
            try:
                results = await asyncio.gather(
                    tracked.ainvoke([]), tracked.ainvoke([]), return_exceptions=True
                )
                assert all(isinstance(error, DomainError) for error in results)
                assert raw.active == 2
                with pytest.raises(DomainError) as caught:
                    await tracked.ainvoke([])
                assert caught.value.code == "LLM_BUSY"
                assert raw.entered == 2
                assert raw.maximum == 2
            finally:
                raw.release.set()
                await runtime.close(timeout=0.3)
            assert raw.active == 0
            assert not unhandled

    asyncio.run(run())


@pytest.mark.parametrize("stubborn", [False, True])
def test_runtime_shutdown_is_bounded_and_reports_stubborn_tasks(stubborn):
    from apps.llm.runtime import LLMRuntime, llm_runtime_context

    class Provider:
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def ainvoke(self, messages):
            self.started.set()
            while not self.release.is_set():
                try:
                    await self.release.wait()
                except asyncio.CancelledError:
                    if not stubborn:
                        raise
            return SimpleNamespace(content="late")

    async def run():
        runtime = LLMRuntime(max_concurrency=1)
        raw = Provider()
        with llm_runtime_context(runtime):
            model = TrackedChatModel(raw, "shutdown")
            request = asyncio.create_task(model.ainvoke([]))
            await raw.started.wait()
            try:
                remaining = await runtime.close(timeout=0.01)
                assert remaining == int(stubborn)
                with pytest.raises(DomainError) as busy:
                    await model.ainvoke([])
                assert busy.value.code == "LLM_BUSY"
            finally:
                raw.release.set()
                await asyncio.gather(request, return_exceptions=True)
                assert await runtime.close(timeout=0.3) == 0

    asyncio.run(run())


def test_stream_close_retains_capacity_and_shutdown_tracks_slow_cleanup():
    from apps.llm.runtime import LLMRuntime, llm_runtime_context

    class SlowClosingStream:
        def __init__(self):
            self.close_started = asyncio.Event()
            self.release_close = asyncio.Event()
            self.first = True

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.first:
                self.first = False
                return SimpleNamespace(content="first")
            await asyncio.Event().wait()

        async def aclose(self):
            self.close_started.set()
            await self.release_close.wait()
            raise RuntimeError("late close failure")

    class Provider:
        def __init__(self):
            self.stream = SlowClosingStream()

        def astream(self, messages):
            return self.stream

    async def run():
        raw = Provider()
        runtime = LLMRuntime(max_concurrency=1)
        settings = Settings(_env_file=None, llm_call_timeout=0.01)
        loop = asyncio.get_running_loop()
        unhandled = []
        loop.set_exception_handler(lambda loop, context: unhandled.append(context))
        with settings_context(settings), llm_runtime_context(runtime):
            tracked = TrackedChatModel(raw, "slow-close")
            stream = tracked.astream([])
            assert (await stream.__anext__()).content == "first"
            await stream.aclose()
            await raw.stream.close_started.wait()
            try:
                with pytest.raises(DomainError) as busy:
                    await tracked.ainvoke([])
                assert busy.value.code == "LLM_BUSY"
                waiting = asyncio.create_task(tracked.ainvoke([]))
                assert await runtime.close(timeout=0.01) == 1
                with pytest.raises(DomainError) as closed:
                    await asyncio.wait_for(waiting, timeout=0.1)
                assert closed.value.code == "LLM_BUSY"
            finally:
                raw.stream.release_close.set()
                assert await runtime.close(timeout=0.3) == 0
                await asyncio.sleep(0)
            assert not unhandled

    asyncio.run(run())


def test_shared_runtime_limits_calls_and_streams_and_releases_after_cancel():
    from apps.llm.runtime import LLMRuntime, llm_runtime_context

    class BlockingModel:
        def __init__(self):
            self.active = 0
            self.maximum = 0
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def ainvoke(self, messages):
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            self.started.set()
            try:
                await self.release.wait()
                return SimpleNamespace(content="ok")
            finally:
                self.active -= 1

        async def astream(self, messages):
            response = await self.ainvoke(messages)
            yield response

    async def run():
        raw = BlockingModel()
        with llm_runtime_context(LLMRuntime(max_concurrency=1)):
            first = TrackedChatModel(raw, "first")
            second = TrackedChatModel(raw, "second")
        task = asyncio.create_task(first.ainvoke([]))
        await raw.started.wait()

        async def consume():
            return [chunk.content async for chunk in second.astream([])]

        stream = asyncio.create_task(consume())
        await asyncio.sleep(0)
        assert raw.active == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        raw.release.set()
        assert await stream == ["ok"]
        assert raw.maximum == 1
        assert raw.active == 0

    asyncio.run(run())


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_provider_uses_explicit_timeout_without_hidden_retries(monkeypatch, provider):
    from apps.llm import factory

    captured = {}

    def client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(factory, "ChatAnthropic", client)
    monkeypatch.setattr(factory, "ChatOpenAI", client)
    with settings_context(
        Settings(_env_file=None, default_llm_provider=provider, llm_call_timeout=17)
    ):
        factory.get_llm()
    assert captured["timeout"] == 17
    assert captured["max_retries"] == 0
