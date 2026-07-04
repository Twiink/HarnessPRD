# 刷新重连：全量快照与增量 chunk

Generation Job 让生成过程在服务端持续运行，不受浏览器连接影响。但仅凭这一点，还解决不了刷新体验的问题：用户刷新后，前端要怎么恢复到中断前的状态？已有的草稿怎么展示？Stepper 停在哪一步？这些问题由刷新重连机制来回答。

## 刷新后发生什么

用户刷新页面，前端先检查 Session 里有没有记录的任务标识。有的话，说明有进行中（或刚完成）的生成任务，走重连流程，而不是重新初始化。

重连是一个两步过程，两次恢复叠加在一起：

**第一步，预加载当前状态**：先调一次查询接口，拿到任务的快照——运行状态、进行到哪一步、已有草稿、审查结果。这份数据立刻填进页面，用户不会看到空白。根据任务状态分三条路：

| 任务状态 | 重连后的行为 |
|---------|------------|
| 进行中 | 从查询结果恢复初始 UI，再订阅事件流接收后续内容 |
| 已完成 | 直接展示最终结果，切到展示页，不订阅事件流 |
| 已失败 | 展示已有草稿和错误提示，切到展示页 |

已完成和已失败处理最简单，直接用查询结果恢复页面即可，不需要订阅任何事件流。

**第二步，snapshot 首包**：对于还在运行的任务，前端发起事件流订阅，后端推出的第一包就是 `snapshot` 事件，携带连上那一刻的全量状态。这次数据覆盖第一步的查询结果，是「截至重连瞬间」的精确快照，之后的新内容从这里继续追加。

两次恢复的分工很清楚：第一步解决"页面不空白"，snapshot 解决"状态精确"。

