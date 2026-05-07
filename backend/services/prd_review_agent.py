"""PRD Review Agent - 负责审查 PRD 草稿并返回结构化意见"""

import json
import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from services.conversation_service import _build_lc_messages
from services.llm_factory import get_llm
from services.prompts import PRD_REVIEW_PROMPT_TEMPLATE, PRD_REVIEWER_SYSTEM_PROMPT


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
                parsed, _ = decoder.raw_decode(candidate_text[match.start():])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

    raise ValueError("review agent 未返回 JSON 对象")


def _build_review_repair_prompt(raw_text: str) -> str:
    return "\n".join([
        "请把下面这段审查结果修复为一个合法 JSON 对象。",
        "要求：",
        "1. 只输出 JSON 对象本身。",
        "2. 不要输出解释，不要输出 Markdown 代码块。",
        "3. 必须包含 passed、summary、issues 字段。",
        "4. issues 中每项需包含 severity、section、problem、suggestion。",
        "",
        "待修复内容：",
        raw_text,
    ])


def _build_review_regeneration_prompt(review_context: str, prd_draft: str) -> str:
    return "\n".join([
        "请重新审查以下 PRD 草稿，并只输出一个合法 JSON 对象。",
        "这是一次失败后的重试，请务必严格遵守格式。",
        "JSON 结构必须如下：",
        "{",
        '  "passed": true,',
        '  "summary": "一句话总结审查结论",',
        '  "issues": [',
        "    {",
        '      "severity": "high",',
        '      "section": "MVP 功能",',
        '      "problem": "问题描述",',
        '      "suggestion": "修改建议"',
        "    }",
        "  ]",
        "}",
        "如果没有明显问题，issues 返回空数组。",
        "",
        "补充上下文：",
        review_context.strip() or "（无额外上下文）",
        "",
        "待审查的 PRD 草稿：",
        prd_draft,
    ])


class PrdReviewAgent:
    """独立的 PRD reviewer agent，专注于找问题，不负责改稿。"""

    async def review(
        self,
        conversation_messages: List[Dict[str, str]],
        prd_draft: str,
        review_context: str = "",
    ) -> Dict[str, Any]:
        llm = get_llm(temperature=0)
        lc_messages = [SystemMessage(content=PRD_REVIEWER_SYSTEM_PROMPT)]
        lc_messages.extend(_build_lc_messages(conversation_messages))
        lc_messages.append(
            HumanMessage(
                content=PRD_REVIEW_PROMPT_TEMPLATE.format(
                    review_context=review_context.strip() or "（无额外上下文）",
                    prd_draft=prd_draft,
                )
            )
        )

        response = await llm.ainvoke(lc_messages)
        raw_content = str(response.content).strip()
        try:
            review_result = _extract_json_object(raw_content)
        except Exception:
            repair_messages = [
                SystemMessage(
                    content="你是一位严格的 JSON 修复助手。你的唯一任务是输出合法 JSON 对象。"
                ),
                HumanMessage(content=_build_review_repair_prompt(raw_content)),
            ]
            repair_response = await llm.ainvoke(repair_messages)
            repaired_content = str(repair_response.content).strip()
            try:
                review_result = _extract_json_object(repaired_content)
            except Exception:
                regenerate_messages = [
                    SystemMessage(content=PRD_REVIEWER_SYSTEM_PROMPT),
                    HumanMessage(
                        content=_build_review_regeneration_prompt(
                            review_context=review_context,
                            prd_draft=prd_draft,
                        )
                    ),
                ]
                regenerate_response = await llm.ainvoke(regenerate_messages)
                regenerated_content = str(regenerate_response.content).strip()
                review_result = _extract_json_object(regenerated_content)
        review_result.setdefault("passed", False)
        review_result.setdefault("summary", "")
        review_result.setdefault("issues", [])
        return review_result
