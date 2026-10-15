"""API 文档 Review Agent（仅 Review，不 Rewrite）。"""

from __future__ import annotations

from typing import Any, Callable, Dict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from apps.agents.contracts import ReviewResult
from apps.agents.review import review_with_repair

from apps.llm.messages import message_text
from apps.llm.factory import get_tracked_llm
from apps.llm.metrics import LlmStep
from apps.core.resources.prompts import get_prompt, get_api_docs_review_prompt
from apps.domain.reviews import normalize_document_review


def _normalize_review(parsed: Dict[str, Any]) -> ReviewResult:
    return normalize_document_review(parsed, default_section="接口文档")


class ApiDocsReviewAgent:
    def __init__(self, llm_factory: Callable[..., Any] | None = None):
        self._llm_factory = llm_factory

    async def review(self, prd_content: str, api_docs_content: str) -> ReviewResult:
        factory = self._llm_factory or get_tracked_llm
        llm = factory(LlmStep.API_DOCS_REVIEW.value, temperature=0)
        messages = [
            SystemMessage(content=get_prompt("API_DOCS_REVIEW_SYSTEM_PROMPT")),
            HumanMessage(content=get_api_docs_review_prompt(prd_content, api_docs_content)),
        ]
        response = await llm.ainvoke(messages)
        raw_content = message_text(response.content).strip()
        return await review_with_repair(raw_content, "接口文档", factory)
