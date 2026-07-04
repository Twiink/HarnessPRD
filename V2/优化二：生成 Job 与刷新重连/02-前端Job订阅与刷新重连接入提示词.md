# 前端 Job 订阅与刷新重连接入提示词

点击此处可复制本篇提示词

前端接入的目标，是把三条生成链路从「POST SSE 直连」改成 **「创建 Job + 订阅 Job stream」**：

- **正常生成：** 体验与今天一致（打字机、Stepper）
- **刷新页面：** `loadSession` 发现 `activeJobId` 后自动重连 stream；snapshot 中的已有全文立即展示，仅重连后的 chunk 继续增量输出

**实现原则：** **Job 生命周期不进 `AppV2.tsx` 大文件**。SSE 解析在 `utils/jobStream.ts`，HTTP 在 `jobApi.ts`，订阅 / 重连 / 三 artifact 编排抽到 **`hooks/useGenerationJob.ts`**。`AppV2` 只传 session 上下文、调 hook 暴露的 `startPrd` / `startApiDocs` / `startPrompts`，以及把 hook 返回的 state 接到现有 UI。

## 使用场景

这份提示词用于在 harnessprd 项目 `frontend/` 接入 Generation Job。

**前置条件**：后端已提供 `POST /api/jobs`、`GET /api/jobs/{id}`、`GET /api/jobs/{id}/stream`，事件协议含 `snapshot`。

**本次不做：**

- 文档优化 Job 化（`handleOptimizeDocument` 仍用现有 `optimize-document-stream`，见 03 篇）
- 改造澄清 `start-stream` / `continue-stream`
- 改造 v1 `App.tsx`
- 「继续生成 / 重新生成」中断 Banner（Job 方案下刷新即重连，不需要伪续写 UI）

### 一、功能目标

- `sessionService.ts`：`V2SessionData` 增加 `activeJobId`（当前进行中的任务 ID）
- 新建 `types/job.ts`（或放在 `jobApi.ts` 内）：Job 相关类型
- 新建 `services/jobApi.ts`：`createJob`、`getJob`
- 新建 `utils/jobStream.ts`：GET SSE 解析（含 `snapshot`）
- 新建 `utils/jobViews.ts`：artifact ↔ viewState、content 字段映射（纯函数）
- 新建 **`hooks/useGenerationJob.ts`**：`start*`、subscribe、刷新重连、AbortController
- **`AppV2.tsx` 薄改造**：删除三处 generate 内联 SSE 逻辑，改为调 hook；**不新增**重连 `useEffect` 在页面里
- 复用 `useGenerationObservability` 与 `DocumentReview` Stepper
- `npm run build` 通过

### 二、代码结构

```
frontend/src/
  types/
    job.ts                        # 新建（可选）：JobArtifact、JobSnapshot 等
  services/
    sessionService.ts             # 改造：activeJobId
    jobApi.ts                     # 新建：createJob、getJob
  utils/
    jobStream.ts                  # 新建：readJobStream
    jobViews.ts                   # 新建：generatingViewFor、reviewViewFor、contentKeyFor
  hooks/
    useGenerationObservability.ts # 已有：Stepper / timer / run_summary
    useGenerationJob.ts           # 新建：Job 编排
  AppV2.tsx                       # 薄改：调 hook，不传 SSE 细节
```

**分层职责：**

| 层 | 职责 |
|----|------|
| `jobApi` | HTTP：创建任务、查快照 |
| `jobStream` | 解析 GET SSE：`snapshot` / `text_delta` / `done` |
| `jobViews` | 哪种 artifact 对应哪个页面、更新哪份文档正文 |
| `useGenerationObservability` | Stepper、计时器、run_summary |
| **`useGenerationJob`** | createJob + subscribe + 重连 + 错误收束 + abort 管理 |
| **`AppV2`** | 组装参数调 `startPrd` 等；渲染；**不写** stream handler 细节 |

**AppV2 允许保留：** 按钮 `onClick={() => void jobGen.startPrd(summary)}`、把 `jobGen.streamingContent` 传给 `DocumentReview`。

**AppV2 禁止堆叠：** `readJobStream` 回调、`onSnapshot` 里改 state、重连 `useEffect`、`AbortController` ref。

### 三、TypeScript 类型

`sessionService.ts`：

```typescript
export type V2SessionData = {
  // ...现有字段
  activeJobId?: string | null;   // 进行中的 Job ID，刷新后用来重连
};
```

`jobApi.ts`：

```typescript
export type JobArtifact = 'prd' | 'api-docs' | 'prompts';

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export type JobPhase = 'writing' | 'reviewing' | 'rewriting' | 'generating' | 'done';

export type JobSnapshot = {
  id: string;
  session_id: string;
  artifact: JobArtifact;
  status: JobStatus;
  phase: JobPhase;
  draft_content: string;           // 当前草稿全文
  review?: PrdReviewResult | null;
  result?: GeneratePrdStreamResult | null;
  error?: string | null;
};

export type JobStreamHandlers = StreamHandlers & {
  onSnapshot?: (snap: JobSnapshotEvent) => void;
};

export type JobSnapshotEvent = {
  type: 'snapshot';
  status: JobStatus;
  phase: JobPhase;
  artifact: JobArtifact;
  draft_content: string;
  review?: PrdReviewResult | null;
};
```

