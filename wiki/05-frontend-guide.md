# 前端开发指南

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173。开发期间通过 Vite proxy 自动转发 `/api/*` 到 `localhost:8000`。

## 核心：`App.tsx` 状态机

`App.tsx` 是整个前端的核心，所有状态和业务逻辑都在这里。理解它的状态机是理解前端的关键。

### 9 个 ViewState

```typescript
type ViewState =
  | 'form'                 // 初始表单页
  | 'chatting'             // AI 对话页
  | 'generating-prd'       // PRD 生成中（流式输出）
  | 'review-prd'           // PRD 审核/编辑
  | 'generating-api-docs'  // 接口文档生成中
  | 'review-api-docs'      // 接口文档审核/编辑
  | 'generating-prompts'   // AI 提示词生成中
  | 'review-prompts'       // AI 提示词审核/编辑
  | 'done'                 // 完成页（可下载）
```

### 状态转换路径

```
form
  ↓ handleStartConversation()
chatting
  ↓ handleGeneratePRD()
generating-prd → review-prd
                   ↓ handleGenerateApiDocs()  or  handleSkipApiDocs()
           generating-api-docs → review-api-docs    ↓
                                    ↓              generating-prompts → review-prompts
                                 handleGeneratePrompts()                  ↓
                                                               handleEndTask() / done
```

每个 `review-*` 状态都可以：
- 继续下一步
- 跳过（接口文档可跳过）
- 结束任务（直接到 done）

### 关键 State

```typescript
const [viewState, setViewState] = useState<ViewState>('form')
const [messages, setMessages] = useState<Message[]>([])
const [conversationId, setConversationId] = useState('')
const [streamingContent, setStreamingContent] = useState('')  // 流式累积
const [isStreaming, setIsStreaming] = useState(false)          // 对话流式中
const [isGenerating, setIsGenerating] = useState(false)        // 文档生成/优化中
const [prdContent, setPrdContent] = useState('')
const [apiDocsContent, setApiDocsContent] = useState('')
const [promptsContent, setPromptsContent] = useState('')
```

`streamingContent` 是共享的流式内容缓冲区，对话流式、文档生成流式、文档优化流式都复用它。

## SSE 流处理模式

前端处理流式响应的通用模式：

```typescript
// 以 handleGeneratePRD 为例
const handleGeneratePRD = async () => {
  setViewState('generating-prd')
  setStreamingContent('')
  setIsGenerating(true)

  try {
    await conversationApi.generatePrdStream(
      messages,
      (chunk: string) => {
        // 每来一个 chunk，追加到 streamingContent
        setStreamingContent(prev => prev + chunk)
      }
    )
    // 流结束后，把 streamingContent 保存到 prdContent
    setPrdContent(streamingContent_ref.current)
    setViewState('review-prd')
  } finally {
    setIsGenerating(false)
  }
}
```

`DocumentReview` 组件区分两种内容来源：
- `isGeneratingPhase=true`：显示 `streamingContent`（只读）
- `isGeneratingPhase=false`：显示 `content`（可编辑）

## 组件说明

### `<FormStep>`
```typescript
<FormStep
  questions={questions}          // 从 API 加载的问题配置
  formData={formData}
  onChange={(key, value) => setFormData(prev => ({...prev, [key]: value}))}
  showAdvanced={showAdvanced}
  onToggleAdvanced={() => setShowAdvanced(!showAdvanced)}
  onSubmit={handleStartConversation}
  loading={isStreaming}
/>
```

表单提交时同时传 `form_data` 和 `initial_input`（用户在输入框里补充的说明）。

### `<MessageList>`
```typescript
<MessageList messages={messages} loading={isStreaming} />
```

组件内部过滤了 `system` 角色消息和首条 Human 上下文消息（前端构造的初始提示不展示给用户）。AI 消息用 `react-markdown` 渲染。

### `<ChatInput>`
```typescript
<ChatInput
  onSend={handleSendMessage}
  loading={isStreaming}
  disabled={isStreaming}
  placeholder="继续告诉我你的想法..."
/>
```

