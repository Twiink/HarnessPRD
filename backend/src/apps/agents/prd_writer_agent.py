"""PRD Writer Agent - 负责起草与修订 PRD 文档"""

from typing import Any, AsyncGenerator, Callable

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from apps.agents.contracts import ReviewResult, TextDeltaEvent

from apps.llm.messages import ConversationInput, build_lc_messages, message_text
from apps.llm.factory import get_tracked_llm
from apps.llm.metrics import LlmStep
from apps.core.resources.prompts import get_prompt


class PrdWriterAgent:
    """独立的 PRD writer agent，专注于文档写作。"""

    def __init__(self, llm_factory: Callable[..., Any] | None = None):
        self._llm_factory = llm_factory

    async def write_stream(
        self,
        conversation_messages: ConversationInput,
    ) -> AsyncGenerator[TextDeltaEvent, None]:
        llm = (self._llm_factory or get_tracked_llm)(LlmStep.PRD_WRITER.value, temperature=0.3)
        lc_messages: list[BaseMessage] = [
            SystemMessage(content=get_prompt("PRD_WRITER_SYSTEM_PROMPT"))
        ]
        lc_messages.extend(build_lc_messages(conversation_messages))
        lc_messages.append(HumanMessage(content=get_prompt("PRD_GENERATION_PROMPT")))

        async for chunk in llm.astream(lc_messages):
            text = message_text(chunk.content)
            if text:
                yield {"type": "text_delta", "phase": "writer", "content": text}

    async def rewrite_stream(
        self,
        conversation_messages: ConversationInput,
        current_draft: str,
        review_result: ReviewResult,
    ) -> AsyncGenerator[TextDeltaEvent, None]:
        llm = (self._llm_factory or get_tracked_llm)(LlmStep.PRD_REWRITE.value, temperature=0.2)
        lc_messages: list[BaseMessage] = [
            SystemMessage(content=get_prompt("PRD_WRITER_SYSTEM_PROMPT"))
        ]
        lc_messages.extend(build_lc_messages(conversation_messages))
        lc_messages.append(
            HumanMessage(
                content=get_prompt("PRD_REWRITE_PROMPT_TEMPLATE").format(
                    current_draft=current_draft,
                    review_result=review_result,
                )
            )
        )

        async for chunk in llm.astream(lc_messages):
            text = message_text(chunk.content)
            if text:
                yield {"type": "text_delta", "phase": "rewrite", "content": text}
