# 后端 Generation Job 实现提示词

点击此处可复制本篇提示词

Generation Job 的核心，是把「生成 PRD / 接口文档 / 提示词」从**绑在浏览器 SSE 连接上的 generator**，改成**后台独立任务**：任务状态存 SQLite，执行在后台协程里跑，进度通过内存广播推给订阅中的客户端。客户端断开 SSE 后，后台 runner 仍继续执行直至完成或失败。

`document_service` 里现有的 async generator **原样复用**，runner 负责写库、发事件；前端通过 `/jobs/{id}/stream` 订阅。**断开 SSE 连接不 cancel 后台任务**。

## 使用场景

这份提示词用于在 harnessprd 项目 `backend/` 实现 Generation Job（**不改 `frontend/`**）。

**前置条件**：结构化流程、`/api/session` 持久化、`document_service.generate_*_stream` 与 SSE 事件格式（`phase` / `text_delta` / `review` / `done` / `run_summary`）已存在。Job stream 结束时同样 emit `run_summary`。

**本次不做：**

- Celery、Redis、独立 Worker 进程（单机 asyncio 够用）
- 文档优化 Job（见 03 篇）
- 改造澄清 `start-stream` / `continue-stream`（澄清仍是短 SSE 直连）
- 删除旧 `POST /conversation/generate-*-stream`（可保留兼容，标记 deprecated）

### 一、功能目标

- 新增 `generation_jobs` SQLite 表（存任务状态与草稿）
- 新增 `job_service`（增删改查）、`job_bus`（同进程事件广播）、`job_runner`（跑三种文档生成）
- 新增 `api/jobs.py`：`POST /jobs`（创建）、`GET /jobs/{id}`（查快照）、`GET /jobs/{id}/stream`（订阅 SSE）
- Runner 每收到 chunk **节流写库**（建议 500ms）；phase 变更 **立即写库**
- Job 完成 / 失败时 **同步 Session**（`activeJobId`、文档正文、`viewState` 等）
- 修正 `downgrade_generating_view_state`：有 running Job 时不误退回澄清页
- 同一 `session_id` + 同一类 `artifact` 同时只允许一个 `running` Job

### 二、代码结构

```
backend/
  db/
    database.py                 # 改造：CREATE generation_jobs
  services/
    job_service.py              # 新建：Job CRUD
    job_bus.py                  # 新建：subscribe / publish / unsubscribe
    job_runner.py               # 新建：run_prd_job / run_api_docs_job / run_prompts_job
    session_service.py          # 改造：downgrade + sync_session_from_job 辅助
    document_service.py         # 不改造 pipeline，runner 调用现有 generator
  api/
    jobs.py                     # 新建：Job 路由
    schemas.py                  # 改造：CreateJobRequest 等
  main.py                       # 改造：include jobs router
```

### 三、generation_jobs 表

在 `database.py` 的 `init_db()` 中追加：

```sql
CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    artifact TEXT NOT NULL,           -- prd | api-docs | prompts
    status TEXT NOT NULL,             -- pending | running | completed | failed | cancelled
    phase TEXT NOT NULL,              -- writing | reviewing | rewriting | generating | done
    payload_json TEXT NOT NULL,       -- 创建时输入（summary、messages、prd_content 等）
    draft_content TEXT DEFAULT '',
    previous_draft TEXT DEFAULT '',   -- PRD rewrite 前 v1
    review_json TEXT,
    result_json TEXT,                 -- done 时 final 结果
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_session ON generation_jobs(session_id);
```

**字段说明：**

| 字段 | 用途 |
|------|------|
| `draft_content` | **权威草稿**，刷新后 snapshot 从这里读；chunk 节流 UPDATE |
| `previous_draft` | PRD 进入改写阶段前，保存 v1 初稿 |
| `review_json` | 审查 Agent 的结构化结论 |
| `result_json` | `done` 时序列化终稿，含 `final_prd` 等 |
| `payload_json` | 创建 Job 时的输入参数，便于排查；running 中一般不重跑 |

### 四、artifact 与 phase 映射

**artifact（用户点的是哪种生成）：**

| 值 | runner | 复用 generator |
|----|--------|----------------|
| `prd` | `run_prd_job` | `generate_prd_from_summary_stream` |
| `api-docs` | `run_api_docs_job` | `generate_api_docs_stream` |
| `prompts` | `run_prompts_job` | `generate_prompts_stream` |

