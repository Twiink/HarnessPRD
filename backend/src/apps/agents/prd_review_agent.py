"""PRD Review Agent - 负责审查 PRD 草稿并返回结构化意见"""

from typing import Any, Dict, cast

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from apps.agents.contracts import ReviewResult
from apps.agents.review import extract_json_object, build_review_repair_prompt

from apps.llm.messages import ConversationInput, build_lc_messages, message_text
from apps.llm.factory import get_tracked_llm
from apps.llm.metrics import LlmStep
from apps.services.prompts import get_prompt


class PrdReviewAgent:
    """独立的 PRD reviewer agent，专注于找问题，不负责改稿。"""

    async def review(
        self,
        conversation_messages: ConversationInput,
        prd_draft: str,
        review_context: str = "",
    ) -> ReviewResult:
        llm = get_tracked_llm(LlmStep.PRD_REVIEW.value, temperature=0)
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
        try:
            review_result = extract_json_object(raw_content)
        except Exception:
            repair_messages = [
                SystemMessage(content=get_prompt("JSON_REPAIR_SYSTEM_PROMPT")),
                HumanMessage(content=build_review_repair_prompt(raw_content)),
            ]
            repair_llm = get_tracked_llm(LlmStep.JSON_REPAIR.value, temperature=0)
            repair_response = await repair_llm.ainvoke(repair_messages)
            repaired_content = message_text(repair_response.content).strip()
            try:
                review_result = extract_json_object(repaired_content)
            except Exception:
                regenerate_messages = [
                    SystemMessage(content=get_prompt("PRD_REVIEWER_SYSTEM_PROMPT")),
                    HumanMessage(
                        content=get_prompt("PRD_REVIEW_REGENERATION_PROMPT_TEMPLATE").format(
                            review_context=review_context.strip() or "（无额外上下文）",
                            prd_draft=prd_draft,
                        )
                    ),
                ]
                regenerate_llm = get_tracked_llm(LlmStep.JSON_REGENERATE.value, temperature=0)
                regenerate_response = await regenerate_llm.ainvoke(regenerate_messages)
                regenerated_content = message_text(regenerate_response.content).strip()
                review_result = extract_json_object(regenerated_content)
        review_result.setdefault("passed", False)
        review_result.setdefault("summary", "")
        review_result.setdefault("issues", [])
        return cast(ReviewResult, review_result)
