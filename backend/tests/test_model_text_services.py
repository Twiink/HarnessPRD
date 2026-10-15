"""Interactive and document use cases accept native model text blocks."""

import asyncio
from types import SimpleNamespace

import pytest

from apps.services.conversations.dialogue import ConversationService
from apps.services.generation.documents import DocumentService


class TextBlockModel:
    async def ainvoke(self, messages):
        return SimpleNamespace(content=[{"type": "text", "text": "draft"}])

    async def astream(self, messages):
        yield SimpleNamespace(
            content=[
                {"type": "text", "text": "draft"},
                {"type": "tool_use", "text": "hidden", "id": "tool"},
                {"type": "text", "text": None},
            ]
        )


class PassingReviewer:
    async def review(self, *args, **kwargs):
        return {"passed": True, "summary": "ok", "issues": []}


@pytest.mark.parametrize("operation", ["start", "continue"])
def test_conversation_normalizes_stream_content_with_injected_factory(operation):
    async def run():
        service = ConversationService(llm_factory=lambda *args, **kwargs: TextBlockModel())
        stream = (
            service.start_conversation_stream("idea")
            if operation == "start"
            else service.continue_conversation_stream("conv", [], "idea")
        )
        return [event async for event in stream]

    events = asyncio.run(run())
    assert events[0] == {"type": "chunk", "content": "draft"}
    assert events[-1]["messages"][-1]["content"] == "draft"


@pytest.mark.parametrize("operation", ["summary", "api", "prompts", "optimize"])
def test_document_streams_normalize_content_blocks(operation):
    async def run():
        service = DocumentService(llm_factory=lambda *args, **kwargs: TextBlockModel())
        service.prd_reviewer = PassingReviewer()
        service.api_docs_reviewer = PassingReviewer()
        service.prompts_reviewer = PassingReviewer()
        streams = {
            "summary": lambda: service.generate_prd_from_summary_stream({}),
            "api": lambda: service.generate_api_docs_stream("prd", []),
            "prompts": lambda: service.generate_prompts_stream("prd", "api"),
            "optimize": lambda: service.optimize_document_stream("prd", "draft", "improve"),
        }
        return [event async for event in streams[operation]()]

    events = asyncio.run(run())
    text = [event["content"] for event in events if event["type"] in ("chunk", "text_delta")]
    assert text == ["draft"]
    if operation == "summary":
        assert events[-1]["final_prd"] == "draft"
    elif operation != "optimize":
        assert events[-1]["content"] == "draft"


def test_nonstream_document_uses_text_blocks():
    service = DocumentService(llm_factory=lambda *args, **kwargs: TextBlockModel())
    assert asyncio.run(service.generate_prd([])) == {"prd": "draft", "status": "completed"}


def test_summary_sync_reads_text_blocks_and_validates_known_fields():
    class SummaryModel:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, messages):
            self.calls += 1
            text = '{"features":42}' if self.calls == 1 else '{"features":["Login"]}'
            return SimpleNamespace(content=[{"type": "text", "text": text}])

    model = SummaryModel()
    service = DocumentService(llm_factory=lambda *args, **kwargs: model)
    result = asyncio.run(service.sync_summary_from_conversation({}, []))
    assert model.calls == 2
    assert result["requirements_summary"]["features"][0]["name"] == "Login"
