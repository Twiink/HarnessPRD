# 00 - 为什么要做生成 Job 与刷新重连

v2 已经跑通 PRD、接口文档、提示词三条生成链路。Session 能持久化，Stepper 能告诉用户当前在「起草」还是「审查」，SSE 也能把正文一行行推出来。

但生成往往要几十秒，甚至更长。用户刷新、关 tab、网络闪断，都很常见。真正伤体验的是：**生成明明在进行，一刷新，连接断了，后台也跟着停——刚才流出来的 PRD 可能只剩一半，页面还可能跳回澄清对话。**

用户的第一反应是：「是不是白做了？」

## 根因：生成绑在浏览器连接上

当前架构里，一次生成 ≈ 一条 SSE 长连接：

```
浏览器 ←── 实时 chunk ──► FastAPI ──► LLM
         刷新 = 连接断 = 生成停
```

Session 保存的是快照，debounce 约 1 秒才写库。流式 chunk 主要在内存里，刷新时后端还会把 `generating-*` **降级**成 review 或澄清——有草稿还好，没及时落库就像从没生成过。

要同时满足 **刷新不丢已有内容** 和 **生成在后台继续跑完**，只能让 **生成与浏览器连接解耦**。

![旧架构中生成绑定浏览器 SSE 连接](https://pic.niumianoffer.com/images/fs/opt2-00-sse-bound-generation.png)

## 哪些阶段受影响

问题集中在三类 **`generating-*` 页面**：

| 流程 | 内部步骤 | 刷新时的问题 |
|------|----------|--------------|
| PRD | Writer → Review → Rewrite | 任一步刷新都可能丢进度、跳页 |
| 接口文档 | RAG + 单段流式 | 草稿未落库则回退 |
| 提示词 | 单段流式 | 同上 |

澄清对话仍是 SSE 直连。文档优化改为 Job 后，刷新可重连，已优化内容不丢失。

## 采用什么方案

我们思考过三种方向，最后选第三种。

### 方案一：假流式

后端先静默跑完 Write → Review → Rewrite，全文就绪后，前端再对**已经生成好的正文**逐字做「打字机」播放。

问题是：真正等 LLM 的那几分钟，用户只能看 loading，比现在的真流式更闷——PRD 多阶段动辄一两分钟，期间完全没有逐字反馈。更关键的是，**在后端还没跑完之前刷新，连接照样断、生成照样停**，和今天一样。假流式只能改善「全文已到手、前端假播那一段」的观感，**解决不了「生成进行中刷新」这个核心痛点**。

### 方案二：流式续传（Session 落库 + 继续生成）

思路是流式过程中把草稿多写进 Session，刷新后调「继续生成」：writing 阶段补全半成品，reviewing 重跑审查，rewriting 接着改。

这条路走不通。**LLM 无状态，做不到 token 级续传**；所谓补写，本质是让模型根据 partial 再生成一版，不是接着上一个 token 写。前端若像现在一样清空再流式出字，**视觉上就是重新生成**；若不清空，补全输出整篇新稿，也会和屏幕上的旧稿对不上。而且生成仍绑在这一次 HTTP 请求上，**刷新后后台不会继续跑**，只是事后另开一次 LLM 调用，和「进度不丢、任务还在进行」不是一回事。

### 方案三：异步任务（Generation Job）——采用

把「一次生成」做成 Job：**后台执行与浏览器连接解耦**。用户点生成 → 创建 Job、立刻返回 `jobId`；Writer / Review / Rewrite 在服务端协程里顺序跑，与前端在不在线无关。前端通过 SSE 订阅 Job 事件；刷新后用同一 `jobId` 重连——先发 **snapshot**（已有全文立刻展示），再收后续 **live chunk**（仅新字打字机）。

为了让方案轻量、不引入 Celery + Redis 和独立 Worker 进程，具体采用：

- **SQLite `generation_jobs` 表**：存 status、phase、draft_content 等，刷新可恢复
- **同进程 `asyncio.create_task`**：在现有 FastAPI 里后台跑，复用 `document_service` 的 generator
- **内存事件广播（job_bus）**：把 chunk / phase 推给当前 SSE 订阅者；连接断开只 unsubscribe，**不 cancel 任务**
- **SSE 重连**：`GET /jobs/{id}/stream`，与现有事件格式（`phase`、`text_delta`、`review`、`done`）兼容

```
点「生成 PRD」
  → POST /api/jobs（创建 Job，立刻返回 jobId）
  → 后台协程跑 Writer / Review / Rewrite（与浏览器无关）
  → GET /api/jobs/{id}/stream（SSE：snapshot + 实时事件）
刷新
  → loadSession 拿到 activeJobId
  → 重连 stream：已有全文立刻展示，后续 chunk 继续打字机
```

![Generation Job 解耦与刷新重连流程](https://pic.niumianoffer.com/images/fs/opt2-00-generation-job-reconnect.png)

单 FastAPI 进程即可部署。以后若要多实例或排队，可以把执行层换成 Celery Worker，Job 表与 API 形状可以保持不变。

## Job 怎么划分

按 **用户点的一次按钮** 建 Job，不按 pipeline 每一步拆：

| 用户操作 | Job |
|----------|-----|
| 生成 PRD | 1 个 Job（内含 writing / reviewing / rewriting） |
| 生成接口文档 | 1 个 Job |
| 生成提示词 | 1 个 Job |
| 文档优化 | 1 个 optimize Job（单段流式，保持 review 页） |

## 刷新后的体验

| Job 状态 | 页面 | 正文展示 |
|----------|------|----------|
| `running` | `generating-*` | 已有内容**立刻整段显示**；重连后的新 chunk 才打字机 |
| `completed` | `review-*` | 静态全文，**无打字机** |
| `failed` | `review-*` | 保留 partial + 错误提示 |

Review 阶段本来就没有新字，Stepper 转圈 + hint，与现在一致。

## 做了之后有什么优势

**对用户**

- 生成中刷新：进度不丢，后台继续跑，回来能接上
- 已完成再刷新：正常审阅页，和今天一样
- 不再因为刷新整段跳回澄清

**对工程**

- 复用现有 `document_service` 流式 generator，不改 LLM pipeline
- 单 FastAPI 进程即可，不新增 Redis / Worker
- Job 模型以后可平滑升级到 Celery（API 形状可不变）
- SSE 事件格式与现有 conversation 流兼容（含 `phase`、`run_summary`）
