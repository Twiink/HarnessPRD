# 链路边界：澄清 SSE 与生成 Job 化

harnessprd 有两类截然不同的后端任务：澄清对话和文档生成。前者用 SSE 长连接直推，后者改成了 Generation Job。这个区别不是偶然的，而是根据两类任务的特点刻意划定的边界。理解这条边界，是理解整个 v2 架构的起点。

## SSE 是什么，适合什么

SSE（Server-Sent Events）是一种 HTTP 长连接协议。服务端建立连接后，可以持续向客户端推送事件；客户端断开连接，推送就停止了。它适合实时性要求高、但连接生命周期与任务生命周期一致的场景。

澄清对话完全符合这个特点。用户问一句，LLM 回一句，每轮对话的流式输出跟着当前连接走。用户关掉页面，对话自然结束；下次打开，重新发起就好。这轮对话和上一轮之间没有继续的必要，也没有中途抢救的价值。

所以澄清对话保留了 SSE 直连。后端把流式 LLM 输出包装成 `StreamingResponse`，以 `text/event-stream` 格式推给前端：

```python
# harnessprd/backend/api/conversation.py

@router.post("/start-stream")
async def start_conversation_stream(request: StartConversationRequest):
    gen = _make_handwritten_sse_generator(
        conversation_service.start_conversation_stream(
            request.initial_input, request.form_data, request.system_prompt_override
        ),
        run_type="chat_start",
    )
    # 以 text/event-stream 格式返回，连接断开后服务端停止推流
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)
```

前端不用原生 `EventSource`，因为它只支持 GET，而是用 `fetch` + `ReadableStream` 接收，逐行解析 `data: {...}` 格式的 SSE 事件：

```typescript
// harnessprd/frontend/src/services/api.ts

// 底层流式读取工具：POST 发起请求，逐行解析 SSE 事件后触发回调
async function readStream(url, body, onChunk, handlers) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const reader = response.body!.getReader();
  // 解码字节流 → 按行切割 → 解析 JSON → 触发 onChunk 或 handlers 回调
  // ...
}

// 开始澄清对话：封装为语义化接口，内部调 readStream
async startConversationStream(initialInput, formData, systemPromptOverride, onChunk, handlers) {
  return readStream(
    '/api/conversation/start-stream',
    { initial_input: initialInput, form_data: formData },
    onChunk,
    handlers,
  );
}
```

## 生成任务为什么不能这样做

PRD、接口文档、提示词套件的生成是另一种情况。

以 PRD 为例，后端要依次完成三步：Writer 起草、Reviewer 审查、Rewriter 修订。每步都是独立的 LLM 调用，合计往往需要一两分钟。

问题在于，这一两分钟里，**浏览器随时可能断开**。网络抖动、用户手滑刷新、切换 Tab 太久被系统休眠——这些都是真实用户的真实操作。如果生成绑在 SSE 连接上，连接一断，后台的协程就跟着取消，已经生成的草稿可能只存在内存里，没来得及写入 `generation_jobs` 表就消失了。

用户重新打开页面，看到的要么是空白，要么是半截内容。Session 里残留着生成中的视图状态，但没有对应进行中的任务，系统不知道该展示什么，有时会把用户"降级"回澄清对话，就像从没开始过一样。

这是一个根本性的问题：**生成任务的生命周期比连接的生命周期长得多**。强行把两者绑在一起，一旦连接断开，就意味着任务失败。

![SSE 与 Generation Job 的生命周期边界](https://pic.niumianoffer.com/images/fs/01-sse-vs-generation-job.png)

## Job 化的核心思路

Generation Job 把这两个生命周期彻底拆开。

用户点击生成，前端 `POST /api/jobs` 创建一个 Job，后端立刻返回任务标识 `job_id`，不等生成完成。实际的 Writer / Reviewer / Rewriter 调用由 `asyncio.create_task` 在后台启动，在同一个 FastAPI 进程里独立运行。

前端拿到 `job_id` 后，再发 `GET /api/jobs/{id}/stream` 订阅事件流。这是两个独立的 HTTP 请求——创建 Job 和订阅 Job 流。生成协程对前端有没有连上来一无所知，它只管往内存事件队列 `job_bus` 里发事件。有订阅者就推出去，没有就丢弃，反正草稿每 500 毫秒节流写一次 `generation_jobs` 表，不会丢失。

```
用户点「生成 PRD」
  ↓
POST /api/jobs  →  后端创建 Job，启动后台协程  →  返回 job_id
  ↓
GET /api/jobs/{id}/stream  →  前端订阅事件流
  ↓
后台协程继续运行（与连接无关）
  ↓
浏览器刷新  →  协程还在跑
  ↓
GET /api/jobs/{id}/stream（同一 job_id 重连）
```

![Generation Job 的创建、订阅与持久化流程](https://pic.niumianoffer.com/images/fs/02-generation-job-flow.png)

## 边界在哪里

这两种模式的分界线，不是「快 vs 慢」，而是**任务是否需要在用户离线时继续存在**。

澄清对话不需要。用户一关页面，这轮对话就结束了。下次打开是新的一轮，不是接着上次继续。

文档生成需要。用户关了页面，不代表他放弃了这次生成。他只是离开了一会儿。任务应该继续，回来的时候应该能看到结果。

| 维度 | 澄清 SSE | 文档生成 Job |
|------|---------|------------|
| 传输方式 | StreamingResponse 直连 | 创建 Job + SSE 订阅（两个请求） |
| 典型时长 | 秒级 | 分钟级 |
| 连接断开 | 生成中止，下次重头开始 | 协程继续运行，重连可恢复 |
| 状态持久化 | 无，内存中即失 | SQLite `generation_jobs` 表，每 500ms 节流写入 |

这个区别决定了两种完全不同的实现路径。理解这条边界，就能理解为什么澄清对话可以保持原样，而文档生成必须 Job 化。
