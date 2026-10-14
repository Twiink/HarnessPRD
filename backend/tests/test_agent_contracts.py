"""使用本地模型替身验证 Agent 的输入、输出与流事件。"""

import asyncio
import importlib
from types import SimpleNamespace

import pytest


def agent_module(name):
    return importlib.import_module(f"apps.agents.{name}")


class FakeModel:
    def __init__(self, responses=(), chunks=()):
        self.responses = iter(responses)
        self.chunks = chunks
        self.messages = []

    async def ainvoke(self, messages):
        self.messages.append(messages)
        return SimpleNamespace(content=next(self.responses))

    async def astream(self, messages):
        self.messages.append(messages)
        for content in self.chunks:
            yield SimpleNamespace(content=content)


def test_writer_and_rewrite_stream_contract(monkeypatch):
    module = agent_module("prd_writer_agent")
    model = FakeModel(chunks=("hello", "", " world"))
    monkeypatch.setattr(module, "get_tracked_llm", lambda *args, **kwargs: model)

    async def run():
        agent = module.PrdWriterAgent()
        messages = [{"role": "user", "content": "input"}]
        written = [event async for event in agent.write_stream(messages)]
        revised = [
            event async for event in agent.rewrite_stream(messages, "draft", {"passed": False})
        ]
        return written, revised

    written, revised = asyncio.run(run())
    assert written == [
        {"type": "text_delta", "phase": "writer", "content": "hello"},
        {"type": "text_delta", "phase": "writer", "content": " world"},
    ]
    assert [event["phase"] for event in revised] == ["rewrite", "rewrite"]
    assert model.messages[0][1].content == "input"


def test_writer_accepts_text_content_blocks(monkeypatch):
    module = agent_module("prd_writer_agent")
    model = FakeModel(
        chunks=(
            [
                {"type": "text", "text": "hello"},
                {"type": "tool_use", "id": "tool"},
                " world",
            ],
        )
    )
    monkeypatch.setattr(module, "get_tracked_llm", lambda *args, **kwargs: model)

    async def run():
        return [event async for event in module.PrdWriterAgent().write_stream([])]

    assert asyncio.run(run()) == [
        {"type": "text_delta", "phase": "writer", "content": "hello world"}
    ]


def test_same_agent_resolves_prompts_for_each_application(tmp_path, monkeypatch):
    from apps.core.config import Settings, settings_context

    module = agent_module("prd_writer_agent")
    model = FakeModel(chunks=("output",))
    monkeypatch.setattr(module, "get_tracked_llm", lambda *args, **kwargs: model)
    agent = module.PrdWriterAgent()

    async def run():
        for name in ("one", "two"):
            root = tmp_path / name
            (root / "prompts").mkdir(parents=True)
            (root / "prompts" / "PRD_WRITER_SYSTEM_PROMPT.md").write_text(name)
            (root / "prompts" / "PRD_GENERATION_PROMPT.md").write_text("generate")
            with settings_context(Settings(_env_file=None, resources_dir=root)):
                [event async for event in agent.write_stream([])]

    asyncio.run(run())
    assert [messages[0].content for messages in model.messages] == ["one", "two"]


@pytest.mark.parametrize(
    "name,cls,args",
    [
        ("prd_review_agent", "PrdReviewAgent", ([], "draft")),
        ("api_docs_review_agent", "ApiDocsReviewAgent", ("prd", "api")),
        ("prompts_review_agent", "PromptsReviewAgent", ("prd", "prompts")),
    ],
)
def test_reviews_repair_json_and_return_required_fields(monkeypatch, name, cls, args):
    module = agent_module(name)
    model = FakeModel(
        responses=("invalid", '```json\n{"passed": true, "summary": "ok", "issues": []}\n```')
    )
    steps = []

    def factory(step, **kwargs):
        steps.append(step)
        return model

    monkeypatch.setattr(module, "get_tracked_llm", factory)
    result = asyncio.run(getattr(module, cls)().review(*args))
    assert result == {"passed": True, "summary": "ok", "issues": []}
    assert steps[-1] == "json_repair"


