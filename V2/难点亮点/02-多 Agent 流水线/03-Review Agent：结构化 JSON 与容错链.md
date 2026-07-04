# Review Agent：结构化 JSON 与容错链

Review Agent 的核心职责很简单：审查草稿，输出一份结构化意见。但这里有一个根本性的挑战——让语言模型每次都输出合法 JSON，比想象中难得多。模型可能用 Markdown 代码块包裹 JSON，可能在 JSON 前面加一段解释，也可能输出语法错误的 JSON，比如单引号代替双引号、末尾多了逗号。

harnessprd 有三个独立的 Review Agent：`PrdReviewAgent`、`ApiDocsReviewAgent`、`PromptsReviewAgent`。它们共享相同的智能提取逻辑（第一层），但容错链的深度不同，失败兜底策略也不同——这篇文章先以 PRD 为例把三级容错链讲清楚，再结合前面的管线视图对比两条链的具体差异。

## 期望的输出结构

Review Agent 要求模型只输出这样的 JSON 对象：

```json
{
  "passed": true,
  "summary": "一句话总结审查结论",
  "issues": [
    {
      "severity": "high",
      "section": "MVP 功能",
      "problem": "问题描述",
      "suggestion": "修改建议"
    }
  ]
}
```

`passed` 决定流程是否需要进入 Rewriter；`issues` 里的每一条都有具体的章节、问题和建议，Rewriter 用这份意见定向修改，不会大范围重写。

问题在于，即使 System Prompt 里反复强调"只输出 JSON"，模型也可能在第一行加上"以下是审查结果："之类的导语，或者把 JSON 包在 Markdown 代码块里。这些情况都会导致直接 `json.loads()` 失败。