### 四、jobApi

```typescript
export async function createJob(
  sessionId: string,
  artifact: JobArtifact,
  payload: Record<string, unknown>,
): Promise<{ job_id: string }> {
  const res = await fetch('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, artifact, payload }),
  });
  if (!res.ok) throw await parseError(res);
  return res.json();
}

export async function getJob(jobId: string): Promise<JobSnapshot> { ... }
```

**payload 形状（创建 Job 时传给后端的参数）：**

| artifact | payload 字段 |
|----------|--------------|
| `prd` | `requirements_summary`, `conversation_messages` |
| `api-docs` | `prd_content`, `conversation_messages` |
| `prompts` | `prd_content`, `api_docs_content`, `conversation_messages` |

### 五、readJobStream（GET SSE）

`utils/jobStream.ts` 实现 `readJobStream(jobId, handlers, signal?)`：

- URL：`GET /api/jobs/${jobId}/stream`
- 解析逻辑 **复用** `api.ts` 的 `readStream` 分支（`text_delta`、`phase`、`review`、`done`、`run_summary`、`error`）
- **新增 `snapshot`：** 调用 `handlers.onSnapshot`，**不要**触发打字机重播整篇

```typescript
if (event.type === 'snapshot') {
  handlers.onSnapshot?.(event);
  continue;
}
```

使用 `AbortController`：组件 unmount 或新订阅前 abort 旧连接，避免 StrictMode 双订阅。

### 六、展示规则（重要）

展示规则由 **`useGenerationJob` 内部** 维护 `streamingContent` 与各 artifact 正文 state，通过返回值交给 `AppV2` 渲染。`DocumentReview` 在 `generating-*` 下：

```typescript
// content 传 prdContent（或 apiDocsContent / promptsContent）
// streamingContent 仅承载「重连后的增量」或「首次订阅后的 live delta」

const displayContent =
  (isGeneratingPhase && streamingContent)
    ? mergeDisplay(prdContent, streamingContent)  // snapshot 已写入 prdContent，streaming 只追加新字
    : prdContent;
```

**规则表（用户看到什么）：**

| 场景 | prdContent | streamingContent | 用户看到 |
|------|------------|------------------|----------|
| 首次生成，snapshot 前 | '' | '' | Stepper，等待首 chunk |
| 收到 snapshot | 设为 draft 全文 | '' | **立刻全文**，无打字机 |
| live text_delta | 同步更新 | 可选：与 content 相同或只追加段 | 打字机 |
| Review 阶段 | 全文 | '' | 静态全文 + Stepper 审查 |
| 已完成刷新 | 全文 | '' | review 页，无 Stepper |

**禁止**：收到 snapshot 后从第一个字重新模拟流式输出整篇正文。

### 七、useGenerationJob（核心 hook）

新建 `hooks/useGenerationJob.ts`，与 `useGenerationObservability` 并列使用。

**入参（Options）：**

```typescript
type UseGenerationJobOptions = {
  sessionId: string | undefined;
  sessionLoadState: 'idle' | 'loading' | 'ready' | 'not_found' | 'error';
  activeJobId: string | null | undefined;
  messages: Message[];
  obs: ReturnType<typeof useGenerationObservability>;
  setContent: {
    setPrdContent: (v: string) => void;
    setApiDocsContent: (v: string) => void;
    setPromptsContent: (v: string) => void;
  };
  setViewState: (v: V2ViewState) => void;
  setPrdReviewResult: (v: PrdReviewResult | null) => void;
  setStreamingContent: (v: string) => void;
  setError: (v: string) => void;
  prdGenerationStageRef: React.RefObject<PrdGenerationStage>;
};
```

**返回值：**

```typescript
{
  startPrd: (summary: RequirementsSummary) => Promise<void>;
  startApiDocs: (prd: string) => Promise<void>;
  startPrompts: (prd: string, apiDocs: string) => Promise<void>;
  isJobRunning: boolean;
}
```

**hook 内部职责：**

1. `streamAbortRef`：新订阅前 abort 旧 SSE
2. `subscribeJob(jobId, artifact)`：封装 `readJobStream` + 全部 handlers
3. `restorePhaseUI(phase, artifact)`：调 `obs.begin*` / `createPrdHandlers`，恢复 Stepper 状态
4. **刷新重连 `useEffect`**：监听 `sessionLoadState === 'ready'` + `activeJobId`，**放在 hook 内，不在 AppV2**
5. 完成 / 失败：切 `review-*`、`obs.captureStreamError`

**subscribeJob 伪代码（在 hook 内）：**

