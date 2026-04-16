"""文档生成服务 — PRD、接口文档、AI 提示词套件的生成与优化"""

import os
from typing import List, Dict, Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from services.llm_factory import get_llm
from services.prompts import (
    PRD_GENERATION_PROMPT,
    API_DOCS_GENERATION_PROMPT,
    PROMPTS_GENERATION_PROMPT,
    OPTIMIZE_DOCUMENT_PROMPT_TEMPLATE,
)
from services.conversation_service import _build_lc_messages


def _load_prd_template() -> str:
    """读取本地 PRD 格式模板文件，文件不存在或为空则返回空字符串"""
    template_path = os.path.join(os.path.dirname(__file__), "..", "core", "prd_template.md")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content
    except Exception:
        return ""


def _build_prd_prompt() -> str:
    """构建 PRD 生成 prompt，如有模板则附上格式参考"""
    template = _load_prd_template()
    if template:
        return PRD_GENERATION_PROMPT + f"\n\n请参考以下格式模板（仅作格式参考，内容以对话为准）：\n\n{template}"
    return PRD_GENERATION_PROMPT


class DocumentService:
    async def generate_prd(self, conversation_messages: List[Dict[str, str]]) -> Dict[str, Any]:
        llm = get_llm(temperature=0.3)
        lc_messages = _build_lc_messages(conversation_messages)
        lc_messages.append(HumanMessage(content=_build_prd_prompt()))
        response = await llm.ainvoke(lc_messages)
        return {"prd": response.content, "status": "completed"}

    async def generate_prd_stream(
        self,
        conversation_messages: List[Dict[str, str]],
    ) -> AsyncGenerator[Dict, None]:
        llm = get_llm(temperature=0.3)
        lc_messages = _build_lc_messages(conversation_messages)
        lc_messages.append(HumanMessage(content=_build_prd_prompt()))

        async for chunk in llm.astream(lc_messages):
            if chunk.content:
                yield {"type": "chunk", "content": chunk.content}

        yield {"type": "done"}

    async def generate_api_docs_stream(
        self,
        prd_content: str,
        conversation_messages: List[Dict[str, str]],
    ) -> AsyncGenerator[Dict, None]:
        llm = get_llm(temperature=0.3)
        lc_messages = _build_lc_messages(conversation_messages)
        lc_messages.append(HumanMessage(
            content=f"以下是已确认的产品需求文档（PRD）：\n\n{prd_content}\n\n{API_DOCS_GENERATION_PROMPT}"
        ))

        async for chunk in llm.astream(lc_messages):
            if chunk.content:
                yield {"type": "chunk", "content": chunk.content}

        yield {"type": "done"}

    async def generate_prompts_stream(
        self,
        prd_content: str,
        api_docs_content: str,
    ) -> AsyncGenerator[Dict, None]:
        llm = get_llm(temperature=0.5)
        context = f"产品需求文档（PRD）：\n\n{prd_content}"
        if api_docs_content.strip():
            context += f"\n\n接口文档：\n\n{api_docs_content}"
        lc_messages = [
            SystemMessage(content="你是一位 AI 辅助开发专家，专门为 Claude Code 等 AI 编程工具设计高质量的系统提示词。"),
            HumanMessage(content=f"{context}\n\n{PROMPTS_GENERATION_PROMPT}"),
        ]

        async for chunk in llm.astream(lc_messages):
            if chunk.content:
                yield {"type": "chunk", "content": chunk.content}

        yield {"type": "done"}

    async def optimize_document_stream(
        self,
        doc_type: str,
        current_content: str,
        instruction: str,
        context: str = "",
    ) -> AsyncGenerator[Dict, None]:
        doc_type_label_map = {
            "prd": "产品需求文档（PRD）",
            "api-docs": "接口文档",
            "prompts": "AI 提示词套件",
        }
        doc_type_label = doc_type_label_map.get(doc_type, "文档")
        context_section = (
            f"**参考上下文**（其他已生成文档）：\n\n{context}\n\n"
            if context.strip()
            else ""
        )
        prompt = OPTIMIZE_DOCUMENT_PROMPT_TEMPLATE.format(
            doc_type_label=doc_type_label,
            instruction=instruction,
            current_content=current_content,
            context_section=context_section,
        )
        llm = get_llm(temperature=0.3)
        lc_messages = [HumanMessage(content=prompt)]

        async for chunk in llm.astream(lc_messages):
            if chunk.content:
                yield {"type": "chunk", "content": chunk.content}

        yield {"type": "done"}
