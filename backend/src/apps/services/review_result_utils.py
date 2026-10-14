"""Shared helpers for document review agent JSON normalization."""

from __future__ import annotations

from typing import Any, Dict, List


def normalize_document_review(parsed: Dict[str, Any], default_section: str) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    for item in parsed.get("issues") or []:
        if not isinstance(item, dict):
            continue
        problem = str(
            item.get("problem") or item.get("title") or item.get("description") or ""
        ).strip()
        suggestion = str(item.get("suggestion") or "").strip()
        if not problem and not suggestion:
            continue
        issues.append(
            {
                "severity": item.get("severity") or "medium",
                "section": item.get("section") or item.get("category") or default_section,
                "problem": problem or suggestion,
                "suggestion": suggestion,
            }
        )

    summary = str(parsed.get("summary") or "").strip()
    passed = parsed.get("passed")
    if passed is None:
        score = parsed.get("overall_score")
        if score is not None:
            try:
                passed = int(score) >= 70
            except (TypeError, ValueError):
                passed = len(issues) == 0
        else:
            passed = len(issues) == 0

    passed = bool(passed)

    if not passed and not issues:
        if not summary:
            summary = "审查未通过，但未返回具体问题。"
        issues.append(
            {
                "severity": "medium",
                "section": default_section,
                "problem": summary,
                "suggestion": "请通读文档与质量报告，或使用「优化文档」补充修订。",
            }
        )

    return {
        "passed": passed,
        "summary": summary,
        "issues": issues,
    }


def build_parse_failed_review(default_section: str) -> Dict[str, Any]:
    summary = "Review 结果解析失败"
    return {
        "passed": False,
        "summary": summary,
        "issues": [
            {
                "severity": "medium",
                "section": default_section,
                "problem": summary,
                "suggestion": "请重新生成，或使用「优化文档」手动修订。",
            }
        ],
    }