```typescript
async function subscribeJob(jobId: string, artifact: JobArtifact) {
  const ac = new AbortController();
  streamAbortRef.current?.abort();
  streamAbortRef.current = ac;

  let accumulated = '';
  const setArtifactContent = contentSetterFor(artifact, setContent);

  await readJobStream(jobId, {
    onSnapshot: (snap) => {
      accumulated = snap.draft_content;
      setArtifactContent(accumulated);
      setStreamingContent('');
      restorePhaseUI(snap.phase, artifact, obs);
      if (snap.review) setPrdReviewResult(snap.review);
    },
    ...obs.createPrdHandlers({
      onPhase: (phase) => handlePrdPhase(phase),
      onReview: (review) => setPrdReviewResult(review),
    }),
    onChunk: (chunk) => {
      accumulated += chunk;
      setArtifactContent(accumulated);
      setStreamingContent(accumulated);
    },
    onRunSummary: (summary) => obs.handleRunSummary(summary, { finalizeSteps: ... }),
  }, ac.signal);

  setViewState(reviewViewFor(artifact));
  setStreamingContent('');
}
```

**startPrd 伪代码：**

```typescript
const startPrd = async (summary: RequirementsSummary) => {
  if (!sessionId) return;
  obs.beginPrdGeneration();
  setError('');
  setContent.setPrdContent('');
  setPrdReviewResult(null);
  setStreamingContent('');
  setViewState('generating-prd');

  const { job_id } = await createJob(sessionId, 'prd', {
    requirements_summary: summary,
    conversation_messages: messages,
  });

  await subscribeJob(job_id, 'prd');
};
```

`startApiDocs` / `startPrompts` 同理。`rewrite_started` 时不清空 v1 正文；失败保留 `accumulated` 并进 `review-*`。

### 八、AppV2.tsx 薄改造

**删除或替换：** 现有三个 `generate*` 内所有 `conversationApi.generate*Stream` 与内联 handler。

**新增 hook 初始化：**

```typescript
const obs = useGenerationObservability();
const jobGen = useGenerationJob({
  sessionId,
  sessionLoadState,
  activeJobId,
  messages,
  obs,
  setContent: { setPrdContent, setApiDocsContent, setPromptsContent },
  setViewState,
  setPrdReviewResult,
  setStreamingContent,
  setError,
  prdGenerationStageRef,
});
```

**AppV2 只保留薄包装（可选）：**

```typescript
const generatePrdForSummary = async (summary: RequirementsSummary) => {
  const createdId = await ensureSessionCreated();
  if (!createdId) return;
  await jobGen.startPrd(summary);
};
```

按钮处：`void jobGen.startApiDocs(prd)`、`void jobGen.startPrompts(prd, apiDocs)`。

`applySessionData` / `buildSessionSnapshot` 增加 `activeJobId`。

**AppV2 行数目标：** 相较内联 Job 逻辑，净增 **~30 行以内**；重连 effect、subscribe、AbortController **0 行** 留在 AppV2。

### 九、generateApiDocs 与前置流程

接口文档生成前，若产品仍有「确认 PRD 基线」等页面逻辑，**留在 AppV2**（例如校验基线 → `jobGen.startApiDocs(prd)`）。Job hook 只管「用户点生成之后」的 createJob + subscribe，不管表单校验和 Skill 注入（后端静默完成）。

若项目已去掉 RAG 确认页，用户点「生成接口文档」直接 `jobGen.startApiDocs(prd)` 即可。

### 十、刷新重连

重连逻辑在 **`useGenerationJob` 的 `useEffect`** 内（不在 AppV2）：

```typescript
useEffect(() => {
  if (sessionLoadState !== 'ready' || !sessionId || !activeJobId) return;
  if (reconnectStartedRef.current) return;
  // getJob → running → subscribeJob
  // completed / failed → 切 review + 写 content
}, [sessionLoadState, sessionId, activeJobId]);
```

- 不要在 `loadSession` 完成前 subscribe
- 不要对 running job 再 `POST /jobs`（会 409）

### 十一、旧 SSE 接口

`conversationApi.generatePrdFromSummaryStream` 等 **可保留** 但 AppV2 / hook **不再调用**。

### 十二、Stepper 与 run_summary

- hook 内调用 `obs.beginPrdGeneration` / `createPrdHandlers`，不重复 Stepper 逻辑
- `run_summary` 由 hook 转给 `obs.handleRunSummary`
- Review hint、phase 映射沿用 `useGenerationObservability` 既有逻辑

### 十三、验收标准

1. 生成 PRD，不刷新 → Stepper、打字机、审查 hint 与改造前体验一致
2. Writer 阶段刷新 → 全文立刻出现，后续继续出字，仍在 `generating-prd`
3. Review 阶段刷新 → 全文 + Stepper 审查，不回澄清
4. 完成后刷新 → `review-*` 静态全文，无打字机
5. 接口文档、提示词各测一次生成 + 刷新重连
6. `AppV2` 无 `readJobStream`、无重连 `useEffect`；Job 逻辑集中在 `useGenerationJob.ts`
7. `npm run build` 通过
