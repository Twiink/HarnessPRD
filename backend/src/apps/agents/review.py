"""三个审查 Agent 共用的纯 JSON 提取逻辑。"""

import json
import re
from typing import Any

from apps.services.prompts import get_prompt


def extract_json_object(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates = [block.strip() for block in fenced_blocks if block.strip()] or [text]
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        for match in re.finditer(r"\{", candidate):
            try:
                parsed, _ = decoder.raw_decode(candidate[match.start() :])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    raise ValueError("review agent 未返回 JSON 对象")


def build_review_repair_prompt(raw_text: str) -> str:
    return get_prompt("REVIEW_REPAIR_PROMPT_TEMPLATE").format(raw_text=raw_text)
