# Generation Job：状态机与生命周期设计

Generation Job 的本质是一个持久化的异步任务。用户每点一次生成按钮，就创建一个 Job；Job 在后台运行，状态持续写库，前端订阅事件流实时感知进度。这篇文章从状态机、数据模型、执行机制三个角度讲清楚 Job 是怎么设计的。

## 状态机

Job 的状态只有五种：

```
pending  →  running  →  completed
                     →  failed
                     →  cancelled
```

Job 创建时是 `pending`，后台协程启动后立刻推进到 `running`。正常跑完是 `completed`，中途出错是 `failed`，外部取消是 `cancelled`（预留字段，暂未实现主动取消入口）。

每种 artifact（文档类型）还有一套内部 Phase，表示当前执行到哪一步。PRD 的 Phase 最复杂：

| Phase | 含义 |
|-------|------|
| `writing` | Writer Agent 正在起草 |
| `reviewing` | Reviewer Agent 正在审查 |
| `rewriting` | Rewriter Agent 正在修订 |
| `done` | 全流程完成 |

接口文档和提示词的 Phase 比 PRD 少：初始进入 `generating`，有 Reviewer Agent 触发时切换到 `reviewing`，结束时变为 `done`。

状态和 Phase 的区分很重要。状态描述 Job 的生命周期，Phase 描述 Job 内部的进度。一个 `running` 状态的 PRD Job 可能处于 `writing`、`reviewing` 或 `rewriting` 任一 Phase。前端 Stepper 展示的就是 Phase，而不是状态。

![Job 状态机与 Phase 双层进度](https://pic.niumianoffer.com/images/fs/03-job-state-phase.png)

## 数据模型

Job 持久化在 SQLite 的 `generation_jobs` 表里：

```sql
-- harnessprd/backend/db/database.py

CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    -- 文档类型：prd | api-docs | prompts | optimize-prd | optimize-api-docs | optimize-prompts
    artifact TEXT NOT NULL,
    -- 任务生命周期：pending | running | completed | failed | cancelled
    status TEXT NOT NULL,
    -- 执行进度：writing | reviewing | rewriting | generating | done
    phase TEXT NOT NULL,
    -- 创建时的输入参数，JSON 序列化，供 runner 重建上下文
    payload_json TEXT NOT NULL,
    -- 权威草稿，每 500ms 节流写入，刷新重连时 snapshot 的来源
    draft_content TEXT DEFAULT '',
    -- rewrite 开始前保存的 v1 初稿，Writer 成品存此字段
    previous_draft TEXT DEFAULT '',
    -- Review Agent 输出的 JSON 报告，Review 阶段完成后写入
    review_json TEXT,
    -- done 事件的完整内容，含 final_prd、revision_applied 等
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

几个字段值得单独说明：

`draft_content` 是草稿的权威来源。后台协程把每个 text_delta 追加到内存里的 buffer，每 500 毫秒把 buffer 写一次库。刷新重连时，前端从这个字段拿全文快照。

`previous_draft` 只在 Rewriter 阶段有意义。进入 `rewriting` Phase 时，把 `draft_content`（Writer 的成品）存进 `previous_draft`，然后清空 `draft_content` 开始接收 Rewriter 的输出。这样两版内容都有据可查。

`payload_json` 存的是创建 Job 时的输入，包括需求摘要、对话历史等。它的存在主要是为了让 Job 在任何时候都能重建执行上下文，虽然 v1 实现里并不会在 running 时重跑。

## 执行机制

Job 创建后，路由层调用 `schedule_job(job_id, artifact)`。这个函数用 `asyncio.create_task` 把对应的 runner 协程提交给当前事件循环。

`run_prd_job` 不负责编排 Writer / Reviewer / Rewriter，那些步骤都在 `generate_prd_from_summary_stream` 内部完成。runner 只做一件事：消费 generator 抛出的事件，更新 Job 状态与草稿，并转发给 SSE 订阅者。下面片段省略了 review、done 与 Session 同步。

```python
# harnessprd/backend/services/job_runner.py

async def run_prd_job(job_id: str) -> None:
    job = get_job(job_id)
    payload = json.loads(job["payload_json"])
    session_id = job["session_id"]
    # 立即推进状态，前端 Stepper 进入 writing 阶段
    update_job(job_id, status="running", phase="writing")
    # 把任务标识写入 Session，前端刷新后可据此重连
    sync_session_active_job(session_id, job_id, "prd")

    draft = ""
    last_persist = 0.0

    try:
        async for event in document_service.generate_prd_from_summary_stream(
            payload["requirements_summary"],
            payload.get("conversation_messages"),
        ):
            et = event.get("type")

            if et == "text_delta":
                draft += event.get("content") or ""
                # 节流写库：每 500ms 落库一次，避免高频 I/O
                last_persist = await _maybe_persist_draft(job_id, draft, last_persist)

            elif et == "phase":
                phase_name = event.get("phase") or ""
                if phase_name == "rewrite_started":
                    # 进入 rewrite 前，把 Writer 成品存入 previous_draft，清空 draft 接收新内容
                    current = get_job(job_id)
                    update_job(
                        job_id,
                        phase="rewriting",
                        previous_draft=current["draft_content"],
                        draft_content="",
                    )
                    draft = ""
                elif phase_name in PHASE_FROM_EVENT:
                    # writer_started → writing，review_started → reviewing
                    update_job(job_id, phase=PHASE_FROM_EVENT[phase_name])
                # phase 变更时强制落库，确保刷新后 Stepper 能恢复到正确步骤
                last_persist = await _maybe_persist_draft(job_id, draft, last_persist, force=True)

            # 推给所有订阅了该 Job 的 SSE 连接；无订阅者时直接忽略
            await publish(job_id, event)

    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc))
        await publish(job_id, {"type": "error", "message": str(exc)})
