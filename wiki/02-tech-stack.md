# 技术栈说明

## 技术栈总览

| 层次 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 前端框架 | React | 18.2 | UI 渲染与状态管理 |
| 前端构建 | Vite | 5.x | 开发服务器 + 生产构建 |
| 类型系统 | TypeScript | 5.x | 静态类型检查 |
| 样式 | Tailwind CSS | 3.x | 原子化 CSS |
| Markdown 渲染 | react-markdown | 9.x | 渲染 AI 回复 |
| HTTP 客户端 | Axios | 1.6 | API 请求 |
| 图标 | lucide-react | 0.294 | UI 图标 |
| 后端框架 | FastAPI | 0.104+ | API 服务 |
| ASGI 服务器 | Uvicorn | 0.24+ | 异步 Web 服务器 |
| 数据验证 | Pydantic v2 | 2.5+ | 请求/响应模型 |
| 配置管理 | pydantic-settings | 2.1+ | 环境变量加载 |
| LLM 编排 | LangChain | 0.1+ | LLM 调用抽象 |
| Anthropic 集成 | langchain-anthropic | <0.3.0 | Claude API |
| OpenAI 集成 | langchain-openai | 0.0.5+ | GPT API |
| 异步 HTTP | httpx | 0.25+ | 异步 HTTP 请求 |
| 语言 | Python | 3.8+ | 后端语言 |

## 后端技术详解

### FastAPI
选择 FastAPI 的原因：
- **原生异步支持**：`async/await` 配合 `AsyncGenerator` 实现 SSE 流式输出，是核心需求
- **自动文档**：访问 `/docs` 即得交互式 API 文档，便于调试
- **Pydantic 集成**：请求体自动验证，减少错误处理代码
- **类型提示**：完整的 Python 类型系统支持

### LangChain
选择 LangChain 的原因：
- **统一接口**：`ChatAnthropic` 和 `ChatOpenAI` 使用相同的 `.astream()` 接口，Provider 切换无需改业务代码
- **消息格式**：`HumanMessage`、`SystemMessage`、`AIMessage` 标准化消息管理
- **流式支持**：`.astream()` 返回 `AsyncGenerator`，配合 FastAPI `StreamingResponse` 实现 SSE

> **注意：** `langchain-anthropic` 版本锁定在 `<0.3.0`。  
> 原因：0.3.0+ 版本发送了 `context_management` 字段，部分 Anthropic API 代理不支持，会返回 400 错误。

### Pydantic Settings
环境变量统一通过 `Settings` 类管理，支持：
- `.env` 文件自动加载
- 类型安全的配置访问
- 运行时配置更新（通过 `/api/config/update` 接口）

## 前端技术详解

### React 18
使用函数组件 + Hooks，核心状态全部集中在 `App.tsx`：
- `useState` 管理所有 UI 状态
- 无全局状态库（Redux/Zustand 等），复杂度不需要
- 子组件通过 props 接收数据 + 回调函数

### Vite 开发代理
`vite.config.ts` 配置了 API 代理：
```typescript
proxy: {
  '/api': 'http://localhost:8000'
}
```
前端请求 `/api/*` 时自动转发到后端，开发期间无跨域问题。

### Tailwind CSS
自定义了 `primary` 颜色系（sky blue，50-900 九档），所有按钮、高亮、激活态均使用 `primary-*` 类名。颜色定义在 `tailwind.config.js`。

### SSE 客户端实现
浏览器原生 `EventSource` 不支持 POST 请求，因此 `api.ts` 使用 Axios + `ReadableStream` 手动解析 SSE：

```typescript
// 简化逻辑
const response = await axios.post(url, body, { responseType: 'stream' })
const reader = response.data.getReader()
// 逐行解析 "data: {...}\n\n" 格式
```

### react-markdown
AI 回复中可能含有 Markdown（代码块、列表、加粗等），使用 `react-markdown` 渲染。自定义了 `code` 元素样式（灰色背景）。

## 为什么不用 XXX

| 方案 | 未选择的原因 |
|------|-------------|
| Next.js | 项目无 SSR 需求，Vite 更轻量快 |
| Redux/Zustand | 状态树不复杂，useState 足够 |
| WebSocket | SSE 对单向流式输出更合适，实现更简单 |
| SQLite/PostgreSQL | 后端无状态设计，无需数据库 |
| Celery/任务队列 | LLM 调用直接流式返回，无需异步任务 |
| Docker（目前） | 本地开发为主，start.sh 一键启动 |
