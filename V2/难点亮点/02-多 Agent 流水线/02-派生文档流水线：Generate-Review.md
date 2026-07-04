# 派生文档流水线：Generate-Review

harnessprd 最终生成三份产物：PRD、接口文档、提示词套件。三份产物共享同一种流水线结构：先生成，再审查。区别只有一个——PRD 在审查不通过时会自动进入 Rewriter，接口文档和提示词套件不会。

## 三条管线对比

| 维度 | PRD | 接口文档 | 提示词套件 |
|------|-----|--------|----------|
| 生成步骤 | Writer → Reviewer → Rewriter（可选）| Generator → Reviewer | Generator → Reviewer |
| 编排入口 | `generate_prd_from_summary_stream` | `generate_api_docs_stream` | `generate_prompts_stream` |
| 上游输入 | 结构化需求摘要 + 澄清对话 | PRD + 澄清对话 | PRD + 接口文档（可选） |
| Reviewer | `PrdReviewAgent` | `ApiDocsReviewAgent` | `PromptsReviewAgent` |
| 容错链 | 三级（提取→修复→重生成，失败 raise）| 两级（提取→修复，失败返回合成 review）| 两级（同接口文档）|
| 审查不通过 | 自动触发 Rewriter 修订 | 记录到结果，不自动修订 | 记录到结果，不自动修订 |
| revision_applied | 有，记录是否经过修订 | 无 | 无 |

接口文档和提示词套件目前不进入 Rewriter，因为这两份文档的修订逻辑更依赖 PRD 内容，Rewriter 需要更多上下文才能做有意义的修改。

