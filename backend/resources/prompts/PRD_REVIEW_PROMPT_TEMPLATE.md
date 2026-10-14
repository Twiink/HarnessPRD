请审查以下 PRD 草稿。

输出要求：
1. 只输出 JSON 对象
2. JSON 结构如下：
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
3. 如果没有明显问题，issues 返回空数组，passed 为 true
4. 如果存在 high 严重级别问题，passed 必须为 false

补充上下文：

{review_context}

待审查的 PRD 草稿：

{prd_draft}