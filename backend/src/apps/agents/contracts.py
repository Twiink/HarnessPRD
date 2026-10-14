"""文档编排实际消费的 Agent 输出与流事件契约。"""

from typing import Literal, TypedDict


class ReviewIssue(TypedDict):
    severity: str
    section: str
    problem: str
    suggestion: str


class ReviewResult(TypedDict):
    passed: bool
    summary: str
    issues: list[ReviewIssue]


class TextDeltaEvent(TypedDict):
    type: Literal["text_delta"]
    phase: Literal["writer", "rewrite"]
    content: str
