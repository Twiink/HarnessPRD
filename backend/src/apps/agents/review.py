"""Shared strict validation and bounded repair for review agents."""

from typing import Any, Callable

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from apps.core.resources.prompts import get_prompt
from apps.domain.reviews import (
    ReviewResult,
    build_parse_failed_review,
    normalize_document_review,
)
from apps.llm.json_output import extract_json_object
from apps.llm.messages import message_text
from apps.llm.metrics import LlmStep


def build_review_repair_prompt(raw_text: str) -> str:
    return get_prompt("REVIEW_REPAIR_PROMPT_TEMPLATE").format(raw_text=raw_text)


async def review_with_repair(
    raw_content: str,
    default_section: str,
    llm_factory: Callable[..., Any],
    regeneration_messages: list[BaseMessage] | None = None,
    *,
    fill_failed_issue: bool = True,
) -> ReviewResult:
    attempts: list[tuple[str, list[BaseMessage]]] = [
        (
            LlmStep.JSON_REPAIR.value,
            [
                SystemMessage(content=get_prompt("JSON_REPAIR_SYSTEM_PROMPT")),
                HumanMessage(content=build_review_repair_prompt(raw_content)),
            ],
        )
    ]
    if regeneration_messages is not None:
        attempts.append((LlmStep.JSON_REGENERATE.value, regeneration_messages))
    for attempt in range(len(attempts) + 1):
        try:
            return normalize_document_review(
                extract_json_object(raw_content),
                default_section,
                fill_failed_issue=fill_failed_issue,
            )
        except ValueError:
            if attempt == len(attempts):
                return build_parse_failed_review(default_section)
        step, messages = attempts[attempt]
        response = await llm_factory(step, temperature=0).ainvoke(messages)
        raw_content = message_text(response.content).strip()
    raise AssertionError("unreachable review repair state")
