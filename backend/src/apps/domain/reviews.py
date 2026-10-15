"""Review contracts and normalization, independent of model and HTTP clients."""

from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class ReviewIssue(TypedDict):
    severity: str
    section: str
    problem: str
    suggestion: str


class ReviewResult(TypedDict):
    passed: bool
    summary: str
    issues: list[ReviewIssue]


class ReviewIssueInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")

    severity: str = "medium"
    section: str = ""
    category: str = ""
    problem: str = ""
    title: str = ""
    description: str = ""
    suggestion: str = ""


class ReviewInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")

    passed: bool | None = None
    summary: str = ""
    issues: list[ReviewIssueInput] = Field(default_factory=list)
    overall_score: int | float | None = None


def normalize_document_review(
    parsed: dict[str, Any], default_section: str, *, fill_failed_issue: bool = True
) -> ReviewResult:
    """Validate types before applying the existing legacy-field normalization."""
    review = ReviewInput.model_validate(parsed)
    issues: list[ReviewIssue] = []
    for item in review.issues:
        problem = (item.problem or item.title or item.description).strip()
        suggestion = item.suggestion.strip()
        if not problem and not suggestion:
            continue
        issues.append(
            {
                "severity": item.severity or "medium",
                "section": item.section or item.category or default_section,
                "problem": problem or suggestion,
                "suggestion": suggestion,
            }
        )

    summary = review.summary.strip()
    passed = review.passed
    if passed is None:
        # A missing decision and score cannot establish a successful review.
        passed = review.overall_score >= 70 if review.overall_score is not None else False

    if fill_failed_issue and not passed and not issues:
        summary = summary or "审查未通过，但未返回具体问题。"
        issues.append(
            {
                "severity": "medium",
                "section": default_section,
                "problem": summary,
                "suggestion": "请通读文档与质量报告，或使用「优化文档」补充修订。",
            }
        )

    return {"passed": passed, "summary": summary, "issues": issues}


def build_parse_failed_review(default_section: str) -> ReviewResult:
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
