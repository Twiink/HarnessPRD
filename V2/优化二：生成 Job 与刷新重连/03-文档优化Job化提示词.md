# 文档优化 Job 化提示词

点击此处可复制本篇提示词

文档优化 Job 化的目标，是把 `review-*` 页上的「优化文档」从 `POST optimize-document-stream` 改成与生成链路一致的 **创建 Job + 订阅 stream**：

- **优化过程中刷新**可重连
- **已有优化稿立刻展示**
- **后台任务不因断连而停止**

**实现原则：** 复用已有 `generation_jobs` / `job_bus` / `job_runner` / `useGenerationJob`；`document_service.optimize_document_stream` **不改**；`AppV2` 只把 `handleOptimizeDocument` 改为调 hook 的 `startOptimize`，不堆 stream 细节。

## 使用场景

**前置条件**：`generation_jobs` / `job_bus` / `job_runner`、`POST /api/jobs`、`useGenerationJob` 已存在。

**本次不做：**

- 澄清 `start-stream` / `continue-stream` Job 化
- 文档版本 / revision（版本链另篇）
- 删除旧 `POST /conversation/optimize-document-stream`（可保留，标记 deprecated）
- 优化中展示三阶段 Stepper（优化是单段流，无 PRD 的写/审/改 phase）

---

## 一、功能目标

### 后端

- 新增三种 optimize artifact：`optimize-prd`、`optimize-api-docs`、`optimize-prompts`
- 新增 `run_optimize_*_job`（或统一 `run_optimize_job`），内部调用 `document_service.optimize_document_stream`
- `create_job` 冲突规则：同一 `session_id` 下，**生成类与优化类互斥**（见第三节）
- Job 完成 / 失败时 **同步 Session**：`viewState` **保持当前 review 页**，更新对应 `*Content`
- stream 结束 emit `run_summary`（`run_type` 为 `optimize_document`）

### 前端

- `useGenerationJob` 新增 `startOptimize(docType, content, instruction, context)`
- `handleOptimizeDocument` 改为 `await jobGen.startOptimize(...)`，删除 `optimizeDocumentStream` 调用
- 优化中：`viewState` **不变**（仍在 `review-prd` 等），`isOptimizingDocument=true`，`streamingContent` 打字机
- 刷新重连：有 `activeJobId` 且 Job 为 optimize artifact 时，恢复优化 UI（不是 `generating-*`）
- 可选：`session_data` 增加 `activeJobKind: 'optimize' | 'generate'` 便于重连区分（若仅用 artifact 前缀 `optimize-` 区分则可省略）

---

## 二、artifact 与 payload

| artifact | 对应 doc_type | 更新 Session 字段 | 完成后 viewState |
|----------|---------------|-------------------|------------------|
| `optimize-prd` | `prd` | `prdContent` | `review-prd`（不变） |
| `optimize-api-docs` | `api-docs` | `apiDocsContent` | `review-api-docs` |
| `optimize-prompts` | `prompts` | `promptsContent` | `review-prompts` |

**POST `/api/jobs` payload 示例：**

```json
{
  "session_id": "<SESSION_ID>",
  "artifact": "optimize-prd",
  "payload": {
    "doc_type": "prd",
    "current_content": "<优化前全文>",
    "instruction": "让技术规格更详细",
    "context": "<可选：prd/api 上下文>"
  }
}
```

`optimize-api-docs` / `optimize-prompts` 同理，`doc_type` 与 artifact 对应。

**phase**：优化 Job 全程 `phase=generating`（与接口文档单次生成一致），无 `writing/reviewing/rewriting`。

---

## 三、Job 冲突规则

同一 `session_id` 在以下任一情况存在 `running` Job 时，**拒绝新建**（409）：

| 新建 | 与以下 running 冲突 |
|------|---------------------|
| `prd` | `prd`、`optimize-prd` |
| `optimize-prd` | `prd`、`optimize-prd` |
| `api-docs` | `api-docs`、`optimize-api-docs` |
| `optimize-api-docs` | `api-docs`、`optimize-api-docs` |
| `prompts` | `prompts`、`optimize-prompts` |
| `optimize-prompts` | `prompts`、`optimize-prompts` |

