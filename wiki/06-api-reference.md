# API 接口文档

## 基础信息

- 基础路径：`http://localhost:8000`
- 前端代理：`/api` → `http://localhost:8000`（Vite dev proxy）
- 内容类型：`application/json`（请求）/ `text/event-stream`（SSE 响应）
- 交互式文档：`http://localhost:8000/docs`

---

## 对话接口

### 获取表单问题配置

```
GET /api/conversation/questions
```

**响应示例**
```json
{
  "base_questions": [
    {
      "id": "product_name",
      "label": "产品名称",
      "question": "你的产品叫什么名字？",
      "description": "...",
      "type": "text",
      "required": true,
      "advanced": false
    }
  ],
  "advanced_questions": [...]
}
```

---

### 开始对话（流式）

```
POST /api/conversation/start-stream
```

**请求体**
```json
{
  "initial_input": "我想做一个...",
  "form_data": {
    "product_name": "...",
    "problem_solved": "...",
    "target_users": "..."
  }
}
```

`initial_input` 和 `form_data` 均可为空，至少提供一个即可。

**SSE 响应流**
```
data: {"type": "chunk", "content": "好的，"}
data: {"type": "chunk", "content": "你的产品想法很有趣..."}
data: {"type": "done", "conversation_id": "conv_a1b2c3d4", "messages": [...]}
data: [DONE]
```

`done` 事件中的 `messages` 为完整消息历史，前端需保存用于后续请求。

---

### 继续对话（流式）

```
POST /api/conversation/continue-stream
```

**请求体**
```json
{
  "conversation_id": "conv_a1b2c3d4",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "human", "content": "..."},
    {"role": "ai", "content": "..."}
  ],
  "user_input": "用户的新消息"
}
```

**SSE 响应流**（同 start-stream，`done` 事件同样返回更新后的 `messages`）

---

## 文档生成接口

### 生成 PRD（流式）

```
POST /api/conversation/generate-prd-stream
```

**请求体**
```json
{
  "conversation_messages": [
    {"role": "system", "content": "..."},
    {"role": "human", "content": "..."},
    ...
  ]
}
```

**SSE 响应流**
```
data: {"type": "chunk", "content": "# PRD: 产品名称\n"}
data: {"type": "chunk", "content": "\n## 1. 产品概述\n"}
...
data: {"type": "done"}
data: [DONE]
```

生成的 PRD 为 Markdown 格式，包含 6 个标准章节。

---

### 生成接口文档（流式）

```
POST /api/conversation/generate-api-docs-stream
```

**请求体**
```json
{
  "prd_content": "# PRD: ...\n\n## 1. 产品概述\n...",
  "conversation_messages": [...]
}
```

需要提供已生成的 PRD 内容作为上下文。

**SSE 响应流**（同 PRD，内容为接口文档 Markdown）

---

### 生成 AI 提示词套件（流式）

```
POST /api/conversation/generate-prompts-stream
```

**请求体**
```json
{
  "prd_content": "# PRD: ...",
  "api_docs_content": "# 接口文档: ..."
}
```

`api_docs_content` 可为空字符串（跳过接口文档时）。

**SSE 响应流**（内容为 5 类提示词 Markdown）

---

### 优化文档（流式）

```
POST /api/conversation/optimize-document-stream
```

**请求体**
```json
{
  "doc_type": "prd",
  "current_content": "当前文档全文...",
  "instruction": "把技术栈部分改成 React + FastAPI",
  "context": "其他已生成文档内容（可选）"
}
```

`doc_type` 可选值：
- `prd`：产品需求文档
- `api-docs`：接口文档
- `prompts`：AI 提示词套件

**SSE 响应流**（内容为优化后的完整文档，直接替换原文档）

---

## 配置管理接口

### 获取支持的 LLM Provider 列表

```
GET /api/config/llm-providers
```

**响应示例**
```json
{
  "providers": [
    {
      "id": "anthropic",
      "name": "Anthropic (Claude)",
      "models": [
        {"id": "claude-opus-4-6", "name": "Claude Opus 4.6"},
        {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"},
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
        {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5"}
      ]
    },
    {
      "id": "openai",
      "name": "OpenAI",
      "models": [
        {"id": "gpt-4o", "name": "GPT-4o"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"}
      ]
    }
  ]
}
```

---

### 获取当前配置

```
GET /api/config/current
```

**响应示例**
```json
{
  "default_llm_provider": "anthropic",
  "default_llm_model": "claude-3-5-sonnet-20241022",
  "anthropic_base_url": "",
  "has_anthropic_key": true,
  "has_openai_key": false
}
```

注意：不返回 API Key 明文。

---

### 更新配置（运行时）

```
POST /api/config/update
```

**请求体**（所有字段可选，只传需要修改的）
```json
{
  "anthropic_api_key": "sk-ant-...",
  "anthropic_base_url": "https://my-proxy.example.com",
  "openai_api_key": "sk-...",
  "default_llm_provider": "openai",
  "default_llm_model": "gpt-4o"
}
```

**响应示例**
```json
{
  "status": "success",
  "updated": ["default_llm_provider", "default_llm_model"]
}
```

> 注意：此接口修改的是运行时内存中的 `settings` 对象，重启后恢复为 `.env` 文件中的值。

---

## 健康检查

```
GET /
GET /health
```

**响应**
```json
{"status": "ok", "message": "Vibe Coding API is running"}
```

---

## 错误处理

### SSE 错误
流式接口出错时，会在流中发送 error 事件，然后正常结束：
```
data: {"type": "error", "message": "错误详情"}
data: [DONE]
```

### HTTP 错误
非流式接口使用标准 HTTP 状态码：
- `422`：请求体验证失败（Pydantic 自动处理）
- `500`：服务器内部错误（含 `detail` 字段）