**PRD Job 内 phase（任务当前在哪个阶段）：**

后端 SSE 的 `phase` 事件会映射成 Job 表的 `phase` 字段：

| SSE 事件 phase | job.phase（存库） |
|----------------|-------------------|
| `writer_started` | `writing`（起草中） |
| `review_started` | `reviewing`（审查中） |
| `rewrite_started` | `rewriting`（改写中；同时 `previous_draft = draft_content`，`draft_content` 随 v2 chunk 更新） |
| `done` | `done` |

接口文档 / 提示词：创建时 `phase=generating`，有 `text_delta` 期间保持，完成时 `done`。

### 五、job_service

```python
def create_job(session_id: str, artifact: str, payload: dict) -> str: ...
def get_job(job_id: str) -> dict: ...
def get_running_job(session_id: str, artifact: str) -> dict | None: ...
def update_job(job_id: str, **fields) -> None: ...
def append_draft(job_id: str, chunk: str) -> str: ...  # 返回新 draft_content
```

**create_job 规则：**

- 若同 session + artifact 已有 `status=running` → 返回 **409**（推荐，防用户连点两次生成）
- 新建时 `status=pending`，runner 启动后立即置 `running`

### 六、job_bus（同进程广播）

作用：后台 runner 产生事件，推给**当前正在订阅**的 SSE 连接。

```python
_subscribers: dict[str, list[asyncio.Queue]] = {}

def subscribe(job_id: str) -> asyncio.Queue: ...
def unsubscribe(job_id: str, queue: asyncio.Queue) -> None: ...
async def publish(job_id: str, event: dict) -> None: ...
```

- SSE 连接断开时只 `unsubscribe`，**不**停止 runner
- 单进程部署足够；多实例以后换 Redis pub/sub

### 七、job_runner

**启动方式**（在 `POST /jobs` 内）：

```python
asyncio.create_task(run_prd_job(job_id))
```

**run_prd_job 伪代码：**

```python
async def run_prd_job(job_id: str):
    job = get_job(job_id)
    payload = json.loads(job["payload_json"])
    update_job(job_id, status="running", phase="writing")
    sync_session_active_job(job["session_id"], job_id, artifact="prd")

    draft_buffer = ""
    last_persist_at = 0.0

    try:
        async for event in document_service.generate_prd_from_summary_stream(
            payload["requirements_summary"],
            payload.get("conversation_messages"),
        ):
            et = event.get("type")

            if et == "text_delta":
                draft_buffer += event["content"]
                draft_buffer = maybe_throttled_persist_draft(job_id, draft_buffer, last_persist_at)

            elif et == "phase":
                if event["phase"] == "rewrite_started":
                    update_job(job_id, phase="rewriting", previous_draft=job["draft_content"], draft_content="")
                    draft_buffer = ""
                else:
                    update_job(job_id, phase=map_phase(event["phase"]))
                flush_draft(job_id, draft_buffer)

            elif et == "review":
                update_job(job_id, review_json=json.dumps(event["content"], ensure_ascii=False))

            elif et == "done":
                update_job(job_id, status="completed", phase="done", result_json=..., draft_content=event["final_prd"])
                sync_session_on_job_complete(job["session_id"], job_id, event)

            await publish(job_id, event)

        # generator 正常结束但未 yield done 的兜底
    except Exception as e:
        update_job(job_id, status="failed", error=str(e))
        await publish(job_id, {"type": "error", "message": str(e)})
        sync_session_on_job_failed(...)
```

**run_api_docs_job / run_prompts_job**：结构相同，无 review/rewrite phase，payload 含 `prd_content`（prompts 另含 `api_docs_content`）。

**节流写库**：不要每个 token 一次事务；内存累加，每 500ms 或 phase 变更时 `UPDATE draft_content`。

**RunMetrics**：在 runner 内包一层 `RunMetricsCollector`（与 `conversation.py` 一致），stream 结束前 publish `run_summary`。

### 八、API 路由

**POST `/api/jobs`** — 用户点「生成」，创建任务

Request：

```json
{
  "session_id": "uuid",
  "artifact": "prd",
  "payload": {
    "requirements_summary": { },
    "conversation_messages": [ ]
  }
}
```

`api-docs` payload：`prd_content`, `conversation_messages`  
`prompts` payload：`prd_content`, `api_docs_content`, `conversation_messages`

Response：`{ "job_id": "..." }`（用于后续查询与订阅 stream）