@pytest.mark.parametrize(
    "name,cls",
    [
        ("api_docs_review_agent", "ApiDocsReviewAgent"),
        ("prompts_review_agent", "PromptsReviewAgent"),
    ],
)
def test_document_review_parse_failure_is_explicit(monkeypatch, name, cls):
    module = agent_module(name)
    model = FakeModel(responses=("invalid", "still invalid"))
    monkeypatch.setattr(module, "get_tracked_llm", lambda *args, **kwargs: model)
    result = asyncio.run(getattr(module, cls)().review("prd", "document"))
    assert result["passed"] is False
    assert result["issues"][0]["problem"] == "Review 结果解析失败"


def test_prd_review_regenerates_after_failed_repair(monkeypatch):
    module = agent_module("prd_review_agent")
    model = FakeModel(responses=("invalid", "invalid", '{"passed": false}'))
    monkeypatch.setattr(module, "get_tracked_llm", lambda *args, **kwargs: model)
    result = asyncio.run(module.PrdReviewAgent().review([], "draft"))
    assert result == {"passed": False, "summary": "", "issues": []}
    assert len(model.messages) == 3


def test_public_message_builder_preserves_role_mapping():
    from apps.llm.messages import build_lc_messages

    result = build_lc_messages(
        [
            {"role": role, "content": role}
            for role in ("system", "user", "human", "assistant", "ai", "unknown")
        ]
    )
    assert [message.type for message in result] == ["system", "human", "human", "ai", "ai"]


def test_injected_resources_are_used_by_prompts_and_documents(tmp_path):
    from apps.core.config import Settings, settings_context
    from apps.services.document_service import _load_prd_template
    from apps.services.prompts import get_prompt

    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "SYSTEM_PROMPT.md").write_text("injected system prompt")
    (tmp_path / "prd_template.md").write_text("injected template")
    with settings_context(Settings(_env_file=None, resources_dir=tmp_path)):
        assert get_prompt("SYSTEM_PROMPT") == "injected system prompt"
        assert _load_prd_template() == "injected template"


def test_prompt_templates_keep_literal_json_braces():
    from apps.services.prompts import get_api_docs_review_prompt, get_prompts_review_prompt

    for build in (get_api_docs_review_prompt, get_prompts_review_prompt):
        text = build("prd context", "document context")
        assert '"passed": true' in text
        assert "prd context" in text
        assert "document context" in text


def test_tracked_model_retains_its_budget_and_redacts_metric_errors(tmp_path):
    from langchain_core.messages import HumanMessage

    from apps.core.config import Settings, settings_context
    from apps.llm.metrics import RunMetricsCollector
    from apps.llm.token_budget import BudgetExceededError
    from apps.llm.tracking import TrackedChatModel

    registry = tmp_path / "models.yaml"
    registry.write_text(
        "models:\n  default:\n    context_window: 1000\n    max_output_tokens: 100\n"
    )
    bounded = Settings(
        _env_file=None,
        models_config_path=registry,
        token_estimator="char_heuristic",
        context_budget_tokens=1,
        token_budget_mode="reject",
    )
    with settings_context(bounded):
        tracked = TrackedChatModel(FakeModel(responses=("unused",)), "test")

    async def reject():
        with settings_context(Settings(_env_file=None, context_budget_tokens=100000)):
            with pytest.raises(BudgetExceededError):
                await tracked.ainvoke([HumanMessage(content="long text")])

    asyncio.run(reject())

    class BrokenModel:
        async def ainvoke(self, messages):
            raise RuntimeError("private-metric-key Bearer private-bearer")

    configured = Settings(
        _env_file=None, models_config_path=registry, openai_api_key="private-metric-key"
    )
    with settings_context(configured):
        tracked = TrackedChatModel(BrokenModel(), "test")

    async def record_error():
        collector = RunMetricsCollector.start("test")
        try:
            with pytest.raises(RuntimeError):
                await tracked.ainvoke([])
        finally:
            summary = collector.finish()
        return summary.steps[0].error

    error = asyncio.run(record_error())
    assert "private-metric-key" not in error
    assert "private-bearer" not in error