同一 `session_id` 下，同一份文档不能同时存在「整篇生成」与「按指令优化」两个 running Job。实现时用 `CONFLICT_GROUPS` 或按组查表，不要只按 artifact 字符串精确匹配。

---

## 四、后端实现要点

### 1. `job_service.py`

- `VALID_ARTIFACTS` 增加三种 optimize artifact
- `create_job` 实现第三节冲突组逻辑

### 2. `job_runner.py`

新增 `run_optimize_job(job_id)`，结构 **照抄 `_run_chunk_job`**，差异仅在于：

```python
async for event in document_service.optimize_document_stream(
    payload["doc_type"],
    payload["current_content"],
    payload["instruction"],
    payload.get("context") or "",
):
    # chunk / text_delta → 累加 draft，节流写库，publish text_delta
    # done → update_job completed，sync_session_on_optimize_complete
```

- `run_type` 映射：`optimize_document`（与现 `conversation.py` 一致）
- `finally` 中 `_finish_run_summary`

`schedule_job` 增加：

```python
elif artifact.startswith("optimize-"):
    asyncio.create_task(run_optimize_job(job_id))
```

### 3. `session_service.py`

新增 **`sync_session_on_optimize_complete`** / **`sync_session_on_optimize_failed`**（或扩展现有 complete/failed）：

**完成时**（与生成 Job 的关键区别）：

```json
{
  "activeJobId": null,
  "viewState": "review-prd",
  "prdContent": "<优化后全文>"
}
```

- **不要**把 `viewState` 改成 `generating-*`（用户仍在审阅页）
- **不要**清空 `prdReviewResult`（优化 PRD 时保留 session 镜像；侧栏仍以版本 `metadata.review` 为准）
- 失败时：保留 `draft_content` 到对应 content 字段，`activeJobId=null`，仍在 review 页

**创建 optimize Job 时**：

```json
{
  "activeJobId": "<job_id>",
  "viewState": "review-prd"
}
```

`viewState` **保持不变**，仅写入 `activeJobId`。

### 4. `api/jobs.py`

- 无需新路由；`artifact` 校验接受 optimize 类型
- SSE 协议与生成 Job 完全一致：snapshot → text_delta → done → run_summary → `[DONE]`

### 5. `downgrade_generating_view_state`

- 若 `activeJobId` 对应 optimize artifact 且 `status=running`：降级时 **保持 review 页**，不要回澄清

---

## 五、前端实现要点

### 1. `types/job.ts`

```typescript
export type JobArtifact =
  | 'prd' | 'api-docs' | 'prompts'
  | 'optimize-prd' | 'optimize-api-docs' | 'optimize-prompts';

export type OptimizeJobArtifact = 'optimize-prd' | 'optimize-api-docs' | 'optimize-prompts';
```

### 2. `utils/jobViews.ts`

新增纯函数：

```typescript
export function isOptimizeArtifact(artifact: JobArtifact): boolean {
  return artifact.startsWith('optimize-');
}

export function contentArtifactFromOptimize(artifact: OptimizeJobArtifact): JobArtifact {
  // optimize-prd → prd
}

export function docTypeFromOptimizeArtifact(artifact: OptimizeJobArtifact): DocType { ... }
```

- optimize Job **不要**调 `generatingViewFor`（不进 generating 页）
- `setContentForArtifact` 扩展：optimize-prd → `setPrdContent`（通过 `contentArtifactFromOptimize` 映射）

### 3. `hooks/useGenerationJob.ts`

**`startOptimize(docType, currentContent, instruction, context)`：**

```typescript
const startOptimize = async (docType, currentContent, instruction, context) => {
  if (!sessionId) return;
  const artifact = optimizeArtifactFor(docType); // optimize-prd
  setError('');
  setIsOptimizingDocument(true);
  setStreamingContent('');
  // viewState 不变，仍在 review-*

  const { job_id } = await createJob(sessionId, artifact, {
    doc_type: docType,
    current_content: currentContent,
    instruction,
    context,
  });
  setActiveJobId(job_id);
  await subscribeJob(job_id, artifact);
};
```

**`subscribeJob` 分支（optimize）：**

