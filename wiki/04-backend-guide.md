# 后端开发指南

## 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看交互式 API 文档。

## 模块职责划分

```
api/          ← HTTP 层（路由、参数解析、返回格式）
  ├── conversation.py   主功能路由
  ├── config.py         LLM 配置路由
  └── schemas.py        Pydantic 请求模型

services/     ← 业务层（核心逻辑）
  ├── prompts.py            Prompt 常量
  ├── llm_factory.py        LLM 工厂
  ├── conversation_service.py  对话逻辑
  └── document_service.py      文档生成逻辑

core/         ← 基础设施（配置、静态资源）
  ├── config.py
  ├── questions_config.json
  └── prd_template.md
```

**原则：路由不含业务逻辑，Service 不含路由概念。**

## SSE 流式响应原理

所有文档生成和对话续接都通过 SSE（Server-Sent Events）实现实时流式输出。

### 后端实现
```python
# services/document_service.py 中的 AsyncGenerator
async def generate_prd_stream(self, ...) -> AsyncGenerator[Dict, None]:
    llm = get_llm(temperature=0.3)
    async for chunk in llm.astream(lc_messages):
        if chunk.content:
            yield {"type": "chunk", "content": chunk.content}
    yield {"type": "done"}

# api/conversation.py 中的路由
@router.post("/generate-prd-stream")
async def generate_prd_stream(request: ConversationMessagesRequest):
    gen = _make_sse_generator(
        document_service.generate_prd_stream(request.conversation_messages)
    )
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)
```

### `_make_sse_generator()` 包装器
```python
def _make_sse_generator(async_gen):
    async def generate():
        try:
            async for event in async_gen:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "data: [DONE]\n\n"
    return generate
```

SSE 格式固定为：`data: {json}\n\n`，结束标记为 `data: [DONE]\n\n`。

### SSE 消息类型
| type | 说明 | 包含字段 |
|------|------|---------|
| `chunk` | 内容片段 | `content: str` |
| `done` | 流结束 | 可选附加数据（如对话 ID、消息列表） |
| `error` | 出错 | `message: str` |

## LLM 调用

### 工厂函数
```python
# services/llm_factory.py
from services.llm_factory import get_llm

llm = get_llm(temperature=0.3)  # 文档生成用低温（确定性）
llm = get_llm(temperature=0.7)  # 对话用默认温度
llm = get_llm(temperature=0.5)  # 提示词生成用中等温度
```

### Provider 切换
通过 `.env` 配置：
```
DEFAULT_LLM_PROVIDER=anthropic    # 或 openai
DEFAULT_LLM_MODEL=claude-3-5-sonnet-20241022
```

也可通过 API 运行时切换（见配置管理章节）。

### 消息格式转换
前端传来的消息格式是 `[{"role": "user", "content": "..."}, ...]`，需转换为 LangChain 格式：
```python
# services/conversation_service.py
def _build_lc_messages(messages: List[Dict[str, str]]):
    for msg in messages:
        if msg["role"] == "system":
            yield SystemMessage(content=msg["content"])
        elif msg["role"] in ("user", "human"):
            yield HumanMessage(content=msg["content"])
        elif msg["role"] in ("assistant", "ai"):
            yield AIMessage(content=msg["content"])
```

## 对话管理

### 会话无状态设计
后端**不存储**任何会话数据。每次请求，前端都把完整的 `messages` 数组发过来，后端直接用于构建 LangChain 消息列表。

### 初始对话构建
```python
def _build_initial_messages(self, user_initial_input, form_data):
    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    if form_data:
        # 把表单数据格式化为可读文本，拼入第一条 Human 消息
        form_summary = format_form_data(form_data)
        initial_content = f"用户已填写了初始产品信息：\n\n{form_summary}\n\n..."
    elif user_initial_input:
        initial_content = f"用户的初步想法：{user_initial_input}\n\n..."
    else:
        initial_content = "用户想开始产品需求对话，但还没有提供具体信息..."

    messages.append(HumanMessage(content=initial_content))
    return messages
```

### 会话 ID 生成
```python
conv_id = "conv_" + str(abs(hash(full_content)))[:8]
```
基于首次 AI 回复内容的 hash，轻量级唯一标识（无需数据库序列）。

## 文档生成

### PRD 生成
```python
# 可选加载本地模板
def _build_prd_prompt() -> str:
    template = _load_prd_template()  # 读 core/prd_template.md
    if template:
        return PRD_GENERATION_PROMPT + f"\n\n请参考以下格式模板：\n\n{template}"
    return PRD_GENERATION_PROMPT
```

### 接口文档生成
接口文档需要 PRD 内容 + 对话历史作为上下文：
```python
async def generate_api_docs_stream(self, prd_content, conversation_messages):
    lc_messages = _build_lc_messages(conversation_messages)
    lc_messages.append(HumanMessage(
        content=f"以下是已确认的产品需求文档（PRD）：\n\n{prd_content}\n\n{API_DOCS_GENERATION_PROMPT}"
    ))
```

### 文档优化
```python
prompt = OPTIMIZE_DOCUMENT_PROMPT_TEMPLATE.format(
    doc_type_label=doc_type_label,   # "产品需求文档（PRD）" 等
    instruction=instruction,          # 用户输入的优化指令
    current_content=current_content,  # 当前文档内容
    context_section=context_section,  # 其他已生成文档（可选上下文）
)
```

## 配置管理 API

### 查询支持的 Provider
```
GET /api/config/llm-providers
```

### 查询当前配置
```
GET /api/config/current
```
注意：API Key 不返回明文，只返回是否已设置的布尔值。

### 运行时更新配置
```
POST /api/config/update
{ "default_llm_provider": "openai", "default_llm_model": "gpt-4o" }
```
更新全局 `settings` 对象，立即生效，重启后恢复（配置未持久化到 `.env`）。

## 添加新接口步骤

1. **在 `services/prompts.py` 添加 Prompt**（如需要）
2. **在 `services/document_service.py` 添加方法**（AsyncGenerator 返回流式结果）
3. **在 `api/schemas.py` 添加请求模型**
4. **在 `api/conversation.py` 添加路由**（用 `_make_sse_generator` 包装）

## 常见问题

### `context_management: Extra inputs are not permitted`
`langchain-anthropic` 版本 ≥ 0.3.0 会发送此字段，部分 API 代理不支持。
解决：`requirements.txt` 已锁定 `langchain-anthropic>=0.1.0,<0.3.0`，删除旧 `.venv` 重装即可。

### `ModuleNotFoundError: No module named 'langchain.schema'`
新版 LangChain 将消息类移到了 `langchain_core.messages`，已修复。

### 后端端口被占用
```bash
lsof -i :8000 | grep LISTEN
kill -9 <PID>
```