![刷新重连的两步恢复机制](https://pic.niumianoffer.com/images/fs/05-refresh-reconnect-recovery.png)

**并发保护**：前端有两道防线，防止同一个任务被重复订阅。一旦重连流程启动就设一个标志位，同一 session 下不会再次触发；订阅发起时也会检查是否已有一个在进行中，有的话直接跳过。

## snapshot 事件：核心协议

`snapshot` 不只在刷新重连时出现，它是**每次订阅流的第一包**。无论是首次生成刚刚发起连接，还是刷新后重连，后端收到 `GET /api/jobs/{id}/stream` 请求，第一件事都是把当前 Job 状态序列化成一条 `snapshot` 推出去：

```json
{
  "type": "snapshot",
  "status": "running",
  "phase": "writing",
  "artifact": "prd",
  "draft_content": "## 1. 项目背景\n\n本项目旨在……（已生成的全文）",
  "review": null
}
```

这条 `snapshot` 是整个重连机制最重要的一条消息。它携带的是 Job 在数据库里的当前视图：`draft_content`、`phase`、`review` 等。前端收到后，立刻把 `draft_content` 整段填进页面，用户看到的是截至重连瞬间已持久化的内容，而不是空白或局部残缺。

PRD 进入 `rewriting` 阶段时有一点例外：Runner 会把 Writer 的 v1 存进 `previous_draft` 并清空 `draft_content` 再收 Rewriter 输出，而 snapshot API 目前只暴露 `draft_content`。因此在修订阶段重连，页面展示的是 **v2 已生成的部分**，v1 全文不在 snapshot 里——多数时间在 `writing` / `reviewing` 刷新，上述逻辑完全适用。

`snapshot` 之后的消息，是后台协程实时推出来的 live chunk。前端正常追加即可，就像连接从未断开过一样。

## 为什么不能重新假流式

收到 `snapshot` 后，有一种直觉上看似自然的做法：把已有草稿从头用打字机效果重新播放一遍。这样看起来好像有连续感。

这个做法是错的，原因有两个。

第一，速度会对不上。打字机重播的速度是人为设定的，和原来生成时 LLM 的实际速度不一样。用户会感知到这段内容和后续实时内容之间的切换，而不是流畅的连续体验。

第二，时机会错乱。重播需要一段时间，重播进行中，后台的新内容可能已经开始进来，两个流同时操作同一个文本区域，结果是错乱。

正确的做法是：`snapshot` 内容**立刻整段展示**，不打字机。后续的新内容才从当前位置继续追加，保持打字机效果。切换点就在 snapshot 和第一条新 chunk 之间。

![snapshot 与 live chunk 的正确拼接方式](https://pic.niumianoffer.com/images/fs/06-snapshot-live-chunk.png)

## 前端的状态恢复

收到 `snapshot` 之后，前端还需要恢复 UI 状态，不只是填充文字内容。

当前处于哪个阶段决定进度条显示什么步骤。起草中让「起草」步骤显示进行中；审查中让「审查」步骤显示进行中并附带提示文案；修订中类似。这个恢复逻辑直接写在收到 snapshot 的回调里，和正常生成时的状态更新共用同一套处理——没有单独的"恢复函数"，两条路走同一个入口。`syncSnapshotPhase` 负责把阶段格式转换后驱动进度条：

```typescript
// harnessprd/frontend/src/hooks/useGenerationJob.ts

// 把 Job phase（"writing"）转成 SSE phase（"writer_started"），驱动 Stepper
const syncSnapshotPhase = (phase: JobPhase) => {
  if (!isPrdGenerate) return;
  const ssePhase = jobPhaseToSsePhase(phase);
  if (ssePhase) {
    prdHandlers?.onPhase?.(ssePhase);
  }
};

onSnapshot: (snap) => {
  // 草稿内容 draft_content：用已有全文直接覆盖，不触发打字机，整段立刻展示
  accumulated = snap.draft_content || '';
  setContentForArtifact(contentArtifact, accumulated, setContent);
  setStreamingContent('');
  if (isPrdGenerate) {
    // 直接更新 Stepper 步骤状态
    if (snap.phase === 'writing') setPrdGenerationStage('writing');
    if (snap.phase === 'reviewing') setPrdGenerationStage('reviewing');
    if (snap.phase === 'rewriting') setPrdGenerationStage('rewriting');
    // 同步通知 obs handler，驱动可观测层
    syncSnapshotPhase(snap.phase);
  } else if (isChunkGenerate && snap.phase === 'reviewing') {
    chunkHandlers?.onPhase?.('review_started');
  }
  // 审查结果 review：若已完成则恢复审查结论
  if (snap.review) setPrdReviewResult(snap.review);
},
```

审查结果同样在这里恢复。snapshot 里的 `review` 字段非空，说明审查阶段已经完成，直接把 review 数据填进页面，进度条显示对应的审查结论。

这些恢复操作集中在一个 hook 里处理，不散落在各处。

## 连接断开不取消任务

SSE 订阅断开时，`job_bus` 只做 unsubscribe，不取消后台协程：

```python
# harnessprd/backend/api/jobs.py

async def generate():
    # 订阅此 Job 的内存事件队列
    queue = subscribe(job_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300.0)
            except asyncio.TimeoutError:
                # 超时后检查 Job 是否已结束，若未结束则继续等待
                refreshed = get_job(job_id)
                if refreshed["status"] in ("completed", "failed"):
                    break
                continue

            yield _sse_line(event)
            # run_summary 或 error 意味着流程已结束，退出循环
            if event.get("type") == "error":
                break
            if event.get("type") == "run_summary":
                break
    finally:
        # 只从队列退订，不 cancel 后台协程，Job 继续运行
        unsubscribe(job_id, queue)
```

这是整个刷新重连机制得以成立的前提条件。如果 unsubscribe 同时取消了协程，刷新就意味着任务终止，重连只能拿到已有草稿，后续不会有新内容推进来。

## 三种场景汇总

| 场景 | 内容展示 | 打字机 |
|------|---------|--------|
| writing 阶段刷新 | snapshot 全文立刻显示，后续新内容追加 | 仅新内容 |
| reviewing 阶段刷新 | 全文静态展示，进度条显示审查提示 | 无 |
| rewriting 阶段刷新 | 展示 v2 已生成部分（v1 在 `previous_draft`，snapshot 未暴露） | 仅新内容 |
| 完成后刷新 | 最终正文静态展示 | 无 |
| 失败后刷新 | 保留已有草稿，显示错误提示 | 无 |

snapshot 机制让每次刷新都变成一次「断点续看」，而不是重新开始。这是 Generation Job 带来的直接用户体验收益。