![三类文档的 Generate-Review 流水线对比](https://pic.niumianoffer.com/images/fs/02-02-pipeline-comparison.png)

## 依赖图与生成顺序

三份文档之间有明确的上游依赖，决定了生成必须按顺序进行：

```
澄清对话 → 结构化需求摘要
                │
                ▼
              PRD ← 必须先确认基线（prdBaselineConfirmed）
                │
        ┌───────┴───────┐
        ▼               ▼
    接口文档        提示词套件 ← 可选接入接口文档内容
```

- 接口文档依赖 PRD：生成时把当前 PRD 内容注入 prompt，Reviewer 也用 PRD 作为对照基准
- 提示词套件依赖 PRD，可选接入接口文档：`api_docs_content` 如果为空，`_build_derived_from` 会记录 `api_docs_skipped=True`，不影响生成，只影响版本元数据
- PRD 未确认基线时，`assert_can_create_job()` 交付守卫会直接拒绝接口文档和提示词套件的创建请求（HTTP 400）

![文档依赖关系与生成顺序](https://pic.niumianoffer.com/images/fs/02-02-doc-dependency-order.png)

## 接口文档和提示词管线：两步版

两条管线共用同一个执行器 `_run_chunk_job()`。职责拆成两层：`document_service` 里的 `generate_*_stream` 只负责**拼 prompt、调 LLM/Reviewer、yield 事件**；`_run_chunk_job` 负责**消费事件**——写 Job 状态、节流落库、推 SSE、同步 Session 和文档版本。接口文档和提示词没有 Rewriter，事件类型固定，所以把 Job 运行时抽成共用执行器；PRD 因要处理 `rewrite_started`、v1/v2 草稿切换等，仍走独立的 `run_prd_job()`。

前端 `POST /api/jobs` 创建 Job 后，`schedule_job()` 用 `asyncio.create_task` 拉起对应 runner。接口文档入口很薄，只是把 stream 工厂传给执行器：

```python
# harnessprd/backend/services/job_runner.py

async def run_api_docs_job(job_id: str) -> None:
    await _run_chunk_job(
        job_id,
        "api-docs",
        lambda payload: document_service.generate_api_docs_stream(
            payload["prd_content"],
            payload.get("conversation_messages") or [],
        ),
    )
```

`stream_factory` 是一个异步生成器工厂：执行器从 Job 读出 `payload_json` 后调用 `stream_factory(payload)`，得到下面这条事件流。以接口文档为例，**内容生产**在 `document_service`：

```python
# harnessprd/backend/services/document_service.py

async def generate_api_docs_stream(
    self,
    prd_content: str,
    conversation_messages: List[Dict[str, str]],
) -> AsyncGenerator[Dict, None]:
    # 加载接口文档 Skill 并组装规范段落
    sections = compose_prompt_sections(load_skill_bundle("api-docs"))
    skill_section = _build_skill_section(sections, title="团队接口规范与参考示例")
    llm = get_tracked_llm(LlmStep.API_DOCS_GENERATE.value, temperature=0.3)
    lc_messages = _build_lc_messages(conversation_messages)
    conversation_text = _format_conversation_context(conversation_messages)
    conversation_section = (
        f"\n\n澄清对话摘要：\n\n{conversation_text}\n\n" if conversation_text else ""
    )
    # 把 PRD、澄清摘要、Skill 规范和生成指令合并为最后一条 HumanMessage
    lc_messages.append(HumanMessage(
        content=(
            f"以下是已确认的产品需求文档（PRD）：\n\n{prd_content}"
            f"{conversation_section}"
            f"{skill_section}"
            f"{API_DOCS_GENERATION_PROMPT}"
        )
    ))

    # Generator 流式输出全部内容
    draft = ""
    async for chunk in llm.astream(lc_messages):
        if chunk.content:
            draft += chunk.content
            yield {"type": "chunk", "content": chunk.content}

    yield {"type": "phase", "phase": "review_started"}
    # Reviewer 非流式调用，审查草稿并返回结构化结果
    review_result = await self.api_docs_reviewer.review(prd_content, draft)
    yield {"type": "review", "content": review_result}
    # done 事件同时携带草稿内容和审查结果
    yield {"type": "done", "content": draft, "review": review_result}
```

执行器 `_run_chunk_job` 用 `async for event in stream_factory(payload)` 逐条消费上述事件，并做 Job 层统一处理：

| 事件 | 执行器行为 |
|------|-----------|
| `chunk` | 累加 draft，500ms 节流写入 `draft_content`，转为 `text_delta` 推给前端 |
| `phase: review_started` | Job `phase` 切到 `reviewing`，原样 publish |
| `review` | 写入 `review_json`，publish 给审查面板（**不改正文**） |
| `done` | Job 标为 `completed`，正文与 review 分别落库；review 进版本 `metadata`，Session 更新 `apiDocsContent` |

`done` 里的 `content` 是接口文档 Markdown 正文；`review` 是独立结构化结果，不会写入 `.md` 文件，前端从版本 metadata 读取展示。提示词套件的结构完全相同，只是 `run_prompts_job` 传入 `generate_prompts_stream`，输入变为 PRD 加接口文档，Reviewer 换为 `PromptsReviewAgent`。

## 派生关系追踪

每次生成时，Job 层会查当前 session 下各文档的最新版本，把依赖信息写入 `derived_from`：

```python
# harnessprd/backend/services/job_runner.py

def _build_derived_from(session_id, artifact, payload) -> Dict[str, Any]:
    derived: Dict[str, Any] = {}
    # 所有派生文档都记录依赖的 PRD 版本
    prd_current = get_current_version(session_id, "prd")
    if prd_current:
        derived["prd_version_id"] = prd_current["id"]
        derived["prd_version_no"] = prd_current["version_no"]
    if artifact == "prompts":
        api_docs_content = (payload.get("api_docs_content") or "").strip()
        if not api_docs_content:
            derived["api_docs_skipped"] = True  # 未传入接口文档，跳过版本记录
        else:
            api_current = get_current_version(session_id, "api-docs")
            if api_current:
                derived["api_docs_version_id"] = api_current["id"]
                derived["api_docs_version_no"] = api_current["version_no"]
    return derived
```

这份元数据存在版本记录里。如果 PRD 更新后重新生成了 v3，而接口文档的 `derived_from.prd_version_no` 还是 2，就能知道接口文档已经过期，可以提示用户重新生成。

## Phase 事件与前端进度

三条管线都通过 phase 事件向前端推送阶段状态。Job 层在每次 phase 切换时同步更新数据库里的 phase 字段：

```python
# harnessprd/backend/services/job_runner.py

# 从 SSE 事件类型到数据库 phase 字段的映射
PHASE_FROM_EVENT = {
    "writer_started": "writing",
    "review_started": "reviewing",
    "rewrite_started": "rewriting",
}
```

PRD 管线因为可能触发 Rewriter，最多有三个 phase；接口文档和提示词最多两个（`generating` → `reviewing`）。这让前端进度条的行为跟实际流程保持一致，不会在"完成"前空等一个不存在的 rewrite 阶段。
