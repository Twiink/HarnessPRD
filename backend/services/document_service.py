"""文档生成服务 — PRD、接口文档、AI 提示词套件的生成与优化"""

import os
import json
import re
from typing import List, Dict, Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from services.llm_factory import get_llm
from services.prompts import (
    PRD_GENERATION_PROMPT,
    API_DOCS_GENERATION_PROMPT,
    PROMPTS_GENERATION_PROMPT,
    OPTIMIZE_DOCUMENT_PROMPT_TEMPLATE,
    PRD_REWRITE_PROMPT_TEMPLATE,
    PRD_WRITER_SYSTEM_PROMPT,
)
from services.prd_review_agent import PrdReviewAgent
from services.prd_writer_agent import PrdWriterAgent
from services.conversation_service import _build_lc_messages
from services.rag_service import retrieve_api_docs_context, retrieve_api_docs_hits


def _load_prd_template() -> str:
    """读取本地 PRD 格式模板文件，文件不存在或为空则返回空字符串"""
    template_path = os.path.join(os.path.dirname(__file__), "..", "core", "prd_template.md")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content
    except Exception:
        return ""


def _load_skill_artifact(*path_parts: str) -> str:
    """读取平台无关 PRD skill 的参考文件，缺失时返回空字符串"""
    artifact_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "skills",
        "prd-generator",
        *path_parts,
    )
    try:
        with open(artifact_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _build_prd_prompt() -> str:
    """构建 PRD 生成 prompt，如有模板则附上格式参考"""
    template = _load_prd_template()
    if template:
        return PRD_GENERATION_PROMPT + f"\n\n请参考以下格式模板（仅作格式参考，内容以对话为准）：\n\n{template}"
    return PRD_GENERATION_PROMPT


def _build_prd_from_summary_prompt(requirements_summary: Dict[str, Any]) -> str:
    """基于结构化需求摘要构建 PRD 生成 prompt"""
    template = _load_skill_artifact("references", "prd-template.md") or _load_prd_template()
    writing_rules = _load_skill_artifact("references", "writing-rules.md")
    instructions = _load_skill_artifact("instructions.md")
    summary_json = json.dumps(requirements_summary, ensure_ascii=False, indent=2)

    prompt_parts = [
        "请基于以下结构化需求摘要生成一份专业、简洁、工程可执行的 PRD。",
        "要求：",
        "1. 使用中文输出 Markdown。",
        "2. 严格遵循给定模板的章节结构。",
        "3. 不编造未提供的业务事实，缺失且重要的信息写“待确认”。",
        "4. MVP 功能必须整理为表格，列为：功能名称、功能描述、用户价值。",
        "5. 技术规格中，已确认项直接写明；推测性实现建议使用“可采用/建议”表述。",
        "6. 删除重复信息，只保留对产品、设计、研发交接有用的内容。",
        "",
        "结构化需求摘要：",
        summary_json,
    ]

    if writing_rules:
        prompt_parts.extend(["", "补充写作规则：", writing_rules])
    if instructions:
        prompt_parts.extend(["", "补充生成说明：", instructions])
    if template:
        prompt_parts.extend(["", "输出模板：", template])

    return "\n".join(prompt_parts)


def _format_conversation_context(conversation_messages: List[Dict[str, str]]) -> str:
    """将澄清对话整理为可读上下文，供 PRD 生成参考"""
    lines: List[str] = []
    for msg in conversation_messages:
        role = msg.get("role", "")
        if role == "system":
            continue
        if role in ("assistant", "ai"):
            speaker = "AI"
        else:
            speaker = "用户"
        content = str(msg.get("content", "")).strip()
        if content:
            lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def _build_summary_sync_prompt(
    requirements_summary: Dict[str, Any],
    conversation_messages: List[Dict[str, str]],
) -> str:
    """构建结构化摘要回填 prompt，要求输出 JSON"""
    summary_json = json.dumps(requirements_summary, ensure_ascii=False, indent=2)
    conversation_text = _format_conversation_context(conversation_messages)
    schema_text = _load_skill_artifact("references", "field-schema.json")

    prompt_parts = [
        "请根据以下结构化需求摘要和后续澄清对话，输出一份更新后的结构化需求摘要 JSON。",
        "要求：",
        "1. 只输出合法 JSON，不要输出 Markdown 代码块，不要输出解释。",
        "2. 保持原有字段结构，尽量不要新增字段。",
        "3. 仅在对话中出现了明确补充、修正或澄清时才更新字段。",
        "4. 不要编造信息；不确定的内容保留原值。",
        "5. 如果对话中补充了更明确的内容，应覆盖原先的“待确认”或较模糊值。",
        "6. mvp_features、ui_pages、interaction_notes、in_scope、out_of_scope 等字段保持结构化。",
        "",
        "当前结构化需求摘要：",
        summary_json,
        "",
        "澄清对话：",
        conversation_text or "（无）",
    ]

    if schema_text:
        prompt_parts.extend(["", "参考 schema：", schema_text])

    return "\n".join(prompt_parts)


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    """尽量从模型输出中提取 JSON 对象"""
    text = raw_text.strip()
    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced_blocks:
        candidates = [block.strip() for block in fenced_blocks if block.strip()]
    else:
        candidates = [text]

    decoder = json.JSONDecoder()

    for candidate_text in candidates:
        try:
            parsed = json.loads(candidate_text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        for match in re.finditer(r"\{", candidate_text):
            try:
                parsed, end_index = decoder.raw_decode(candidate_text[match.start():])
                if isinstance(parsed, dict):
                    tail = candidate_text[match.start() + end_index:].strip()
                    if not tail or tail.startswith(("```", "#", "//")):
                        return parsed
                    return parsed
            except json.JSONDecodeError:
                continue

    raise ValueError("模型未返回合法 JSON 对象")


def _truncate_text(text: str, max_len: int = 800) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n...<truncated>..."


def _build_json_repair_prompt(raw_text: str) -> str:
    return "\n".join([
        "请把下面这段内容修复为一个合法的 JSON 对象。",
        "要求：",
        "1. 只输出 JSON 对象本身。",
        "2. 不要输出解释，不要输出 Markdown 代码块。",
        "3. 保持原字段结构和语义，不要新增无关字段。",
        "",
        "待修复内容：",
        raw_text,
    ])


def _build_summary_regeneration_prompt(
    requirements_summary: Dict[str, Any],
    conversation_messages: List[Dict[str, str]],
) -> str:
    summary_json = json.dumps(requirements_summary, ensure_ascii=False, indent=2)
    conversation_text = _format_conversation_context(conversation_messages)
    return "\n".join([
        "请重新输出一份更新后的结构化需求摘要 JSON。",
        "这是一次失败后的重试，请务必严格遵守格式。",
        "要求：",
        "1. 只输出一个合法 JSON 对象。",
        "2. 不要输出 Markdown，不要输出解释，不要输出代码块。",
        "3. 保持原字段结构；不要新增无关字段。",
        "4. 仅根据澄清对话中的明确内容更新字段。",
        "5. 无法确定的值保留原值。",
        "",
        "当前结构化需求摘要：",
        summary_json,
        "",
        "澄清对话：",
        conversation_text or "（无）",
    ])


class DocumentService:
    def __init__(self):
        self.prd_writer = PrdWriterAgent()
        self.prd_reviewer = PrdReviewAgent()

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
        draft_v1 = ""
        yield {"type": "phase", "phase": "writer_started"}

        async for event in self.prd_writer.write_stream(conversation_messages):
            if event["type"] == "text_delta":
                draft_v1 += event["content"]
            yield event

        yield {"type": "phase", "phase": "review_started"}
        review_result = await self.prd_reviewer.review(conversation_messages, draft_v1)
        yield {"type": "review", "phase": "review", "content": review_result}

        if review_result.get("passed", False):
            yield {
                "type": "done",
                "final_prd": draft_v1,
                "review": review_result,
                "revision_applied": False,
            }
            return

        yield {"type": "phase", "phase": "rewrite_started"}
        draft_v2 = ""
        async for event in self.prd_writer.rewrite_stream(
            conversation_messages=conversation_messages,
            current_draft=draft_v1,
            review_result=review_result,
        ):
            if event["type"] == "text_delta":
                draft_v2 += event["content"]
            yield event

        yield {
            "type": "done",
            "final_prd": draft_v2,
            "review": review_result,
            "revision_applied": True,
        }

    async def generate_prd_from_summary_stream(
        self,
        requirements_summary: Dict[str, Any],
        conversation_messages: List[Dict[str, str]] | None = None,
    ) -> AsyncGenerator[Dict, None]:
        clarification_context = ""
        review_context_parts = [
            "结构化需求摘要：",
            json.dumps(requirements_summary, ensure_ascii=False, indent=2),
        ]
        if conversation_messages:
            clarification_context = _format_conversation_context(conversation_messages)
            if clarification_context:
                review_context_parts.extend(["", "补充澄清对话：", clarification_context])

        yield {"type": "phase", "phase": "writer_started"}
        llm = get_llm(temperature=0.2)
        lc_messages = [
            SystemMessage(
                content=(
                    "你是一位资深产品经理和技术写作者。"
                    "请把结构化需求摘要整理成简洁、结构化、工程可执行的 PRD。"
                    "如果存在补充对话，请优先采用对话中已澄清的内容。"
                )
            )
        ]

        if clarification_context:
            lc_messages.append(
                HumanMessage(
                    content=(
                        "以下是围绕该需求的澄清对话，请将其中明确的信息视为对结构化需求摘要的补充或修正：\n\n"
                        f"{clarification_context}"
                    )
                )
            )

        lc_messages.append(HumanMessage(content=_build_prd_from_summary_prompt(requirements_summary)))

        draft_v1 = ""
        async for chunk in llm.astream(lc_messages):
            if chunk.content:
                draft_v1 += chunk.content
                yield {"type": "text_delta", "phase": "writer", "content": chunk.content}

        yield {"type": "phase", "phase": "review_started"}
        review_result = await self.prd_reviewer.review(
            conversation_messages or [],
            draft_v1,
            review_context="\n".join(review_context_parts),
        )
        yield {"type": "review", "phase": "review", "content": review_result}

        if review_result.get("passed", False):
            yield {
                "type": "done",
                "final_prd": draft_v1,
                "review": review_result,
                "revision_applied": False,
            }
            return

        yield {"type": "phase", "phase": "rewrite_started"}
        rewrite_prompt = PRD_REWRITE_PROMPT_TEMPLATE.format(
            current_draft=draft_v1,
            review_result=review_result,
        )
        rewrite_messages = [
            SystemMessage(content=PRD_WRITER_SYSTEM_PROMPT),
        ]
        if clarification_context:
            rewrite_messages.append(
                HumanMessage(
                    content=(
                        "以下是围绕该需求的澄清对话，请将其中明确的信息视为对结构化需求摘要的补充或修正：\n\n"
                        f"{clarification_context}"
                    )
                )
            )
        rewrite_messages.append(HumanMessage(content=_build_prd_from_summary_prompt(requirements_summary)))
        rewrite_messages.append(HumanMessage(content=rewrite_prompt))

        draft_v2 = ""
        async for chunk in llm.astream(rewrite_messages):
            if chunk.content:
                draft_v2 += chunk.content
                yield {"type": "text_delta", "phase": "rewrite", "content": chunk.content}

        yield {
            "type": "done",
            "final_prd": draft_v2,
            "review": review_result,
            "revision_applied": True,
        }

    async def sync_summary_from_conversation(
        self,
        requirements_summary: Dict[str, Any],
        conversation_messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        llm = get_llm(temperature=0)
        lc_messages = [
            SystemMessage(
                content=(
                    "你是一位严谨的需求分析师。"
                    "你的任务是根据澄清对话更新结构化需求摘要，并只返回 JSON。"
                )
            ),
            HumanMessage(content=_build_summary_sync_prompt(requirements_summary, conversation_messages)),
        ]
        response = await llm.ainvoke(lc_messages)
        content = str(response.content).strip()
        try:
            updated_summary = _extract_json_object(content)
        except Exception:
            repair_messages = [
                SystemMessage(
                    content="你是一位严格的 JSON 修复助手。你的唯一任务是输出合法 JSON 对象。"
                ),
                HumanMessage(content=_build_json_repair_prompt(content)),
            ]
            repair_response = await llm.ainvoke(repair_messages)
            repaired_content = str(repair_response.content).strip()
            try:
                updated_summary = _extract_json_object(repaired_content)
            except Exception:
                regenerate_messages = [
                    SystemMessage(
                        content=(
                            "你是一位严谨的需求分析师。"
                            "你的任务是根据澄清对话更新结构化需求摘要，并且只返回合法 JSON 对象。"
                        )
                    ),
                    HumanMessage(
                        content=_build_summary_regeneration_prompt(
                            requirements_summary,
                            conversation_messages,
                        )
                    ),
                ]
                regenerate_response = await llm.ainvoke(regenerate_messages)
                regenerated_content = str(regenerate_response.content).strip()
                try:
                    updated_summary = _extract_json_object(regenerated_content)
                except Exception as regenerate_error:
                    raise ValueError(
                        "结构化摘要回填失败：模型未返回可解析的 JSON。"
                        f"\n原始输出片段：\n{_truncate_text(content)}"
                        f"\n修复后输出片段：\n{_truncate_text(repaired_content)}"
                        f"\n重试后输出片段：\n{_truncate_text(regenerated_content)}"
                    ) from regenerate_error
        return {"requirements_summary": updated_summary, "status": "completed"}

    async def retrieve_api_docs_rag_hits(
        self,
        prd_content: str,
        conversation_messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        query = f"{prd_content}\n\n{_format_conversation_context(conversation_messages)}"
        hits = retrieve_api_docs_hits(query)
        return {
            "status": "completed",
            "hits": [
                {
                    "source": hit.source,
                    "title": hit.title,
                    "score": hit.score,
                    "content": hit.content,
                    "content_preview": hit.content_preview,
                }
                for hit in hits
            ],
        }

    async def generate_api_docs_stream(
        self,
        prd_content: str,
        conversation_messages: List[Dict[str, str]],
    ) -> AsyncGenerator[Dict, None]:
        llm = get_llm(temperature=0.3)
        lc_messages = _build_lc_messages(conversation_messages)
        rag_context = retrieve_api_docs_context(
            f"{prd_content}\n\n{_format_conversation_context(conversation_messages)}"
        )
        rag_section = (
            f"\n\n接口文档生成前检索到的 RAG 参考资料：\n\n{rag_context}\n\n"
            if rag_context
            else "\n\n未检索到可用的 RAG 参考资料，请仅基于 PRD 和通用接口设计经验生成。\n\n"
        )
        lc_messages.append(HumanMessage(
            content=(
                f"以下是已确认的产品需求文档（PRD）：\n\n{prd_content}"
                f"{rag_section}"
                f"{API_DOCS_GENERATION_PROMPT}"
                "\n\n额外要求："
                "\n1. 优先遵循 RAG 中的团队接口规范。"
                "\n2. 参考历史接口文档示例的路径命名、参数表、响应结构和错误码写法。"
                "\n3. 如果引用了 RAG 中的规范，请把它内化为接口设计结果，不要在正文中机械堆砌原文。"
            )
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