![Review JSON 驱动 Rewriter 定向修订](https://pic.niumianoffer.com/images/fs/02-03-review-json-rewriter.png)

## 第一层：智能提取

提取逻辑由 `_extract_json_object()` 承担。它的策略是先找 Markdown 代码块里的内容，把代码块里的文本作为候选解析对象；如果没有代码块，就把整段输出作为候选。对每段候选文本，先试 `json.loads()` 直接解析；失败了再从每个 `{` 字符位置开始，用增量解码器试着提取第一个合法 JSON 对象。

```python
# harnessprd/backend/services/prd_review_agent.py

def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    # 先找 Markdown 代码块里的内容，作为优先候选
    fenced_blocks = re.findall(
        r"```(?:json)?\s*(.*?)```",
        text,
        flags=re.DOTALL | re.IGNORECASE
    )
    # 有代码块就用代码块内容，否则把整段输出作为候选
    candidates = [block.strip() for block in fenced_blocks if block.strip()] or [text]
    decoder = json.JSONDecoder()

    for candidate_text in candidates:
        # 先试直接解析，处理格式完全正确的情况
        try:
            parsed = json.loads(candidate_text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # 直接解析失败，从每个 { 位置开始增量解码，跳过前面可能的导语文字
        for match in re.finditer(r"\{", candidate_text):
            try:
                parsed, _ = decoder.raw_decode(candidate_text[match.start():])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

    raise ValueError("review agent 未返回 JSON 对象")
```

这一层能处理大多数情况：模型在 JSON 前加了说明文字，或者把 JSON 放在 Markdown 代码块里，都能正确提取。

## 第二层：JSON 修复

如果第一层提取失败，说明模型输出的内容根本不是合法 JSON 结构。这时候，与其直接放弃，不如再调一次模型，让它专门做修复任务。

修复 prompt 非常明确：把原始输出给模型，要求它只输出一个合法 JSON 对象，不要解释，不要代码块，必须包含 `passed`、`summary`、`issues` 这三个字段。修复模型的 temperature 也设为 0，让输出尽量确定。

```python
# harnessprd/backend/services/prd_review_agent.py

# System Prompt 只声明角色，让模型专注于修格式而不是重新审查
repair_messages = [
    SystemMessage(
        content="你是一位严格的 JSON 修复助手。你的唯一任务是输出合法 JSON 对象。"
    ),
    # 把原始输出作为待修复内容传入，由 repair prompt 组装后发送
    HumanMessage(content=_build_review_repair_prompt(raw_content)),
]
# temperature=0 让修复结果尽量确定，不引入新的随机性
repair_llm = get_tracked_llm(LlmStep.JSON_REPAIR.value, temperature=0)
repair_response = await repair_llm.ainvoke(repair_messages)
```

修复的思路是把模型当成一个 JSON 格式化工具来用。原始内容里的语义是对的，只是格式坏了，让另一次调用专门修格式，成本低，成功率高。

## 第三层：完整重生成

如果连修复都失败了，说明原始输出质量太低，连修复都无从下手。这时候执行最后一级回退：完全重新审查一遍，但用的是格式要求更严格的 prompt。

重生成 prompt 不只是"再来一次"，而是把 JSON 结构模板完整打印在 prompt 里，告诉模型"上一次格式出了问题，这次你必须严格按这个结构输出"：

```python
# harnessprd/backend/services/prd_review_agent.py

def _build_review_regeneration_prompt(review_context: str, prd_draft: str) -> str:
    return "\n".join([
        # 明确告知模型这是失败重试，强化格式遵守意识
        "请重新审查以下 PRD 草稿，并只输出一个合法 JSON 对象。",
        "这是一次失败后的重试，请务必严格遵守格式。",
        # 把完整 JSON 模板嵌入 prompt，让模型有具体填写示例可参考
        "JSON 结构必须如下：",
        "{",
        '  "passed": true,',
        '  "summary": "一句话总结审查结论",',
        '  "issues": [',
        "    {",
        '      "severity": "high",',
        '      "section": "MVP 功能",',
        '      "problem": "问题描述",',
        '      "suggestion": "修改建议"',
        "    }",
        "  ]",
        "}",
        # ... 原始草稿
    ])
```

这一步的设计思路是：显式地把 JSON 模板嵌入 prompt，让模型几乎没有机会偏离格式。在模型对格式指令不够敏感的情况下，直接给一个具体的填写示例比抽象描述"输出 JSON"效果好得多。

## 三级容错链全貌

```
模型原始输出
    │
    ▼
_extract_json_object()
    │
    ├─ 成功 ──────────────────────────▶ 返回结果
    │
    └─ 失败
         │
         ▼
    JSON 修复调用（repair prompt + temperature=0）
         │
         ├─ 成功 ──────────────────────▶ 返回结果
         │
         └─ 失败
              │
              ▼
         完整重生成（regeneration prompt，内嵌 JSON 模板）
              │
              ├─ 成功 ────────────────▶ 返回结果
              │
              └─ 失败 ────────────────▶ 抛出异常（整个 Job 失败）
```

最终无论走了哪条路，成功拿到 dict 之后还有一步兜底（仅 PRD）：

```python
# harnessprd/backend/services/prd_review_agent.py

# 对最终结果做字段兜底，防止后续代码因 KeyError 崩溃
review_result.setdefault("passed", False)
review_result.setdefault("summary", "")
review_result.setdefault("issues", [])
```

即使模型只返回了部分字段，后续代码也能安全访问三个字段，不会因为 KeyError 崩溃。

![PRD 三级容错链与派生文档两级容错链对比](https://pic.niumianoffer.com/images/fs/02-03-review-fallback-chain.png)

## 两套策略：PRD 三级链 vs 派生文档两级链

`ApiDocsReviewAgent` 和 `PromptsReviewAgent` 的容错链**只有两级**，且失败时的处理策略与 PRD 完全不同：

```
PRD（三级链）
    提取 → 修复 → 重生成 → 抛出异常（整个 Job 失败）
    成功后：setdefault 补缺省字段

接口文档 / 提示词（两级链）
    提取 → 修复 → build_parse_failed_review（合成失败 review，Job 继续）
    成功后：normalize_document_review（语义归一化）
```

关键差异有两点：

**深度不同**：PRD 在修复失败后还有第三级重生成兜底，然后才 raise；api-docs / prompts 修复失败后直接返回合成结果，不会抛出异常。

**失败行为不同**：PRD 审查解析失败会让整个 Job 失败，因为 PRD 需要决定是否触发 Rewriter，JSON 不可缺；api-docs / prompts 不触发 Rewriter，审查 JSON 只是附加信息，Job 可以带着合成的失败 review 继续走完流程。

```python
# harnessprd/backend/services/api_docs_review_agent.py

class ApiDocsReviewAgent:
    async def review(self, prd_content: str, api_docs_content: str) -> Dict[str, Any]:
        # ...
        try:
            parsed = _extract_json_object(raw_content)   # 第一层：提取
            return _normalize_review(parsed)
        except Exception:
            # 第二层：修复
            repair_response = await repair_llm.ainvoke([...])
            try:
                parsed = _extract_json_object(str(repair_response.content).strip())
                return _normalize_review(parsed)
            except Exception:
                # 修复失败：返回合成 review，Job 继续运行，不 raise
                return build_parse_failed_review("接口文档")
```

`build_parse_failed_review` 返回一个 `passed=False`、带有占位 issue 的合成 dict，让下游代码有一个格式正确的结构可以消费：

```python
# harnessprd/backend/services/review_result_utils.py

def build_parse_failed_review(default_section: str) -> Dict[str, Any]:
    summary = "Review 结果解析失败"
    return {
        "passed": False,
        "summary": summary,
        "issues": [{
            "severity": "medium",
            "section": default_section,
            "problem": summary,
            "suggestion": "请重新生成，或使用「优化文档」手动修订。",
        }],
    }
```

## 语义归一化：normalize_document_review

PRD 用 `setdefault` 只补缺字段，不改值。派生文档在此基础上多了一步语义归一化——因为不同模型、不同 prompt 的输出格式差异更大，字段名可能不一致，`passed` 可能用 `overall_score` 替代表达，issue 对象里的 key 也可能不标准。

`normalize_document_review` 统一处理这些差异：

```python
# harnessprd/backend/services/review_result_utils.py

def normalize_document_review(parsed: Dict[str, Any], default_section: str) -> Dict[str, Any]:
    issues = []
    for item in parsed.get("issues") or []:
        # 字段别名容错：title / description 都可以作为 problem 来源
        problem = str(item.get("problem") or item.get("title") or item.get("description") or "").strip()
        suggestion = str(item.get("suggestion") or "").strip()
        if not problem and not suggestion:
            continue  # 完全空的 issue 直接丢弃
        issues.append({
            "severity": item.get("severity") or "medium",
            # section 别名容错：category 也可以作为 section 来源
            "section": item.get("section") or item.get("category") or default_section,
            "problem": problem or suggestion,
            "suggestion": suggestion,
        })

    passed = parsed.get("passed")
    if passed is None:
        # 部分模型用 overall_score 而不是 passed，尝试转换
        score = parsed.get("overall_score")
        if score is not None:
            try:
                passed = int(score) >= 70
            except (TypeError, ValueError):
                passed = len(issues) == 0
        else:
            passed = len(issues) == 0

    # 语义兜底：not passed 但 issues 为空时，自动补一条占位 issue
    if not passed and not issues:
        summary = str(parsed.get("summary") or "").strip() or "审查未通过，但未返回具体问题。"
        issues.append({
            "severity": "medium",
            "section": default_section,
            "problem": summary,
            "suggestion": "请通读文档与质量报告，或使用「优化文档」补充修订。",
        })

    return {"passed": bool(passed), "summary": str(parsed.get("summary") or "").strip(), "issues": issues}
```

这一步在语法容错（能提取出 dict）之后才触发，是语义层面的归一化：把各种格式的输出统一成下游代码能消费的标准结构。

| | PRD | 接口文档 / 提示词 |
|---|---|---|
| 容错层数 | 三级（提取→修复→重生成）| 两级（提取→修复）|
| 全部失败时 | 抛出异常，Job 失败 | 返回合成 review，Job 继续 |
| 成功后处理 | `setdefault` 补缺省 | `normalize_document_review` 语义归一化 |

## 为什么不直接用工具调用

现代 LLM API 提供了 function calling 和 structured output 能力，可以从协议层强制 JSON 输出。这套容错链是针对不支持这些特性的模型场景（比如 MiniMax）设计的，同时也是一种防御性设计——即使模型 API 支持结构化输出，边界情况下的格式异常依然存在，容错逻辑作为兜底仍然有价值。

三级容错的代价是最坏情况下多出两次 LLM 调用，但这比让整个生成流程因一次格式异常崩溃要好得多。在实际运行中，第一层提取能覆盖绝大多数情况，第二层和第三层只是安全网。
