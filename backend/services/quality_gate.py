"""文档结构校验 quality_gate — 确定性规则，不调用 LLM"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _check(
    check_id: str,
    label: str,
    passed: bool,
    severity: str = "high",
    detail: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "passed": passed,
        "severity": severity,
        "detail": detail,
    }


def _section_present(content: str, pattern: str) -> bool:
    return bool(re.search(pattern, content, re.IGNORECASE | re.MULTILINE))


def _count_mvp_table_rows(prd_content: str) -> int:
    lines = prd_content.splitlines()
    in_table = False
    count = 0
    for line in lines:
        stripped = line.strip()
        if re.search(r"\|\s*功能名称\s*\|", stripped, re.IGNORECASE):
            in_table = True
            continue
        if in_table:
            if stripped.startswith("|") and not re.match(r"^\|\s*[-—:]+\s*\|", stripped):
                if not re.search(r"功能名称", stripped, re.IGNORECASE):
                    count += 1
            elif stripped and not stripped.startswith("|"):
                break
    return count


def _scope_has_content(content: str, keyword: str) -> bool:
    pattern = rf"\*?\*?{re.escape(keyword)}[^*\n]*\*?\*?[：:]*\s*\n([\s\S]*?)(?:\n##|\Z)"
    match = re.search(pattern, content)
    if not match:
        return False
    block = match.group(1)
    lines = [ln.strip() for ln in block.splitlines() if ln.strip() and ln.strip() != "-"]
    return len(lines) >= 1


def _run_prd_checks(content: str) -> List[Dict[str, Any]]:
    checks = [
        _check("prd.section.overview", "产品概述章节", _section_present(content, r"##\s*1\.\s*产品概述")),
        _check("prd.section.features", "功能需求章节", _section_present(content, r"##\s*2\.\s*功能需求")),
        _check("prd.section.pages", "页面设计章节", _section_present(content, r"##\s*3\.\s*页面设计")),
        _check("prd.section.tech", "技术规格章节", _section_present(content, r"##\s*4\.\s*技术规格")),
        _check("prd.section.nfr", "非功能需求章节", _section_present(content, r"##\s*5\.\s*非功能需求")),
        _check("prd.section.scope", "项目范围章节", _section_present(content, r"##\s*6\.\s*项目范围")),
        _check(
            "prd.mvp.table",
            "MVP 功能表格",
            bool(re.search(r"\|\s*功能名称\s*\|", content, re.IGNORECASE)),
        ),
        _check("prd.scope.in", "在范围内", _scope_has_content(content, "在范围内")),
        _check("prd.scope.out", "不在范围内", _scope_has_content(content, "不在范围内")),
    ]
    pending_count = len(re.findall(r"待确认", content))
    checks.append(
        _check(
            "prd.pending.count",
            "待确认项数量",
            pending_count <= 5,
            severity="medium",
            detail=None if pending_count <= 5 else f"出现 {pending_count} 处「待确认」，建议控制在 5 以内",
        )
    )
    return checks


_HTTP_METHOD = r"(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)"


def _count_api_endpoint_definitions(content: str) -> int:
    """识别接口条目：支持标题行内联写法，以及 skill 模板的「方法 + 路径」分行写法。"""
    inline_heading = len(
        re.findall(
            rf"(?:^|\n)#+\s[^\n]*(?:{_HTTP_METHOD}|/api/)",
            content,
            re.IGNORECASE,
        )
    )
    structured_paths = len(
        re.findall(
            r"路径[\s*：:]*[`'\"]?(/api/v\d+/[^\s`'\"`\n]+)",
            content,
            re.IGNORECASE,
        )
    )
    inline_method_path = len(
        re.findall(
            rf"(?:^|\n)\s*(?:-\s*)?(?:\*\*)?\s*({_HTTP_METHOD})\s+(/api/v\d+/[^\s\n]+)",
            content,
            re.IGNORECASE,
        )
    )
    return max(inline_heading, structured_paths, inline_method_path)


def _run_api_docs_checks(content: str) -> List[Dict[str, Any]]:
    endpoint_count = _count_api_endpoint_definitions(content)
    return [
        _check("api.section.core", "核心接口分区", bool(re.search(r"核心接口", content))),
        _check(
            "api.section.edge",
            "边缘/辅助接口分区",
            bool(re.search(r"边缘接口|辅助接口", content)),
        ),
        _check(
            "api.response.wrapper",
            "统一响应结构",
            bool(re.search(r'"code"', content) and re.search(r'"data"', content)),
        ),
        _check("api.path.prefix", "API 路径前缀", bool(re.search(r"/api/v1", content))),
        _check(
            "api.endpoint.count",
            "接口条目",
            endpoint_count >= 1,
            detail=None if endpoint_count >= 1 else "未识别到接口定义（需含 HTTP 方法与 /api/v1/ 路径）",
        ),
    ]


def _count_prompt_feature_headings(content: str) -> int:
    section_match = re.search(r"功能开发[\s\S]*", content, re.IGNORECASE)
    if not section_match:
        return 0
    section = section_match.group(0)
    return len(re.findall(r"^###\s+", section, re.MULTILINE))


def _run_prompts_checks(content: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    context = context or {}
    checks = [
        _check(
            "prompts.section.context",
            "项目总览章节",
            bool(re.search(r"项目总览|Project Context", content, re.IGNORECASE)),
        ),
        _check(
            "prompts.section.features",
            "功能开发章节",
            bool(re.search(r"功能开发", content)),
        ),
        _check(
            "prompts.section.frontend",
            "前端开发章节",
            bool(re.search(r"前端开发", content)),
        ),
        _check(
            "prompts.section.review",
            "代码审查章节",
            bool(re.search(r"代码审查|Code Review", content, re.IGNORECASE)),
        ),
    ]

    skip_api = context.get("api_docs_skipped") or not (context.get("api_docs_content") or "").strip()
    if skip_api:
        checks.append(
            _check(
                "prompts.section.api",
                "接口实现章节",
                True,
                severity="low",
                detail="skipped",
            )
        )
    else:
        checks.append(
            _check(
                "prompts.section.api",
                "接口实现章节",
                bool(re.search(r"接口实现", content)),
            )
        )

    prd_content = (context.get("prd_content") or "").strip()
    feature_headings = _count_prompt_feature_headings(content)
    if prd_content:
        expected = _count_mvp_table_rows(prd_content)
        if expected == 0:
            expected = max(1, len(re.findall(r"^\|\s*[^|]+\s*\|", prd_content, re.MULTILINE)) - 1)
        diff = abs(feature_headings - expected) if expected else 0
        checks.append(
            _check(
                "prompts.feature.count",
                "功能提示词数量",
                expected == 0 or diff <= 1,
                severity="high",
                detail=None
                if expected == 0 or diff <= 1
                else f"功能开发提示词 {feature_headings} 条，PRD MVP 约 {expected} 条",
            )
        )
    else:
        checks.append(
            _check(
                "prompts.feature.count",
                "功能提示词数量",
                True,
                severity="low",
                detail="skipped",
            )
        )

    return checks


def _compute_score_and_passed(checks: List[Dict[str, Any]]) -> tuple[int, bool]:
    if not checks:
        return 0, False
    weight_map = {"high": 2, "medium": 1, "low": 1}
    total = sum(weight_map.get(c["severity"], 1) for c in checks)
    earned = sum(weight_map.get(c["severity"], 1) for c in checks if c["passed"])
    score = round((earned / total) * 100) if total else 0
    passed = all(c["passed"] for c in checks if c["severity"] == "high")
    return score, passed


def run_quality_gate(
    doc_type: str,
    content: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    try:
        text = (content or "").strip()
        if not text:
            checks = [
                _check("empty_content", "文档非空", False, detail="文档内容为空"),
            ]
            score, passed = _compute_score_and_passed(checks)
            return {
                "passed": passed,
                "score": score,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "doc_type": doc_type,
                "checks": checks,
            }

        if doc_type == "prd":
            checks = _run_prd_checks(text)
        elif doc_type == "api-docs":
            checks = _run_api_docs_checks(text)
        elif doc_type == "prompts":
            checks = _run_prompts_checks(text, context)
        else:
            checks = [_check("unsupported", "文档类型", False, detail=f"未知类型 {doc_type}")]

        score, passed = _compute_score_and_passed(checks)
        return {
            "passed": passed,
            "score": score,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "doc_type": doc_type,
            "checks": checks,
        }
    except Exception as exc:
        return {
            "passed": False,
            "score": 0,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "doc_type": doc_type,
            "checks": [
                _check("gate.error", "质量校验", False, detail=str(exc)),
            ],
        }


def build_gate_context_from_job(job: Dict[str, Any], session_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    session_data = session_data or {}
    try:
        payload = json.loads(job.get("payload_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        payload = {}

    ctx: Dict[str, Any] = {}
    prd = payload.get("prd_content") or session_data.get("prdContent") or ""
    api_docs = payload.get("api_docs_content") or session_data.get("apiDocsContent") or ""
    ctx["prd_content"] = str(prd)[:50000]
    ctx["api_docs_content"] = str(api_docs)[:50000]
    if job.get("artifact") == "prompts" and not str(api_docs).strip():
        ctx["api_docs_skipped"] = True
    return ctx
