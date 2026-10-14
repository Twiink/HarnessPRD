"""对话服务 — 负责需求收集对话的启动与延续"""

from typing import List, Dict, Any, Optional, AsyncGenerator

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage

from apps.llm.messages import build_lc_messages
from apps.llm.factory import get_tracked_llm
from apps.llm.metrics import LlmStep
from apps.llm.token_budget import get_last_budget_check
from apps.services.prompts import get_prompt
from apps.services.clarification_response import parse_clarification_response


def format_form_data(form_data: Dict[str, Any]) -> str:
    label_map = {
        "product_name": "产品名称",
        "problem_solved": "解决的问题",
        "target_users": "目标用户",
        "features": "产品功能 核心功能",
        "page_count": "页面数量",
        "design_style": "页面风格",
        "platform_type": "平台类型",
        "auth_required": "登录需求",
        "database_required": "数据存储",
        "tech_stack": "技术栈偏好",
        "third_party_apis": "第三方服务",
        "security_requirements": "安全要求",
        "performance_requirements": "性能要求",
        "deployment": "部署方式",
    }
    lines = []
    for key, value in form_data.items():
        if value and str(value).strip():
            label = label_map.get(key, key)
            lines.append(f"- **{label}**：{value}")
    return "\n".join(lines) if lines else "（用户未填写任何信息）"


def _serialize_messages(
    lc_messages,
    last_clarification_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for msg in lc_messages:
        role = msg.type
        if role == "human":
            role = "human"
        elif role == "ai":
            role = "ai"
        serialized.append({"role": role, "content": msg.content})

    if last_clarification_meta and serialized:
        last = serialized[-1]
        if last.get("role") in ("assistant", "ai"):
            last["clarification_meta"] = last_clarification_meta

    return serialized


def _finalize_ai_response(full_content: str) -> tuple[str, Optional[Dict[str, Any]]]:
    return parse_clarification_response(full_content)


class ConversationService:
    def _build_initial_messages(
        self,
        user_initial_input: str,
        form_data: Optional[Dict[str, Any]],
        system_prompt_override: Optional[str] = None,
    ):
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt_override or get_prompt("SYSTEM_PROMPT"))
        ]

        if form_data and any(v for v in form_data.values() if v):
            form_summary = format_form_data(form_data)
            initial_content = f"用户已填写了初始产品信息：\n\n{form_summary}"
            if user_initial_input:
                initial_content += f"\n\n补充说明：{user_initial_input}"
            initial_content += "\n\n请分析这些信息并开始对话：\n1. 简要确认你理解了用户的产品想法\n2. 指出最需要深入讨论的 1-2 个关键点\n3. 提出具体建议或问题推动讨论\n\n保持友好自然的交流风格，像产品伙伴一样。"
        elif user_initial_input:
            initial_content = f"用户的初步想法：{user_initial_input}\n\n请分析这个想法并开始需求讨论，帮助用户逐步完善产品定义。"
        else:
            initial_content = "用户想开始产品需求对话，但还没有提供具体信息。\n\n请友好地介绍一下你能帮助做什么，并请用户描述他们想开发的产品。"

        messages.append(HumanMessage(content=initial_content))
        return messages

    async def start_conversation_stream(
        self,
        user_initial_input: str = "",
        form_data: Optional[Dict[str, Any]] = None,
        system_prompt_override: Optional[str] = None,
    ) -> AsyncGenerator[Dict, None]:
        llm = get_tracked_llm(LlmStep.CHAT_START.value)
        lc_messages = self._build_initial_messages(
            user_initial_input,
            form_data,
            system_prompt_override,
        )

        full_content = ""
        async for chunk in llm.astream(lc_messages):
            if chunk.content:
                full_content += chunk.content
                yield {"type": "chunk", "content": chunk.content}

        display_content, clarification_meta = _finalize_ai_response(full_content)
        lc_messages.append(AIMessage(content=display_content))
        conv_id = "conv_" + str(abs(hash(full_content)))[:8]
        done_event: Dict[str, Any] = {
            "type": "done",
            "conversation_id": conv_id,
            "messages": _serialize_messages(lc_messages, clarification_meta),
        }
        budget_check = get_last_budget_check()
        if budget_check is not None:
            done_event["context_usage"] = budget_check.to_context_usage()
        yield done_event

    async def continue_conversation_stream(
        self,
        conversation_id: str,
        messages: List[Dict[str, Any]],
        user_input: str,
    ) -> AsyncGenerator[Dict, Any]:
        llm = get_tracked_llm(LlmStep.CHAT_CONTINUE.value)
        lc_messages = build_lc_messages(messages)
        last_message = lc_messages[-1] if lc_messages else None
        if not (isinstance(last_message, HumanMessage) and last_message.content == user_input):
            lc_messages.append(HumanMessage(content=user_input))

        full_content = ""
        async for chunk in llm.astream(lc_messages):
            if chunk.content:
                full_content += chunk.content
                yield {"type": "chunk", "content": chunk.content}

        display_content, clarification_meta = _finalize_ai_response(full_content)
        lc_messages.append(AIMessage(content=display_content))
        done_event: Dict[str, Any] = {
            "type": "done",
            "conversation_id": conversation_id,
            "messages": _serialize_messages(lc_messages, clarification_meta),
        }
        budget_check = get_last_budget_check()
        if budget_check is not None:
            done_event["context_usage"] = budget_check.to_context_usage()
        yield done_event
