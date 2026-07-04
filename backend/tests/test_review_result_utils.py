from services.review_result_utils import build_parse_failed_review, normalize_document_review


def test_normalize_review_fills_issue_when_failed_without_details():
    result = normalize_document_review(
        {"passed": False, "summary": "", "issues": []},
        default_section="接口文档",
    )
    assert result["passed"] is False
    assert len(result["issues"]) == 1
    assert "未返回具体问题" in result["issues"][0]["problem"]


def test_normalize_review_keeps_meaningful_issues_only():
    result = normalize_document_review(
        {
            "passed": False,
            "summary": "存在遗漏",
            "issues": [
                {"severity": "high", "section": "创建申请", "problem": "缺少错误码", "suggestion": "补充 400"},
                {"severity": "low", "section": "", "problem": "", "suggestion": ""},
            ],
        },
        default_section="接口文档",
    )
    assert len(result["issues"]) == 1
    assert result["issues"][0]["problem"] == "缺少错误码"


def test_normalize_review_uses_summary_as_issue_when_failed():
    result = normalize_document_review(
        {"passed": False, "summary": "部分接口未覆盖", "issues": []},
        default_section="接口文档",
    )
    assert len(result["issues"]) == 1
    assert result["issues"][0]["problem"] == "部分接口未覆盖"


def test_build_parse_failed_review_has_issue():
    result = build_parse_failed_review("提示词")
    assert result["passed"] is False
    assert len(result["issues"]) == 1
