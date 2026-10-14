请重新审查以下 PRD 草稿，并只输出一个合法 JSON 对象。
这是一次失败后的重试，请务必严格遵守格式。
JSON 结构必须如下：
{{
  "passed": true,
  "summary": "一句话总结审查结论",
  "issues": [
    {{
      "severity": "high",
      "section": "产品功能",
      "problem": "问题描述",
      "suggestion": "修改建议"
    }}
  ]
}}
如果没有明显问题，issues 返回空数组。

补充上下文：
{review_context}

待审查的 PRD 草稿：
{prd_draft}