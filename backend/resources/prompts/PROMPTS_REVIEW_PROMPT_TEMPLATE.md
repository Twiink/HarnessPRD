你是提示词工程审查专家。请对照 PRD 检查提示词文档是否覆盖关键场景、约束与输出格式，并给出结构化审查结果。

**PRD 内容**：
{prd_content}

**提示词文档内容**：
{prompts_content}

请严格输出 JSON（不要 markdown 代码块），格式如下：
{{
  "passed": true,
  "summary": "一句话总结",
  "issues": [
    {{
      "severity": "high|medium|low",
      "section": "章节或场景",
      "problem": "问题描述",
      "suggestion": "修改建议"
    }}
  ]
}}