**GET `/api/jobs/{job_id}`** — 查任务快照（刷新时先调，页面不空白）

```json
{
  "id": "...",
  "session_id": "...",
  "artifact": "prd",
  "status": "running",
  "phase": "writing",
  "draft_content": "...",
  "review": { },
  "result": null,
  "error": null
}
```

**GET `/api/jobs/{job_id}/stream`**（SSE，**GET** 无 body）— 订阅进度

流程：

1. 读 DB，发 **`snapshot`** 事件（见第十节，已有全文立刻给前端）
2. 若 `status` 已是 `completed` / `failed`：发 `done` / `error` + `run_summary` + `[DONE]`，结束
3. 若 `running`：注册 `job_bus` 队列，转发后续 `publish` 事件直至 `done` / `error`
4. `finally`：`unsubscribe`

Headers 同现有：`Cache-Control: no-cache`，`X-Accel-Buffering: no`。

### 九、Session 同步

Job 表是草稿权威来源；Session 存「用户做到哪、当前任务 ID」，在关键节点同步即可。

在 `session_service.py` 增加辅助函数：

**创建 Job 时**（`session_data` patch）：

```json
{
  "activeJobId": "<job_id>",
  "viewState": "generating-prd"
}
```

artifact 对应：`generating-api-docs`、`generating-prompts`。

**Job 完成时**：

```json
{
  "activeJobId": null,
  "viewState": "review-prd",
  "prdContent": "<final>",
  "prdReviewResult": { }
}
```

**Job 失败时**：`activeJobId=null`，`viewState=review-*`，保留 `draft_content` 到对应 `*Content` 字段。

**节流同步**：不必每个 chunk 写 Session；phase 变更、完成、失败时同步即可。前端 snapshot 主要来自 Job API。

### 十、SSE 事件协议（前端契约）

与现有 `conversation` SSE **兼容扩展**，新增 `snapshot`：

**snapshot**（stream 连接建立时**第一条**，重连时用）

```json
{
  "type": "snapshot",
  "status": "running",
  "phase": "writing",
  "artifact": "prd",
  "draft_content": "已有 Markdown 全文",
  "review": null
}
```

**其余与现有一致：**

| type | 说明 |
|------|------|
| `phase` | `{ "phase": "writer_started" \| "review_started" \| "rewrite_started" }` |
| `text_delta` | `{ "content": "..." }` 增量文字 |
| `review` | `{ "content": { passed, issues, ... } }` 审查结论 |
| `done` | PRD：`final_prd`, `review`, `revision_applied` |
| `error` | `{ "message": "...", "request_id": "..." }` |
| `run_summary` | 与 `conversation.py` 一致（耗时、Token 统计等） |
| `[DONE]` | 流结束 |

### 十一、downgrade_generating_view_state

加载 Session 时，若误判会把「正在生成」降级成澄清页，导致无法重连。改造规则：

```python
# 若 session_data 含 activeJobId，且 DB 中该 job status==running
#   → 保持 generating-*（按 artifact 映射），禁止 _fallback_before_prd 回澄清

# 若无 activeJobId 但 viewState 为 generating-*：
#   → 落到对应 review-*（有 draft_content 则 Session 字段已有正文）
#   → 禁止回 chatting
```

**关键：** 有 running Job 时**不要**降级成 review 或澄清，否则前端无法进入重连流程。

### 十二、服务重启（V1 约定）

单进程 `asyncio.create_task` 在服务重启后丢失。V1 行为：

- 启动时扫描 `status=running` 的 Job → 置 `failed`，`error="服务重启，任务中断"`
- Session 保留最后 `draft_content`（用户可手动编辑或重新生成）

不在 V1 做自动续跑。

### 十三、验收标准

1. `POST /api/jobs` 可创建 `prd` / `api-docs` / `prompts` 三种 Job，返回 `job_id`
2. `GET /api/jobs/{id}/stream` 首条为 `snapshot`，运行中有 `text_delta` / `phase` / `review`（PRD），结束有 `done` + `run_summary` + `[DONE]`
3. SSE 订阅者断开连接后，Job 仍 `running` 直至完成（`unsubscribe` 不 cancel runner）
4. 同 `session_id` + artifact 重复创建 running Job 返回 409
5. Job 完成 / 失败时 Session 同步 `activeJobId`、`viewState`、对应 `*Content` 字段
6. `downgrade_generating_view_state`：有 running Job 时保持 `generating-*`，不回澄清
