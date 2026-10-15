"""文档编排实际消费的 Agent 输出与流事件契约。"""

from typing import Literal, TypedDict

from apps.domain.reviews import ReviewIssue, ReviewResult


class TextDeltaEvent(TypedDict):
    type: Literal["text_delta"]
    phase: Literal["writer", "rewrite"]
    content: str
