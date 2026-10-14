你是 API 文档质量审查专家。请对照 PRD 检查 API 文档是否覆盖关键接口、字段与错误码，并给出结构化审查结果。

**PRD 内容**：
{prd_content}

**API 文档内容**：
{api_docs_content}

请严格输出 JSON（不要 markdown 代码块），格式如下：
{{
  "passed": true,
  "summary": "一句话总结",
  "issues": [
    {{
      "severity": "high|medium|low",
      "section": "章节或接口名",
      "problem": "问题描述",
      "suggestion": "修改建议"
    }}
  ]
}}