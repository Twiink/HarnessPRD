"""将业务对话历史转换为模型消息的公共入口。"""

from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

ConversationInput = Sequence[Mapping[str, Any]]


def message_text(content: Any) -> str:
    """兼容模型返回的字符串和结构化文本内容块。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item if isinstance(item, str) else item["text"]
            for item in content
            if isinstance(item, str)
            or (
                isinstance(item, dict)
                and item.get("type") in (None, "text", "text_delta", "output_text")
                and isinstance(item.get("text"), str)
            )
        )
    return ""


def build_lc_messages(messages: ConversationInput) -> list[BaseMessage]:
    """读取 role/content，兼容 human/ai 别名，并忽略未知角色。"""
    result: list[BaseMessage] = []
    for message in messages:
        role = message["role"]
        content = message["content"]
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role in ("user", "human"):
            result.append(HumanMessage(content=content))
        elif role in ("assistant", "ai"):
            result.append(AIMessage(content=content))
    return result
