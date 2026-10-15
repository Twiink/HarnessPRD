"""文档生成服务 — PRD、接口文档、AI 提示词套件的生成与优化"""

import json
from typing import List, Dict, Any, AsyncGenerator, Callable

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage


from apps.llm.factory import get_tracked_llm
from apps.llm.metrics import LlmStep
from apps.core.resources.prompts import get_prompt
from apps.agents.prd_review_agent import PrdReviewAgent
from apps.agents.api_docs_review_agent import ApiDocsReviewAgent
from apps.agents.prompts_review_agent import PromptsReviewAgent
from apps.agents.prd_writer_agent import PrdWriterAgent
from apps.llm.messages import build_lc_messages, message_text
from apps.core.resources.skill_loader import (
    compose_prompt_sections,
    load_skill_bundle,
)
from apps.domain.requirements.normalization import normalize_feature_fields


from apps.services.generation.prompt_builders import (
    _build_skill_section,
    _artifact_for_optimize,
    _build_prd_prompt,
    _build_prd_from_summary_prompt,
    _format_conversation_context,
    _build_summary_sync_prompt,
    _truncate_text,
    _parse_summary,
    _build_json_repair_prompt,
    _build_summary_regeneration_prompt,
)


class DocumentService:
    def __init__(self, llm_factory: Callable[..., Any] | None = None):
        self._llm_factory = llm_factory
        self.prd_writer = PrdWriterAgent(llm_factory)
        self.prd_reviewer = PrdReviewAgent(llm_factory)
        self.api_docs_reviewer = ApiDocsReviewAgent(llm_factory)
        self.prompts_reviewer = PromptsReviewAgent(llm_factory)

    def _llm(self, step: str, **kwargs: Any) -> Any:
        return (self._llm_factory or get_tracked_llm)(step, **kwargs)

    async def generate_prd(self, conversation_messages: List[Dict[str, str]]) -> Dict[str, Any]:
        llm = self._llm(LlmStep.PRD_WRITER.value, temperature=0.3)
        lc_messages = build_lc_messages(conversation_messages)
        lc_messages.append(HumanMessage(content=_build_prd_prompt()))
        response = await llm.ainvoke(lc_messages)
        return {"prd": message_text(response.content), "status": "completed"}

    async def generate_prd_stream(
        self,
        conversation_messages: List[Dict[str, str]],
    ) -> AsyncGenerator[Dict, None]:
        initial_draft = ""
        yield {"type": "phase", "phase": "writer_started"}

        async for event in self.prd_writer.write_stream(conversation_messages):
            if event["type"] == "text_delta":
                initial_draft += event["content"]
            yield dict(event)

        yield {"type": "phase", "phase": "review_started"}
        review_result = await self.prd_reviewer.review(conversation_messages, initial_draft)
        yield {"type": "review", "phase": "review", "content": review_result}

        if review_result.get("passed", False):
            yield {
                "type": "done",
                "final_prd": initial_draft,
                "review": review_result,
                "revision_applied": False,
            }
            return

        yield {"type": "phase", "phase": "rewrite_started"}
        revised_draft = ""
        async for event in self.prd_writer.rewrite_stream(
            conversation_messages=conversation_messages,
            current_draft=initial_draft,
            review_result=review_result,
        ):
            if event["type"] == "text_delta":
                revised_draft += event["content"]
            yield dict(event)

        yield {
            "type": "done",
            "final_prd": revised_draft,
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
            json.dumps(
                normalize_feature_fields(requirements_summary), ensure_ascii=False, indent=2
            ),
        ]
        if conversation_messages:
            clarification_context = _format_conversation_context(conversation_messages)
            if clarification_context:
                review_context_parts.extend(["", "补充澄清对话：", clarification_context])

        yield {"type": "phase", "phase": "writer_started"}
        llm = self._llm(LlmStep.PRD_WRITER.value, temperature=0.2)
        lc_messages: list[BaseMessage] = [
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

        lc_messages.append(
            HumanMessage(content=_build_prd_from_summary_prompt(requirements_summary))
        )

        initial_draft = ""
        async for chunk in llm.astream(lc_messages):
            text = message_text(chunk.content)
            if text:
                initial_draft += text
                yield {"type": "text_delta", "phase": "writer", "content": text}

        yield {"type": "phase", "phase": "review_started"}
        review_result = await self.prd_reviewer.review(
            conversation_messages or [],
            initial_draft,
            review_context="\n".join(review_context_parts),
        )
        yield {"type": "review", "phase": "review", "content": review_result}

        if review_result.get("passed", False):
            yield {
                "type": "done",
                "final_prd": initial_draft,
                "review": review_result,
                "revision_applied": False,
            }
            return

        yield {"type": "phase", "phase": "rewrite_started"}
        rewrite_prompt = get_prompt("PRD_REWRITE_PROMPT_TEMPLATE").format(
            current_draft=initial_draft,
            review_result=review_result,
        )
        rewrite_messages: list[BaseMessage] = [
            SystemMessage(content=get_prompt("PRD_WRITER_SYSTEM_PROMPT")),
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
        rewrite_messages.append(
            HumanMessage(content=_build_prd_from_summary_prompt(requirements_summary))
        )
        rewrite_messages.append(HumanMessage(content=rewrite_prompt))

        rewrite_llm = self._llm(LlmStep.PRD_REWRITE.value, temperature=0.2)
        revised_draft = ""
        async for chunk in rewrite_llm.astream(rewrite_messages):
            text = message_text(chunk.content)
            if text:
                revised_draft += text
                yield {"type": "text_delta", "phase": "rewrite", "content": text}

        yield {
            "type": "done",
            "final_prd": revised_draft,
            "review": review_result,
            "revision_applied": True,
        }

    async def sync_summary_from_conversation(
        self,
        requirements_summary: Dict[str, Any],
        conversation_messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        llm = self._llm(LlmStep.SUMMARY_SYNC.value, temperature=0)
        lc_messages: list[BaseMessage] = [
            SystemMessage(
                content=(
                    "你是一位严谨的需求分析师。"
                    "你的任务是根据澄清对话更新结构化需求摘要，并只返回 JSON。"
                )
            ),
            HumanMessage(
                content=_build_summary_sync_prompt(requirements_summary, conversation_messages)
            ),
        ]
        response = await llm.ainvoke(lc_messages)
        content = message_text(response.content).strip()
        try:
            updated_summary = _parse_summary(content)
        except Exception:
            repair_messages = [
                SystemMessage(
                    content="你是一位严格的 JSON 修复助手。你的唯一任务是输出合法 JSON 对象。"
                ),
                HumanMessage(content=_build_json_repair_prompt(content)),
            ]
            repair_llm = self._llm(LlmStep.JSON_REPAIR.value, temperature=0)
            repair_response = await repair_llm.ainvoke(repair_messages)
            repaired_content = message_text(repair_response.content).strip()
            try:
                updated_summary = _parse_summary(repaired_content)
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
                regenerate_llm = self._llm(LlmStep.JSON_REGENERATE.value, temperature=0)
                regenerate_response = await regenerate_llm.ainvoke(regenerate_messages)
                regenerated_content = message_text(regenerate_response.content).strip()
                try:
                    updated_summary = _parse_summary(regenerated_content)
                except Exception as regenerate_error:
                    raise ValueError(
                        "结构化摘要回填失败：模型未返回可解析的 JSON。"
                        f"\n原始输出片段：\n{_truncate_text(content)}"
                        f"\n修复后输出片段：\n{_truncate_text(repaired_content)}"
                        f"\n重试后输出片段：\n{_truncate_text(regenerated_content)}"
                    ) from regenerate_error
        return {
            "requirements_summary": normalize_feature_fields(updated_summary),
            "status": "completed",
        }

    async def generate_api_docs_stream(
        self,
        prd_content: str,
        conversation_messages: List[Dict[str, str]],
    ) -> AsyncGenerator[Dict, None]:
        llm = self._llm(LlmStep.API_DOCS_GENERATE.value, temperature=0.3)
        lc_messages = build_lc_messages(conversation_messages)
        sections = compose_prompt_sections(load_skill_bundle("api-docs"))
        skill_section = _build_skill_section(sections, title="团队接口规范与参考示例")
        conversation_text = _format_conversation_context(conversation_messages)
        conversation_section = (
            f"\n\n澄清对话摘要：\n\n{conversation_text}\n\n" if conversation_text else ""
        )
        lc_messages.append(
            HumanMessage(
                content=(
                    f"以下是已确认的产品需求文档（PRD）：\n\n{prd_content}"
                    f"{conversation_section}"
                    f"{skill_section}"
                    f"{get_prompt('API_DOCS_GENERATION_PROMPT')}"
                    "\n\n额外要求："
                    "\n1. 遵循 skill 中的团队接口规范。"
                    "\n2. 参考示例的路径、参数表、错误码写法。"
                    "\n3. 规范内化为设计结果，不堆砌原文。"
                )
            )
        )

        draft = ""
        async for chunk in llm.astream(lc_messages):
            text = message_text(chunk.content)
            if text:
                draft += text
                yield {"type": "chunk", "content": text}

        yield {"type": "phase", "phase": "review_started"}
        review_result = await self.api_docs_reviewer.review(prd_content, draft)
        yield {"type": "review", "content": review_result}
        yield {"type": "done", "content": draft, "review": review_result}

    async def generate_prompts_stream(
        self,
        prd_content: str,
        api_docs_content: str,
    ) -> AsyncGenerator[Dict, None]:
        llm = self._llm(LlmStep.PROMPTS_GENERATE.value, temperature=0.5)
        sections = compose_prompt_sections(load_skill_bundle("prompts"))
        skill_section = _build_skill_section(sections, title="提示词套件生成规范")
        context = f"产品需求文档（PRD）：\n\n{prd_content}"
        if api_docs_content.strip():
            context += f"\n\n接口文档：\n\n{api_docs_content}"
        lc_messages: list[BaseMessage] = [
            SystemMessage(
                content="你是一位 AI 辅助开发专家，专门为 Claude Code 等 AI 编程工具设计高质量的系统提示词。"
            ),
            HumanMessage(content=f"{context}\n\n{skill_section}"),
        ]

        draft = ""
        async for chunk in llm.astream(lc_messages):
            text = message_text(chunk.content)
            if text:
                draft += text
                yield {"type": "chunk", "content": text}

        yield {"type": "phase", "phase": "review_started"}
        review_result = await self.prompts_reviewer.review(prd_content, draft)
        yield {"type": "review", "content": review_result}
        yield {"type": "done", "content": draft, "review": review_result}

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
            f"**参考上下文**（其他已生成文档）：\n\n{context}\n\n" if context.strip() else ""
        )
        skill_section = ""
        artifact = _artifact_for_optimize(doc_type)
        if artifact:
            sections = compose_prompt_sections(load_skill_bundle(artifact))
            skill_section = _build_skill_section(sections, title="优化时需遵循的团队规范")
        prompt = get_prompt("OPTIMIZE_DOCUMENT_PROMPT_TEMPLATE").format(
            doc_type_label=doc_type_label,
            instruction=instruction,
            current_content=current_content,
            context_section=context_section,
        )
        if skill_section:
            prompt = f"{prompt}\n\n{skill_section}"
        llm = self._llm(LlmStep.DOCUMENT_OPTIMIZE.value, temperature=0.3)
        lc_messages: list[BaseMessage] = [HumanMessage(content=prompt)]

        async for chunk in llm.astream(lc_messages):
            text = message_text(chunk.content)
            if text:
                yield {"type": "chunk", "content": text}

        yield {"type": "done"}