### `<DocumentReview>`
```typescript
<DocumentReview
  title="产品需求文档（PRD）"
  content={prdContent}                     // 已生成/编辑的内容
  streamingContent={streamingContent}       // 流式生成中的内容
  isGenerating={isGenerating}              // 优化中
  isGeneratingPhase={viewState === 'generating-prd'}  // 首次生成中
  actions={[
    { label: '生成接口文档', variant: 'primary', onClick: handleGenerateApiDocs },
    { label: '跳过接口文档', variant: 'secondary', onClick: handleSkipApiDocs },
    { label: '结束任务', variant: 'ghost', onClick: handleEndTask },
  ]}
  onSaveEdit={(newContent) => setPrdContent(newContent)}
  onOptimize={(instruction) => handleOptimizeDocument('prd', instruction)}
/>
```

## 会话持久化

### 保存
```typescript
const saveSession = () => {
  localStorage.setItem('vibecoding_session', JSON.stringify({
    formData, messages, conversationId, viewState,
    prdContent, apiDocsContent, promptsContent
  }))
}
```

在每次状态改变（`viewState`、`messages`、文档内容）时自动调用。

### 恢复与状态降级
```typescript
const loadSession = () => {
  const saved = localStorage.getItem('vibecoding_session')
  if (!saved) return

  const session = JSON.parse(saved)
  let restoredState = session.viewState

  // 如果上次是生成中的状态，降级到上一个稳定状态
  const downgradeMap = {
    'generating-prd': 'chatting',
    'generating-api-docs': 'review-prd',
    'generating-prompts': 'review-api-docs',
  }
  if (downgradeMap[restoredState]) {
    restoredState = downgradeMap[restoredState]
  }

  setViewState(restoredState)
  // ... 恢复其他状态
}
```

用户刷新页面后不会卡在"生成中"状态，而是退回到上一个可操作状态。

### 重置
```typescript
const handleRestart = () => {
  localStorage.removeItem('vibecoding_session')
  // 重置所有 state 到初始值
  setViewState('form')
  setMessages([])
  // ...
}
```

## API 客户端

`api.ts` 封装了所有后端调用，核心是 `readStream()` 函数：

```typescript
async function readStream(
  response: Response,
  onChunk: (text: string) => void
): Promise<any> {
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''  // 保留未完成的行

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6)
      if (data === '[DONE]') return lastEvent
      const event = JSON.parse(data)
      if (event.type === 'chunk') onChunk(event.content)
      else if (event.type === 'error') throw new Error(event.message)
      else lastEvent = event  // 保存 done 事件的附加数据
    }
  }
}
```

## 进度指示器

顶部进度条通过 `STEP_INDEX` 映射实现：

```typescript
const STEP_INDEX: Record<ViewState, number> = {
  'form': 0,
  'chatting': 1,
  'generating-prd': 2, 'review-prd': 2,
  'generating-api-docs': 3, 'review-api-docs': 3,
  'generating-prompts': 4, 'review-prompts': 4,
  'done': 5,
}
```

5 个步骤：表单 → 对话 → PRD → 接口文档 → 提示词。

## 添加新组件步骤

1. 在 `src/components/` 创建 `.tsx` 文件
2. 定义 Props 接口
3. 在 `App.tsx` 对应的 viewState 分支中引入使用
4. 如有新 API 调用，在 `api.ts` 添加对应方法

## 开发常用命令

```bash
npm run dev      # 启动开发服务器
npm run build    # 构建生产版本（含 TypeScript 检查）
npm run lint     # ESLint 检查
npm run preview  # 预览生产构建
```

## 样式约定

- 使用 Tailwind utility classes，不写自定义 CSS
- 主题色用 `primary-*`（sky blue 系），在 `tailwind.config.js` 定义
- 按钮变体：`primary`（蓝色实心）、`secondary`（灰色边框）、`ghost`（无边框）
- 响应式：目前未做移动端适配，主要面向桌面使用
