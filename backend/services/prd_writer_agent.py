"""PRD Writer Agent - 负责起草与修订 PRD 文档"""

from typing import Any, AsyncGenerator, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from services.conversation_service import _build_lc_messages
from services.llm_factory import get_llm
from services.prompts import (
    PRD_GENERATION_PROMPT,
    PRD_REWRITE_PROMPT_TEMPLATE,
    PRD_WRITER_SYSTEM_PROMPT,
)


class PrdWriterAgent:
    """独立的 PRD writer agent，专注于文档写作。"""

    async def write_stream(
        self,
        conversation_messages: List[Dict[str, str]],
    ) -> AsyncGenerator[Dict[str, str], None]:
        llm = get_llm(temperature=0.3)
        lc_messages = [SystemMessage(content=PRD_WRITER_SYSTEM_PROMPT)]
        lc_messages.extend(_build_lc_messages(conversation_messages))
        lc_messages.append(HumanMessage(content=PRD_GENERATION_PROMPT))

        async for chunk in llm.astream(lc_messages):
            if chunk.content:
                yield {"type": "text_delta", "phase": "writer", "content": chunk.content}

    async def rewrite_stream(
        self,
        conversation_messages: List[Dict[str, str]],
        current_draft: str,
        review_result: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, str], None]:
        llm = get_llm(temperature=0.2)
        lc_messages = [SystemMessage(content=PRD_WRITER_SYSTEM_PROMPT)]
        lc_messages.extend(_build_lc_messages(conversation_messages))
        lc_messages.append(
            HumanMessage(
                content=PRD_REWRITE_PROMPT_TEMPLATE.format(
                    current_draft=current_draft,
                    review_result=review_result,
                )
            )
        )

        async for chunk in llm.astream(lc_messages):
            if chunk.content:
                yield {"type": "text_delta", "phase": "rewrite", "content": chunk.content}
