"""提示词文档 Review Agent（仅 Review，不 Rewrite）。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from services.llm_factory import get_tracked_llm
from services.llm_metrics import LlmStep
from services.prompts import get_prompts_review_prompt
from services.review_result_utils import build_parse_failed_review, normalize_document_review


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates = [block.strip() for block in fenced_blocks if block.strip()] or [text]
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
                parsed, _ = decoder.raw_decode(candidate_text[match.start() :])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

    raise ValueError("review agent 未返回 JSON 对象")


def _build_review_repair_prompt(raw_text: str) -> str:
    return "\n".join(
        [
            "请把下面这段审查结果修复为一个合法 JSON 对象。",
            "要求：",
            "1. 只输出 JSON 对象本身。",
            "2. 不要输出解释，不要输出 Markdown 代码块。",
            "3. 必须包含 passed、summary、issues 字段。",
            "4. issues 中每项需包含 severity、section、problem、suggestion。",
            "",
            "待修复内容：",
            raw_text,
        ]
    )


def _normalize_review(parsed: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_document_review(parsed, default_section="提示词")


class PromptsReviewAgent:
    async def review(self, prd_content: str, prompts_content: str) -> Dict[str, Any]:
        llm = get_tracked_llm(LlmStep.PROMPTS_REVIEW.value, temperature=0)
        messages = [
            SystemMessage(content="你是一位提示词工程审查专家，只输出 JSON 审查结果。"),
            HumanMessage(content=get_prompts_review_prompt(prd_content, prompts_content)),
        ]
        response = await llm.ainvoke(messages)
        raw_content = str(response.content).strip()
        try:
            parsed = _extract_json_object(raw_content)
            return _normalize_review(parsed)
        except Exception:
            repair_llm = get_tracked_llm(LlmStep.JSON_REPAIR.value, temperature=0)
            repair_response = await repair_llm.ainvoke(
                [
                    SystemMessage(content="你是一位严格的 JSON 修复助手。你的唯一任务是输出合法 JSON 对象。"),
                    HumanMessage(content=_build_review_repair_prompt(raw_content)),
                ]
            )
            try:
                parsed = _extract_json_object(str(repair_response.content).strip())
                return _normalize_review(parsed)
            except Exception:
                return build_parse_failed_review("提示词")
