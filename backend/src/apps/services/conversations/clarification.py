"""澄清对话结构化响应解析 — 从 LLM 回复中剥离 clarification_state JSON 块"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

CLARIFICATION_STATE_FENCE = "clarification_state"

_FENCE_BLOCK_PATTERN = re.compile(
    rf"```(?:{CLARIFICATION_STATE_FENCE})\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)

_FENCE_START_PATTERN = re.compile(
    rf"\n?```(?:{CLARIFICATION_STATE_FENCE})?\s*$",
    re.IGNORECASE,
)


def normalize_clarification_meta(data: Dict[str, Any]) -> Dict[str, Any]:
    raw_questions = data.get("open_questions", [])
    open_questions: List[str] = []
    if isinstance(raw_questions, list):
        open_questions = [str(item).strip() for item in raw_questions if str(item).strip()][:5]

    ready_to_generate = bool(data.get("ready_to_generate", False))
    if open_questions:
        ready_to_generate = False

    return {
        "open_questions": open_questions,
        "ready_to_generate": ready_to_generate,
    }


def _parse_meta_json(json_text: str) -> Optional[Dict[str, Any]]:
    text = json_text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return normalize_clarification_meta(parsed)


def parse_clarification_response(raw_text: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """从完整 AI 回复中分离展示文本与 clarification_meta。"""
    match = _FENCE_BLOCK_PATTERN.search(raw_text)
    if not match:
        return raw_text, None

    display_content = raw_text[: match.start()].rstrip()
    meta = _parse_meta_json(match.group(1))
    return display_content, meta


def strip_clarification_state_block(text: str) -> str:
    """流式展示用：移除已出现或部分出现的 clarification_state 代码块。"""
    if not text:
        return text

    complete = _FENCE_BLOCK_PATTERN.search(text)
    if complete:
        return text[: complete.start()].rstrip()

    marker = f"```{CLARIFICATION_STATE_FENCE}"
    marker_idx = text.find(marker)
    if marker_idx >= 0:
        return text[:marker_idx].rstrip()

    for length in range(len(marker) - 1, 2, -1):
        partial = marker[:length]
        if text.endswith(partial):
            return text[: -len(partial)].rstrip()

    partial_fence = _FENCE_START_PATTERN.search(text)
    if partial_fence and partial_fence.start() is not None:
        return text[: partial_fence.start()].rstrip()

    return text
