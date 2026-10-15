"""Review output must be validated before it can pass a quality gate."""

import asyncio
import importlib
import json
from types import SimpleNamespace

import pytest


AGENTS = [
    ("prd_review_agent", "PrdReviewAgent", ([], "draft"), 3),
    ("api_docs_review_agent", "ApiDocsReviewAgent", ("prd", "api"), 2),
    ("prompts_review_agent", "PromptsReviewAgent", ("prd", "prompts"), 2),
]


class Responses:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        return SimpleNamespace(content=next(self.values))


@pytest.mark.parametrize("module_name,class_name,args,attempts", AGENTS)
@pytest.mark.parametrize(
    "invalid",
    [
        {"passed": "false", "summary": "bad", "issues": []},
        {"passed": True, "summary": {"text": "ok"}, "issues": []},
        {"passed": True, "summary": "ok", "issues": "none"},
        {"passed": True, "summary": "ok", "issues": ["bad"]},
        {"passed": True, "summary": "ok", "issues": [{"problem": ["bad"]}]},
    ],
)
def test_invalid_review_exhausts_bounded_repair_and_fails_closed(
    monkeypatch, module_name, class_name, args, attempts, invalid
):
    module = importlib.import_module(f"apps.agents.{module_name}")
    model = Responses([json.dumps(invalid)] * attempts)
    monkeypatch.setattr(module, "get_tracked_llm", lambda *args, **kwargs: model)
    result = asyncio.run(getattr(module, class_name)().review(*args))
    assert result["passed"] is False
    assert result["issues"][0]["problem"] == "Review 结果解析失败"
    assert model.calls == attempts


@pytest.mark.parametrize("module_name,class_name,args,attempts", AGENTS)
def test_invalid_type_can_be_repaired_to_valid_boolean(
    monkeypatch, module_name, class_name, args, attempts
):
    module = importlib.import_module(f"apps.agents.{module_name}")
    model = Responses(
        [
            '{"passed":"false","summary":"bad","issues":[]}',
            [{"type": "text", "text": '{"passed":true,"summary":"ok","issues":[]}'}],
        ]
    )
    monkeypatch.setattr(module, "get_tracked_llm", lambda *args, **kwargs: model)
    assert asyncio.run(getattr(module, class_name)().review(*args)) == {
        "passed": True,
        "summary": "ok",
        "issues": [],
    }
    assert model.calls == 2
