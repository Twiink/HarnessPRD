"""文档生成与摘要同步的 Prompt 构建，独立于模型客户端。"""

import json
from typing import Any, Dict, List
from apps.core.config import get_settings
from apps.core.resources.prompts import get_prompt
from apps.core.resources.skill_loader import (
    compose_prompt_sections,
    load_skill_bundle,
)
from apps.domain.inputs import RequirementsInput, input_dict
from apps.domain.requirements.normalization import normalize_feature_fields
from apps.llm.json_output import extract_json_object as _extract_json_object
from apps.llm.messages import message_text


def _load_prd_template() -> str:
    """读取本地 PRD 格式模板文件，文件不存在或为空则返回空字符串"""
    root = get_settings().resources_dir.resolve()
    template_path = (root / "prd_template.md").resolve()
    if not template_path.is_relative_to(root):
        raise ValueError("Template path escapes resources_dir")
    try:
        return template_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _build_skill_section(sections: Dict[str, str], title: str = "团队规范与参考示例") -> str:
    """将 skill sections 拼成 prompt 段落。"""
    parts: List[str] = []
    role_labels = {
        "instructions": "生成说明",
        "reference": "规范与写作要点",
        "template": "输出模板",
        "example": "参考示例",
    }
    for role in ("instructions", "reference", "template", "example"):
        content = sections.get(role)
        if content:
            parts.append(f"### {role_labels.get(role, role)}\n\n{content}")
    if not parts:
        return ""
    return f"\n\n## {title}\n\n" + "\n\n".join(parts) + "\n\n"


def _artifact_for_optimize(doc_type: str) -> str:
    return {
        "prd": "optimize-prd",
        "api-docs": "optimize-api-docs",
        "prompts": "optimize-prompts",
    }.get(doc_type, "")


def _build_prd_prompt() -> str:
    """构建 PRD 生成 prompt，如有模板则附上格式参考"""
    template = _load_prd_template()
    if template:
        return (
            get_prompt("PRD_GENERATION_PROMPT")
            + f"\n\n请参考以下格式模板（仅作格式参考，内容以对话为准）：\n\n{template}"
        )
    return get_prompt("PRD_GENERATION_PROMPT")


def _build_prd_from_summary_prompt(requirements_summary: Dict[str, Any]) -> str:
    """基于结构化需求摘要构建 PRD 生成 prompt"""
    sections = compose_prompt_sections(load_skill_bundle("prd"))
    template = sections.get("template") or _load_prd_template()
    writing_rules = sections.get("reference", "")
    instructions = sections.get("instructions", "")
    summary_json = json.dumps(
        normalize_feature_fields(requirements_summary), ensure_ascii=False, indent=2
    )

    prompt_parts = [
        "请基于以下结构化需求摘要生成一份专业、简洁、工程可执行的 PRD。",
        "要求：",
        "1. 使用中文输出 Markdown。",
        "2. 严格遵循给定模板的章节结构。",
        "3. 不编造未提供的业务事实，缺失且重要的信息写“待确认”。",
        "4. 产品功能必须整理为表格，列为：功能名称、功能描述、用户价值。",
        "5. 技术规格中，已确认项直接写明；推测性实现建议使用“可采用/建议”表述。",
        "6. 删除重复信息，只保留对产品、设计、研发交接有用的内容。",
        "",
        "结构化需求摘要：",
        summary_json,
    ]

    if writing_rules:
        prompt_parts.extend(["", "补充写作规则：", writing_rules])
    if instructions:
        prompt_parts.extend(["", "补充生成说明：", instructions])
    if template:
        prompt_parts.extend(["", "输出模板：", template])

    return "\n".join(prompt_parts)


def _format_conversation_context(conversation_messages: List[Dict[str, str]]) -> str:
    """将澄清对话整理为可读上下文，供 PRD 生成参考"""
    lines: List[str] = []
    for msg in conversation_messages:
        role = msg.get("role", "")
        if role == "system":
            continue
        if role in ("assistant", "ai"):
            speaker = "AI"
        else:
            speaker = "用户"
        content = message_text(msg.get("content", "")).strip()
        if content:
            lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def _build_summary_sync_prompt(
    requirements_summary: Dict[str, Any],
    conversation_messages: List[Dict[str, str]],
) -> str:
    """构建结构化摘要回填 prompt，要求输出 JSON"""
    summary_json = json.dumps(
        normalize_feature_fields(requirements_summary), ensure_ascii=False, indent=2
    )
    conversation_text = _format_conversation_context(conversation_messages)
    schema_text = compose_prompt_sections(load_skill_bundle("prd")).get("schema") or json.dumps(
        RequirementsInput.model_json_schema(), ensure_ascii=False
    )

    prompt_parts = [
        "请根据以下结构化需求摘要和后续澄清对话，输出一份更新后的结构化需求摘要 JSON。",
        "要求：",
        "1. 只输出合法 JSON，不要输出 Markdown 代码块，不要输出解释。",
        "2. 保持原有字段结构，尽量不要新增字段。",
        "3. 仅在对话中出现了明确补充、修正或澄清时才更新字段。",
        "4. 不要编造信息；不确定的内容保留原值。",
        "5. 如果对话中补充了更明确的内容，应覆盖原先的“待确认”或较模糊值。",
        "6. features、ui_pages、interaction_notes、in_scope、out_of_scope 等字段保持结构化。",
        "",
        "当前结构化需求摘要：",
        summary_json,
        "",
        "澄清对话：",
        conversation_text or "（无）",
    ]

    if schema_text:
        prompt_parts.extend(["", "参考 schema：", schema_text])

    return "\n".join(prompt_parts)


def _truncate_text(text: str, max_len: int = 800) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n...<truncated>..."


def _parse_summary(text: str) -> dict[str, Any]:
    return input_dict(RequirementsInput.model_validate(_extract_json_object(text)))


def _build_json_repair_prompt(raw_text: str) -> str:
    return "\n".join(
        [
            "请把下面这段内容修复为一个合法的 JSON 对象。",
            "要求：",
            "1. 只输出 JSON 对象本身。",
            "2. 不要输出解释，不要输出 Markdown 代码块。",
            "3. 保持原字段结构和语义，不要新增无关字段。",
            "",
            "待修复内容：",
            raw_text,
        ]
    )


def _build_summary_regeneration_prompt(
    requirements_summary: Dict[str, Any],
    conversation_messages: List[Dict[str, str]],
) -> str:
    summary_json = json.dumps(
        normalize_feature_fields(requirements_summary), ensure_ascii=False, indent=2
    )
    conversation_text = _format_conversation_context(conversation_messages)
    return "\n".join(
        [
            "请重新输出一份更新后的结构化需求摘要 JSON。",
            "这是一次失败后的重试，请务必严格遵守格式。",
            "要求：",
            "1. 只输出一个合法 JSON 对象。",
            "2. 不要输出 Markdown，不要输出解释，不要输出代码块。",
            "3. 保持原字段结构；不要新增无关字段。",
            "4. 仅根据澄清对话中的明确内容更新字段。",
            "5. 无法确定的值保留原值。",
            "",
            "当前结构化需求摘要：",
            summary_json,
            "",
            "澄清对话：",
            conversation_text or "（无）",
        ]
    )
