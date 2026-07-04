# 职责分离：Writer · Reviewer · Rewriter 的三角设计

harnessprd 的 PRD 生成不是一个单独的大型 prompt 搞定所有事。整个流程拆给三个独立的 Agent 各管一块：Writer 负责写，Reviewer 负责审，Rewriter 负责改。这种三角结构看上去增加了调用次数，但它解决的是一个很实际的问题——如果试过用一个 prompt 同时让模型写文档、自检问题、再自我修改，会发现三件事在一个上下文里互相干扰，哪件都做不好。

## 为什么要分开

让模型生成 PRD 的同时审查自己的输出，效果很差。模型在生成文本时倾向于沿着已有内容的方向继续，自我批评的动机不足，很难发现刚写完的内容有什么问题。这就像让作者在刚写完稿子之后立刻审校，不换一双眼睛。

把生成和审查分成两次独立调用，Reviewer 拿到的是一份完整草稿，它的角色只有一个：找问题。它不需要顾及如何生成下一句，只需要对照需求检查草稿是否覆盖完整、是否有矛盾。

Rewriter 拿到的则是草稿加审查意见，任务是针对问题点修订，对没有问题的部分尽量不动。如果让同一个 Agent 又写又改，很可能把没问题的部分也改掉——没有"只改这里"的约束。

## 三个角色的边界

**Writer** 负责起草结构化 Markdown。主输入是结构化需求摘要，Skill 规范通过 `_build_prd_from_summary_prompt()` 注入，澄清对话如果有的话会单独作为一条 HumanMessage 传入。temperature 设为 0.2，让输出有一定创意但不失控。

**Reviewer** 只做一件事：审。它不流式输出，而是等待完整响应，把结果解析为结构化 JSON，包含三个字段——`passed`（是否通过）、`summary`（一句话总结）、`issues`（问题列表，每条带 `severity`、`section`、`problem`、`suggestion`）。temperature 设为 0，让评审结论尽量确定。

**Rewriter** 是 Writer 的第二种工作模式，走同一条编排流程。改写时会重建完整上下文：Skill 规范和结构化摘要重新注入，改写指令追加在最后。这样 Rewriter 既知道"改哪里"（review JSON），也知道"改成什么样"（Skill 与摘要约束），不是只凭草稿和 review JSON 盲改。

![Writer、Reviewer、Rewriter 的三角职责分离](https://pic.niumianoffer.com/images/fs/02-01-agent-triangle.png)

## 编排逻辑

三个角色的协作由 `generate_prd_from_summary_stream()` 编排，输入是结构化需求摘要（澄清对话 summary 的产物）：

```python
# harnessprd/backend/services/document_service.py

async def generate_prd_from_summary_stream(
    self,
    requirements_summary: Dict[str, Any],    # 结构化需求摘要（来自澄清对话）
    conversation_messages: List[Dict[str, str]] | None = None,
) -> AsyncGenerator[Dict, None]:
    # 把澄清对话格式化为文本，同时构建 Reviewer 的额外上下文
    clarification_context = _format_conversation_context(conversation_messages or [])
    review_context = ...  # 结构化摘要 + 澄清对话的合并文本

    # 通知前端进入写作阶段
    yield {"type": "phase", "phase": "writer_started"}
    # Writer：SystemMessage + 澄清对话（可选）+ 结构化摘要 prompt（含 Skill 规范）
    draft_v1 = ""
    async for chunk in llm.astream(writer_messages):
        if chunk.content:
            draft_v1 += chunk.content
            yield {"type": "text_delta", "phase": "writer", "content": chunk.content}

    # 通知前端进入审查阶段
    yield {"type": "phase", "phase": "review_started"}
    # Reviewer 非流式，等待完整 JSON 结果；review_context 把结构化摘要一并传入
    review_result = await self.prd_reviewer.review(
        conversation_messages or [],
        draft_v1,
        review_context=review_context,
    )
    yield {"type": "review", "phase": "review", "content": review_result}

    if review_result.get("passed", False):
        # 审查通过，直接结束，不触发 Rewriter
        yield {"type": "done", "final_prd": draft_v1, "review": review_result, "revision_applied": False}
        return

    # 通知前端进入修订阶段
    yield {"type": "phase", "phase": "rewrite_started"}
    # Rewriter：重建完整上下文——Skill 规范和结构化摘要同样注入，改写指令追加在最后
    # rewrite_messages = [SystemMessage, HumanMessage(澄清对话), HumanMessage(摘要 prompt), HumanMessage(改写指令)]
    draft_v2 = ""
    async for chunk in rewrite_llm.astream(rewrite_messages):
        if chunk.content:
            draft_v2 += chunk.content
            yield {"type": "text_delta", "phase": "rewrite", "content": chunk.content}

    # revision_applied=True 表示这次生成经过了 Rewriter 修订
    yield {"type": "done", "final_prd": draft_v2, "review": review_result, "revision_applied": True}
```

整条流程可以用这张图描述：

```
结构化需求摘要 + 澄清对话
    │
    ▼
┌──────────────┐
│  Writer      │  llm.astream()    temperature=0.2
│  起草 PRD    │  (SystemMsg + 摘要 prompt + Skill 规范)
└──────┬───────┘
       │ draft_v1
       ▼
┌──────────────┐
│  Reviewer    │  review()         temperature=0
│  审查草稿    │  返回结构化 JSON
└──────┬───────┘
       │
   passed?
  ┌────┴────┐
  │ True    │ False
  ▼         ▼
直接返回  ┌──────────────┐
draft_v1  │  Rewriter    │  rewrite_llm.astream()  temperature=0.2
          │  针对意见改写 │  (含 Skill 规范 + 摘要 prompt + 改写指令)
          └──────┬───────┘
                 │ draft_v2
                 ▼
              返回 draft_v2
```

Reviewer 通过后不触发 Rewriter，避免无谓的额外调用。最终的 `done` 事件会带上 `revision_applied` 标记，Job 层根据这个字段在 run summary 里记录本次生成是否经过修订。

![PRD 三阶段编排流程](https://pic.niumianoffer.com/images/fs/02-01-prd-orchestration.png)

## 三角设计的工程价值

三个角色各自独立，带来的最直接好处是**可以分开调优**。想调整审查维度或 JSON 格式，只改 `PRD_REVIEWER_SYSTEM_PROMPT`；想调整文档风格，改 Skill 规范文件或 `_build_prd_from_summary_prompt()` 的拼装；想调整改写行为，改 `PRD_REWRITE_PROMPT_TEMPLATE`。三者不挤在一条 prompt 里，改一处不会意外影响另一处。

每个阶段切换时发出 `phase` 事件，前端可以展示"写作中 → 审查中 → 修订中"的实时进度。用户知道当前在哪一步，不是对着一个没有反馈的等待框在猜。

如果草稿质量已经足够，Reviewer 直接放行，Rewriter 不会被触发。这不只是节省了一次 LLM 调用，对用户来说是更快拿到结果；对系统来说，减少了一次可能出错的额外环节。三角结构表面上步骤更多，但它只在真正需要时才走完整个三角。
