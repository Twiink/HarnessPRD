"""PRD Review Agent - 负责审查 PRD 草稿并返回结构化意见"""

from typing import Any, Callable

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from apps.agents.contracts import ReviewResult
from apps.agents.review import review_with_repair

from apps.llm.messages import ConversationInput, build_lc_messages, message_text
from apps.llm.factory import get_tracked_llm
from apps.llm.metrics import LlmStep
from apps.core.resources.prompts import get_prompt


class PrdReviewAgent:
    """独立的 PRD reviewer agent，专注于找问题，不负责改稿。"""

    def __init__(self, llm_factory: Callable[..., Any] | None = None):
        self._llm_factory = llm_factory

    async def review(
        self,
        conversation_messages: ConversationInput,
        prd_draft: str,
        review_context: str = "",
    ) -> ReviewResult:
        factory = self._llm_factory or get_tracked_llm
        llm = factory(LlmStep.PRD_REVIEW.value, temperature=0)
        lc_messages: list[BaseMessage] = [
            SystemMessage(content=get_prompt("PRD_REVIEWER_SYSTEM_PROMPT"))
        ]
        lc_messages.extend(build_lc_messages(conversation_messages))
        lc_messages.append(
            HumanMessage(
                content=get_prompt("PRD_REVIEW_PROMPT_TEMPLATE").format(
                    review_context=review_context.strip() or "（无额外上下文）",
                    prd_draft=prd_draft,
                )
            )
        )

        response = await llm.ainvoke(lc_messages)
        raw_content = message_text(response.content).strip()
        regeneration_messages: list[BaseMessage] = [
            SystemMessage(content=get_prompt("PRD_REVIEWER_SYSTEM_PROMPT")),
            HumanMessage(
                content=get_prompt("PRD_REVIEW_REGENERATION_PROMPT_TEMPLATE").format(
                    review_context=review_context.strip() or "（无额外上下文）",
                    prd_draft=prd_draft,
                )
            ),
        ]
        return await review_with_repair(
            raw_content, "PRD", factory, regeneration_messages, fill_failed_issue=False
        )
