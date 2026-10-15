"""Extract one JSON object from plain, fenced, or prose-wrapped model output."""

import json
import re
from typing import Any


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
    raise ValueError("模型未返回合法 JSON 对象")
