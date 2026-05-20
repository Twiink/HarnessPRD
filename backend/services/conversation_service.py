"""对话服务 — 负责需求收集对话的启动与延续"""

from typing import List, Dict, Any, Optional, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from services.llm_factory import get_llm
from services.prompts import SYSTEM_PROMPT


def format_form_data(form_data: Dict[str, Any]) -> str:
    label_map = {
        "product_name": "产品名称",
        "problem_solved": "解决的问题",
        "target_users": "目标用户",
        "mvp_features": "MVP 核心功能",
        "v2_features": "v2 功能规划",
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


def _build_lc_messages(messages: List[Dict[str, str]]):
    """将前端消息列表转换为 LangChain 消息对象"""
    result = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role in ("user", "human"):
            result.append(HumanMessage(content=content))
        elif role in ("assistant", "ai"):
            result.append(AIMessage(content=content))
    return result


def _serialize_messages(lc_messages) -> List[Dict[str, str]]:
    return [{"role": msg.type, "content": msg.content} for msg in lc_messages]


class ConversationService:
    def __init__(self):
        self.system_prompt = SYSTEM_PROMPT

    def _build_initial_messages(
        self,
        user_initial_input: str,
        form_data: Optional[Dict[str, Any]],
        system_prompt_override: Optional[str] = None,
    ):
        messages = [SystemMessage(content=system_prompt_override or self.system_prompt)]

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
        llm = get_llm()
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

        lc_messages.append(AIMessage(content=full_content))
        conv_id = "conv_" + str(abs(hash(full_content)))[:8]
        yield {
            "type": "done",
            "conversation_id": conv_id,
            "messages": _serialize_messages(lc_messages),
        }

    async def continue_conversation_stream(
        self,
        conversation_id: str,
        messages: List[Dict[str, str]],
        user_input: str,
    ) -> AsyncGenerator[Dict, None]:
        llm = get_llm()
        lc_messages = _build_lc_messages(messages)
        last_message = lc_messages[-1] if lc_messages else None
        if not (
            isinstance(last_message, HumanMessage)
            and last_message.content == user_input
        ):
            lc_messages.append(HumanMessage(content=user_input))

        full_content = ""
        async for chunk in llm.astream(lc_messages):
            if chunk.content:
                full_content += chunk.content
                yield {"type": "chunk", "content": chunk.content}

        lc_messages.append(AIMessage(content=full_content))
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "messages": _serialize_messages(lc_messages),
        }
