# 开发者指南

## 本地开发环境

### 前置要求
- Python 3.8+（推荐 3.11+）
- Node.js 18+
- Git

### 开发启动
```bash
# 后端（带热重载）
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000

# 前端（另一个终端）
cd frontend
npm run dev
```

访问：
- 前端：http://localhost:5173
- API 文档：http://localhost:8000/docs
- API ReDoc：http://localhost:8000/redoc

## 常见开发任务

### 添加新的表单问题

编辑 `backend/core/questions_config.json`，无需修改代码：

```json
{
  "base_questions": [...],
  "advanced_questions": [
    {
      "id": "new_field",          // 唯一 ID，snake_case
      "label": "字段标签",
      "question": "问题文案？",
      "description": "帮助文字",
      "type": "text",             // text | textarea | select | radio
      "placeholder": "例如：...",
      "options": null,            // select/radio 类型需要提供
      "required": false,
      "advanced": true
    }
  ]
}
```

新字段会自动出现在前端表单，并通过 `form_data` 传给 AI。需要在 `conversation_service.py` 的 `format_form_data()` `label_map` 中添加对应中文标签。

### 添加新的文档生成类型

**步骤 1：添加 Prompt（`services/prompts.py`）**
```python
NEW_DOC_GENERATION_PROMPT = """..."""
```

**步骤 2：添加 Service 方法（`services/document_service.py`）**
```python
async def generate_new_doc_stream(
    self,
    prd_content: str,
) -> AsyncGenerator[Dict, None]:
    llm = get_llm(temperature=0.3)
    lc_messages = [
        HumanMessage(content=f"{prd_content}\n\n{NEW_DOC_GENERATION_PROMPT}")
    ]
    async for chunk in llm.astream(lc_messages):
        if chunk.content:
            yield {"type": "chunk", "content": chunk.content}
    yield {"type": "done"}
```

**步骤 3：添加请求模型（`api/schemas.py`）**
```python
class GenerateNewDocRequest(BaseModel):
    prd_content: str
```

**步骤 4：添加路由（`api/conversation.py`）**
```python
from api.schemas import GenerateNewDocRequest

@router.post("/generate-new-doc-stream")
async def generate_new_doc_stream(request: GenerateNewDocRequest):
    gen = _make_sse_generator(
        document_service.generate_new_doc_stream(request.prd_content)
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)
```

**步骤 5：前端添加 API 调用（`frontend/src/services/api.ts`）**
```typescript
generateNewDocStream: async (prdContent: string, onChunk: (text: string) => void) => {
  const response = await fetch('/api/conversation/generate-new-doc-stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prd_content: prdContent }),
  })
  return readStream(response, onChunk)
},
```

**步骤 6：前端添加状态和 UI（`frontend/src/App.tsx`）**
在 `ViewState` 类型添加新状态，在对应位置添加 Handler 和渲染逻辑。

### 修改 Prompt

直接编辑 `backend/services/prompts.py`，修改对应常量。后端热重载会自动生效（开发模式）。

### 切换 LLM Provider

```bash
# 运行时切换（立即生效，重启失效）
curl -X POST http://localhost:8000/api/config/update \
  -H "Content-Type: application/json" \
  -d '{"default_llm_provider": "openai", "default_llm_model": "gpt-4o"}'

# 永久切换（修改 .env）
echo "DEFAULT_LLM_PROVIDER=openai" >> backend/.env
echo "DEFAULT_LLM_MODEL=gpt-4o" >> backend/.env
```

### 调试 SSE 流

在浏览器 Network 面板中，找到 SSE 请求，点击 "EventStream" 标签页，可以实时看到每个 SSE 事件。

后端调试：在 Service 方法中添加 `print()` 或使用 Python logging：
```python
import logging
logger = logging.getLogger(__name__)
logger.info(f"LLM chunk: {chunk.content[:50]}")
```

## 代码规范

### 后端（Python）
- 类型注解：函数参数和返回值都加类型注解
- 异步函数：使用 `async/await`，流式方法返回 `AsyncGenerator[Dict, None]`
- 错误处理：Service 层抛出异常，路由层的 `_make_sse_generator` 统一捕获并发送 error 事件
- 命名：函数/变量 snake_case，类 PascalCase，常量 UPPER_CASE

### 前端（TypeScript）
- 类型：所有 props 定义接口，不用 `any`
- 组件：纯函数组件 + Hooks，不用 class 组件
- 状态：只在 `App.tsx` 维护状态，子组件无状态（通过 props 接收 + 回调通知）
- 命名：组件 PascalCase，函数 camelCase，类型/接口 PascalCase

## 项目扩展方向

### 用户认证
目前无认证，所有人都能使用。如需添加：
- 后端：FastAPI 的 `Depends` 机制 + JWT
- 前端：登录页 + token 存储

### 会话持久化（数据库）
目前状态存在 localStorage，无法多设备同步。如需后端持久化：
- 数据库：SQLite（简单）或 PostgreSQL（生产）
- ORM：SQLAlchemy
- 需要改造后端 API，添加用户-会话关联

### 多语言支持
目前完全中文。如需多语言：
- 前端：i18n 库（如 `react-i18next`）
- Prompt：切换 `SYSTEM_PROMPT` 为对应语言版本

### 模板市场
支持多种 PRD 模板（通用 SaaS、电商、内容平台等）：
- `core/prd_template.md` 改为多模板支持
- 前端添加模板选择 UI

## 常见问题

### 后端启动失败：端口占用
```bash
lsof -i :8000 | grep LISTEN
kill -9 <PID>
```

### 前端代理不生效
确认后端正在运行，`vite.config.ts` 中 proxy 目标地址正确：
```typescript
proxy: {
  '/api': 'http://localhost:8000'
}
```

### `langchain-anthropic` 版本问题
删除 venv 重装：
```bash
rm -rf backend/.venv
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 流式响应卡住不动
可能原因：
1. Nginx 代理未设置 `proxy_buffering off`
2. 网络代理（VPN 等）缓冲了响应
3. 浏览器扩展拦截了 SSE

### 前端构建失败（TypeScript 错误）
```bash
cd frontend
npm run build 2>&1 | head -50
```
查看 TS 错误详情，通常是类型不匹配或导入路径问题。

## 依赖升级注意事项

| 依赖 | 注意事项 |
|------|---------|
| `langchain-anthropic` | 锁定 `<0.3.0`，升级前测试 API 兼容性 |
| `langchain` | 与 `langchain-anthropic`/`langchain-openai` 版本需匹配 |
| `pydantic` | v1 和 v2 API 不兼容，当前使用 v2 |
| `react` | 18.x，升级到 19 需测试 SSE hook 行为 |
