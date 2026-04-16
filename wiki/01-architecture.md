# 架构设计

## 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                      浏览器 (前端)                        │
│                                                         │
│  FormStep → ChatView → DocumentReview → Done           │
│                   React SPA (Vite)                      │
│                App.tsx (状态机核心)                      │
└─────────────────────┬───────────────────────────────────┘
                      │  HTTP / SSE (流式)
                      │  /api/conversation/*
┌─────────────────────▼───────────────────────────────────┐
│                    FastAPI 后端                          │
│                                                         │
│  api/conversation.py   api/config.py                   │
│         ↓                     ↓                         │
│  ConversationService   DocumentService                  │
│         ↓                     ↓                         │
│         └──────┬──────────────┘                         │
│                ↓                                         │
│           get_llm() (llm_factory.py)                   │
│                ↓                                         │
└───────────────────────────────────────────────────────┬─┘
                                                        │
                                           ┌────────────▼──────────┐
                                           │   LLM Provider         │
                                           │   Anthropic / OpenAI   │
                                           └───────────────────────┘
```

## 分层设计

### 前端层（React SPA）
- 单页应用，无路由跳转，通过 `viewState` 状态机控制页面切换
- 所有会话状态存储在 `localStorage`，后端无状态
- 通过 SSE（Server-Sent Events）接收流式响应

### API 层（FastAPI Router）
- 纯路由层，只做参数解析 + 返回 StreamingResponse
- 不含业务逻辑，委托给 Service 层
- 两个 Router：`conversation`（主功能）、`config`（LLM 配置）

### Service 层
| Service | 职责 |
|---------|------|
| `ConversationService` | 对话启动与延续，消息格式转换 |
| `DocumentService` | PRD、接口文档、提示词的生成与优化 |
| `get_llm()` | LLM 实例工厂，隔离 Anthropic/OpenAI 差异 |

### 基础设施层
| 模块 | 职责 |
|------|------|
| `prompts.py` | 所有 LLM Prompt 常量集中管理 |
| `core/config.py` | 环境变量加载（pydantic-settings） |
| `core/questions_config.json` | 表单问题配置（数据驱动） |
| `core/prd_template.md` | PRD 格式模板（可选参考） |

## 核心设计决策

### 1. 流式优先（Streaming First）
所有 LLM 调用均使用 SSE 流式输出，用户实时看到内容生成，提升感知响应速度。

```
LLM.astream() → AsyncGenerator → SSE → EventSource → 前端 state 累积
```

### 2. 后端无状态
对话历史完全由前端维护（`messages` state + `localStorage`）。每次请求把完整历史发给后端，后端不存储任何会话数据。

**优点：**
- 无需数据库
- 横向扩展简单
- 刷新页面可恢复进度

**取舍：**
- 历史越长，请求体越大
- 不支持多设备同步

### 3. 工厂模式隔离 LLM 差异
`get_llm()` 工厂函数统一创建 LLM 实例，两个 Service 无需感知底层 Provider 差异。运行时通过 `/api/config/update` 切换 Provider。

### 4. Prompt 集中管理
所有 Prompt 定义在 `services/prompts.py`，不散落在业务代码中。便于迭代优化和版本管理。

### 5. 前端状态机
9 个 `ViewState` 枚举值构成线性状态机，使用 `STEP_INDEX` 映射到进度条：

```
form → chatting → generating-prd → review-prd
     → generating-api-docs → review-api-docs
     → generating-prompts → review-prompts → done
```

状态转换严格单向，避免逻辑混乱。

## 数据流

### 对话流程
```
用户填写表单
    ↓
FormStep.onSubmit()
    ↓
App.handleStartConversation()
    ↓
POST /api/conversation/start-stream { initial_input, form_data }
    ↓ SSE chunks
AI 回复逐字显示
    ↓
viewState: 'chatting'，等待用户继续对话
    ↓
用户输入 → POST /api/conversation/continue-stream
    ↓
... 持续对话 ...
    ↓
用户点击"生成 PRD"
```

### 文档生成流程
```
App.handleGeneratePRD()
    ↓
viewState: 'generating-prd'
    ↓
POST /api/conversation/generate-prd-stream { conversation_messages }
    ↓ SSE chunks
DocumentReview（只读 textarea 实时显示）
    ↓
SSE done → viewState: 'review-prd'，textarea 变可编辑
    ↓
用户审核/编辑/优化
    ↓
点击"生成接口文档" → 重复上述流程
```

## 会话持久化

```javascript
// 保存
localStorage.setItem('vibecoding_session', JSON.stringify({
  formData, messages, conversationId, viewState,
  prdContent, apiDocsContent, promptsContent
}))

// 恢复（状态降级处理）
// generating-* 状态 → 降级到上一个 review-* 状态
// 避免用户刷新页面后卡在"生成中"
```
