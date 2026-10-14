"""提示词文档 Review Agent（仅 Review，不 Rewrite）。"""

from __future__ import annotations

from typing import Any, Dict, cast

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from apps.agents.contracts import ReviewResult
from apps.agents.review import extract_json_object, build_review_repair_prompt

from apps.llm.messages import message_text
from apps.llm.factory import get_tracked_llm
from apps.llm.metrics import LlmStep
from apps.services.prompts import get_prompt, get_prompts_review_prompt
from apps.services.review_result_utils import (
    build_parse_failed_review,
    normalize_document_review,
)


def _normalize_review(parsed: Dict[str, Any]) -> ReviewResult:
    return cast(ReviewResult, normalize_document_review(parsed, default_section="提示词"))


class PromptsReviewAgent:
    async def review(self, prd_content: str, prompts_content: str) -> ReviewResult:
        llm = get_tracked_llm(LlmStep.PROMPTS_REVIEW.value, temperature=0)
        messages = [
            SystemMessage(content=get_prompt("PROMPTS_REVIEW_SYSTEM_PROMPT")),
            HumanMessage(content=get_prompts_review_prompt(prd_content, prompts_content)),
        ]
        response = await llm.ainvoke(messages)
        raw_content = message_text(response.content).strip()
        try:
            parsed = extract_json_object(raw_content)
            return _normalize_review(parsed)
        except Exception:
            repair_llm = get_tracked_llm(LlmStep.JSON_REPAIR.value, temperature=0)
            repair_response = await repair_llm.ainvoke(
                [
                    SystemMessage(content=get_prompt("JSON_REPAIR_SYSTEM_PROMPT")),
                    HumanMessage(content=build_review_repair_prompt(raw_content)),
                ]
            )
            try:
                parsed = extract_json_object(message_text(repair_response.content).strip())
                return _normalize_review(parsed)
            except Exception:
                return cast(ReviewResult, build_parse_failed_review("提示词"))