```

![Job Runner 执行与持久化机制](https://pic.niumianoffer.com/images/fs/04-job-runner-persistence.png)

几个关键点：

runner 的设计有一个核心约束：内部的任何操作，都要能容忍连接随时断开。`asyncio.create_task` 在任务级别满足这个要求——协程提交给事件循环之后独立运行，不依附于任何 HTTP 连接。路由函数返回 `job_id` 之后，协程继续执行，前端掉线与否和它无关。

事件广播也是同样的容忍姿态。`job_bus.publish` 把事件推给当时所有订阅者；如果没有人在线，直接返回，不报错，协程接着跑。没有丢失内容的风险，因为草稿在持续写库——下次有人重连，从数据库拿全量快照即可。

节流写库（500ms）和即时写库（Phase 变更）的区分，也服务于同一个目标。token 级别的 text_delta 非常密集，每个都写一次库会撑爆 I/O；但 Phase 变更稀少，必须立刻落盘——如果不及时写，服务重启或用户刷新后，Stepper 不知道该停在哪一步，只能从头展示。

## Job 的三段生命周期

一个 Job 的后端执行可以分三段来看：

**开始时**：协程一启动，立即做两件事——把 Job 推进「进行中」，同时通知当前 Session「有一个活跃任务正在跑」，顺带把前端页面切到生成视图（`generating-prd`）。这两步之所以放在最前面，是为了让「刷新重连」成立：用户刷新后，前端从 Session 里找到任务标识 `activeJobId`，就知道该去重连，而不是重新初始化。

**运行中**：两件事同时进行。一是把生成内容持续攒进内存 buffer，每 500ms 落一次数据库（`draft_content` 字段）；二是把每条事件实时推给当前连着的前端。这两件事彼此独立——即使前端断线、没有订阅者，内容也在持续落库，重连后从数据库拿快照即可，不会少内容。

**结束时**（完成或失败），三件事按顺序收尾：

```
├ 先把最终内容写进文档版本库（document_versions 表，current 版本 + metadata）
├ 再更新 Session 状态（清掉活跃任务标记，把页面切回展示视图）
└ 最后在 finally 块里给前端发一条结束信号（run_summary 事件）
```

顺序很重要：前端收到结束信号时，文档数据和 Session 状态已经落好，不存在"前端已经展示完成，但数据库还没写完"的窗口期。

## 冲突保护

同一个 Session 里，同类 artifact 同时只允许一个 running 状态的 Job。创建时系统检查是否已有冲突的 running Job：

```python
# harnessprd/backend/services/job_service.py

def create_job(session_id: str, artifact: str, payload: dict) -> str:
    # 检查同 session 同冲突组是否已有 running Job，防止重复生成
    existing = get_conflicting_running_job(session_id, artifact)
    if existing:
        raise JobConflictError(existing["id"])
    # ...
```

路由层把 `JobConflictError` 转成 HTTP 409，前端可以根据这个错误码决定是提示用户、还是直接接管已有 Job 的事件流。

冲突判断不是简单比 artifact 字符串，而是按冲突组来判。比如 `prd` 和 `optimize-prd` 属于同一组，两者不能同时运行，因为它们都会修改同一份文档内容。

## 服务重启时的行为

`asyncio.create_task` 的任务在进程重启后会全部丢失。v1 的处理方式是：FastAPI 启动时扫描 `status=running` 的 Job，把它们标记为 `failed`，`error` 字段写入「服务重启，任务中断」。这样用户下次打开时，能看到明确的失败提示，而不是一个永远停在 running 状态的 Job。

Session 里会保留最后一次节流写入的 `draft_content`。虽然任务没跑完，已经生成的内容不会消失。