- **不要**调用 `obs.beginPrdGeneration` / `beginApiDocsGeneration` 等（无 Stepper，或仅 `obs.startTimer` + 单行 hint「优化中…」）
- `onSnapshot`：写入 content，`setStreamingContent('')`，**不切 viewState**
- `onChunk`：与生成相同，更新 content + streamingContent
- `onRunSummary`：`obs.handleRunSummary(summary, { artifact: mappedContentArtifact })`
- 完成：`setIsOptimizingDocument(false)`，`setActiveJobId(null)`，`setStreamingContent('')`，viewState 仍为 review-*

**刷新重连 `useEffect`：**

- `getJob(activeJobId)` 若 `artifact` 为 optimize-* 且 `running`：
  - `setIsOptimizingDocument(true)`
  - `viewState` 设为 `reviewViewFor(contentArtifact)`，**不是** `generatingViewFor`
  - `subscribeJob(jobId, artifact)`

**返回值增加：** `startOptimize`、`isOptimizing`（或由 AppV2 继续自持 `isOptimizingDocument`，但重连时需 hook 内恢复）

推荐：hook 内部维护 `isOptimizingJob`，与 `isJobRunning` 并列，供 AppV2 绑定 `DocumentReview` 的 `isGenerating`。

### 4. `AppV2.tsx`

```typescript
const handleOptimizeDocument = async (docType, currentContent, instruction, context) => {
  if (!currentContent.trim()) { setError('...'); return; }
  const createdId = await ensureSessionCreated();
  if (!createdId) return;
  await jobGen.startOptimize(docType, currentContent, instruction, context);
};
```

- `DocumentReview` 的 `isGenerating={isOptimizingDocument || jobGen.isOptimizingJob}`
- 删除对 `conversationApi.optimizeDocumentStream` 的依赖（v1 `App.tsx` 可暂保留）

### 5. `sessionService.ts`（可选）

```typescript
export type V2SessionData = {
  // ...
  activeJobKind?: 'generate' | 'optimize' | null;
};
```

创建 optimize Job 时写 `optimize`，完成写 `null`。重连时可与 `getJob().artifact` 交叉校验。

---

## 六、UI 与体验约定

| 场景 | viewState | 正文展示 |
|------|-----------|----------|
| 点击优化 | `review-*` 不变 | 流式 `streamingContent` 只读 |
| 优化中刷新 | 仍 `review-*` | snapshot 全文立刻显示，后续 chunk 继续追加 |
| 优化完成 | `review-*` | 静态可编辑，优化后内容写入 `*Content` |
| 优化失败 | `review-*` | 保留 partial draft（若有），错误 banner |

**禁止**：优化中切到 `generating-*` 或跳回澄清。

**与生成 Job 的差异（实现时反复核对）：**

| | 生成 Job | 优化 Job |
|--|----------|----------|
| viewState | → `generating-*` | **保持** `review-*` |
| Stepper | 有 | **无**（或仅简单 loading） |
| artifact | prd / api-docs / prompts | optimize-* |
| 完成后 | → review-* | 已在 review-* |

---

## 七、run_summary

- optimize Job 结束时 SSE 必须有 `run_summary`
- 前端 `handleRunSummary` 写入对应 content artifact 的 `runSummaries`（如 `prd`），与同文档类型的生成统计共用同一槽位
- 失败走 `obs.captureStreamError`，保留 `request_id`

---

## 八、验收标准

1. PRD 审阅页优化，不刷新 → 流式出字，完成后正文更新，仍 `review-prd`
2. 优化过程中刷新 → 已优化部分立刻显示，后续继续，不回到优化前
3. 优化完成后刷新 → 静态 review，无打字机
4. 优化中关闭 tab 再打开同一 session → 重连继续，后台任务不中断
5. PRD 生成 `running` 时再点优化 → 409 或友好提示
6. 接口文档、提示词各测一次优化 + 刷新
7. `npm run build` 通过

---

## 九、实现边界

- 不改动生成三链路既有 Job 逻辑；仅新增 optimize artifact 与对应 runner / hook 分支
- 旧 `optimize-document-stream` 实现并验收后可标 deprecated
