"""需求就绪度评估 — 与前端 requirementsReadiness 规则对齐"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.requirements_normalization import normalize_feature_fields


def _non_empty_lines(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [line.strip() for line in str(value).split("\n") if line.strip()]


def _has_nfr(summary: Dict[str, Any]) -> bool:
    nfr = summary.get("non_functional_requirements") or {}
    if not isinstance(nfr, dict):
        return False
    for key in ("performance", "security", "usability"):
        group = nfr.get(key)
        if isinstance(group, list) and any(str(item).strip() for item in group):
            return True
    return False


def assess_requirements_readiness(
    summary: Optional[Dict[str, Any]],
    messages: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    messages = messages or []

    if not summary:
        check = {
            "id": "summary.missing",
            "label": "结构化需求摘要",
            "passed": False,
            "severity": "blocker",
            "detail": "请先完成结构化表单",
        }
        return {
            "score": 0,
            "blockers": [check],
            "warnings": [],
            "checks": [check],
        }

    summary = normalize_feature_fields(summary)
    checks: List[Dict[str, Any]] = []

    product_name = str(summary.get("product_name") or "").strip()
    checks.append(
        {
            "id": "summary.product_name",
            "label": "产品名称",
            "passed": bool(product_name),
            "severity": "blocker",
            "detail": None if product_name else "请填写产品名称",
        }
    )

    product_goal = str(summary.get("product_goal") or "").strip()
    checks.append(
        {
            "id": "summary.product_goal",
            "label": "产品目标",
            "passed": len(product_goal) >= 10,
            "severity": "blocker",
            "detail": None if len(product_goal) >= 10 else "产品目标至少 10 字",
        }
    )

    features = summary.get("features") or []
    if not isinstance(features, list):
        features = []
    checks.append(
        {
            "id": "summary.features",
            "label": "产品功能",
            "passed": len(features) >= 1,
            "severity": "blocker",
            "detail": None if len(features) >= 1 else "至少填写 1 条 产品功能",
        }
    )

    platform = str(summary.get("platform") or "").strip()
    checks.append(
        {
            "id": "summary.platform",
            "label": "产品平台",
            "passed": bool(platform),
            "severity": "blocker",
            "detail": None if platform else "请填写产品平台",
        }
    )

    in_scope = _non_empty_lines(summary.get("in_scope"))
    checks.append(
        {
            "id": "summary.in_scope",
            "label": "在范围内",
            "passed": len(in_scope) >= 1,
            "severity": "warning",
            "detail": None if in_scope else "建议补充项目交付范围",
        }
    )

    out_scope = _non_empty_lines(summary.get("out_of_scope"))
    checks.append(
        {
            "id": "summary.out_of_scope",
            "label": "不在范围内",
            "passed": len(out_scope) >= 1,
            "severity": "warning",
            "detail": None if out_scope else "建议补充项目范围外的事项",
        }
    )

    checks.append(
        {
            "id": "summary.nfr",
            "label": "非功能需求",
            "passed": _has_nfr(summary),
            "severity": "warning",
            "detail": None if _has_nfr(summary) else "建议补充非功能需求",
        }
    )

    blockers = [c for c in checks if not c["passed"] and c["severity"] == "blocker"]
    warnings = [c for c in checks if not c["passed"] and c["severity"] == "warning"]

    weight_sum = sum(2 if c["severity"] == "blocker" else 1 for c in checks)
    earned = sum((2 if c["severity"] == "blocker" else 1) for c in checks if c["passed"])
    score = round((earned / weight_sum) * 100) if weight_sum else 0
    if blockers:
        score = min(score, 59)

    return {
        "score": score,
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
    }


def readiness_has_blockers(summary: Optional[Dict[str, Any]], messages: Optional[List] = None) -> bool:
    result = assess_requirements_readiness(summary, messages)
    return len(result["blockers"]) > 0


def first_blocker_message(summary: Optional[Dict[str, Any]], messages: Optional[List] = None) -> str:
    result = assess_requirements_readiness(summary, messages)
    blockers = result.get("blockers") or []
    if not blockers:
        return "需求尚未就绪"
    first = blockers[0]
    return first.get("detail") or first.get("label") or "需求尚未就绪"
