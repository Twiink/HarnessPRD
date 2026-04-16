# 目录结构与文件说明

## 完整目录树

```
vibecoding/
├── start.sh                    # 一键启动脚本（后端 + 前端）
├── README.md                   # 项目简介
│
├── backend/                    # Python FastAPI 后端
│   ├── main.py                 # 应用入口，FastAPI 实例
│   ├── requirements.txt        # Python 依赖
│   ├── .env                    # 环境变量（不提交 git）
│   ├── .env.example            # 环境变量模板
│   │
│   ├── core/                   # 基础配置与静态资源
│   │   ├── config.py           # 环境变量配置类（Settings）
│   │   ├── questions_config.json   # 表单问题配置
│   │   └── prd_template.md     # PRD 格式参考模板（可选）
│   │
│   ├── api/                    # HTTP 路由层
│   │   ├── conversation.py     # 对话与文档生成路由
│   │   ├── config.py           # LLM 配置管理路由
│   │   └── schemas.py          # Pydantic 请求模型
│   │
│   └── services/               # 业务逻辑层
│       ├── prompts.py          # 所有 LLM Prompt 常量
│       ├── llm_factory.py      # LLM 实例工厂函数
│       ├── conversation_service.py  # 对话服务（chat）
│       └── document_service.py      # 文档生成服务（PRD/API/prompts）
│
├── frontend/                   # React + TypeScript 前端
│   ├── package.json            # npm 依赖与脚本
│   ├── vite.config.ts          # Vite 构建配置（含 API 代理）
│   ├── tailwind.config.js      # Tailwind CSS 自定义配置
│   ├── tsconfig.json           # TypeScript 编译选项
│   ├── index.html              # HTML 入口
│   │
│   └── src/
│       ├── main.tsx            # React 挂载入口
│       ├── App.tsx             # 主应用（状态机 + 所有业务逻辑）
│       ├── index.css           # Tailwind 基础样式引入
│       │
│       ├── types/
│       │   └── index.ts        # TypeScript 类型定义
│       │
│       ├── services/
│       │   └── api.ts          # API 客户端（含 SSE 流处理）
│       │
│       └── components/
│           ├── FormStep.tsx        # 需求收集表单
│           ├── MessageList.tsx     # 聊天消息列表
│           ├── ChatInput.tsx       # 消息输入框
│           └── DocumentReview.tsx  # 文档查看/编辑/优化
│
└── wiki/                       # 项目文档（本目录）
    ├── 00-overview.md
    ├── 01-architecture.md
    └── ...
```

## 各文件详细说明

### 后端

#### `backend/main.py`
FastAPI 应用入口。负责：
- 创建 `FastAPI` 实例，配置标题和版本
- 注册 CORS 中间件（从 `settings.cors_origins_list` 读取允许的源）
- 挂载两个 Router：`conversation_router`（前缀 `/api/conversation`）、`config_router`（前缀 `/api/config`）
- 提供 `GET /` 和 `GET /health` 健康检查接口

#### `backend/core/config.py`
使用 `pydantic-settings` 管理所有配置项，自动从 `.env` 文件加载。提供全局 `settings` 单例。

**关键配置项：**
- `anthropic_api_key` / `openai_api_key`：API 密钥
- `anthropic_base_url`：自定义 API 端点（代理/私有化部署）
- `default_llm_provider`：`anthropic` 或 `openai`
- `default_llm_model`：默认模型名称
- `cors_origins`：允许的跨域来源（逗号分隔）

#### `backend/core/questions_config.json`
表单问题的数据驱动配置。包含 `base_questions`（10 个，必填）和 `advanced_questions`（5 个，可选）。

每个问题字段：
```json
{
  "id": "product_name",
  "label": "产品名称",
  "question": "你的产品叫什么名字？",
  "description": "...",
  "type": "text | textarea | select | radio",
  "options": [...],
  "required": true,
  "advanced": false
}
```

#### `backend/core/prd_template.md`
PRD 格式参考模板。生成 PRD 时，若该文件存在且非空，AI 会将其作为格式参考（内容仍以对话为准）。可按需修改以定制 PRD 格式。

#### `backend/api/conversation.py`
主路由文件，定义 8 个 HTTP 端点（全部为流式或 JSON 响应）。只负责参数解析 + 调用 Service + 返回 StreamingResponse，不含业务逻辑。

#### `backend/api/config.py`
LLM 配置管理路由。支持查询当前配置、获取支持的 Provider 列表、运行时更新配置（切换模型/Provider/API Key）。

#### `backend/api/schemas.py`
所有 Pydantic 请求模型集中定义，包含 6 个模型类。路由文件从此处导入。

#### `backend/services/prompts.py`
所有 LLM Prompt 常量的唯一来源，共 5 个：
- `SYSTEM_PROMPT`：AI 对话角色设定
- `PRD_GENERATION_PROMPT`：PRD 生成模板
- `API_DOCS_GENERATION_PROMPT`：接口文档设计模板
- `PROMPTS_GENERATION_PROMPT`：AI 提示词套件生成模板
- `OPTIMIZE_DOCUMENT_PROMPT_TEMPLATE`：文档优化模板（含变量）

#### `backend/services/llm_factory.py`
`get_llm(temperature)` 工厂函数，根据 `settings.default_llm_provider` 返回对应的 LangChain LLM 实例。两个 Service 都从此导入，不重复配置。

#### `backend/services/conversation_service.py`
管理需求对话的全流程：
- `format_form_data()`：表单数据转可读文本
- `_build_lc_messages()`：前端消息格式 → LangChain 消息对象
- `_serialize_messages()`：LangChain 消息 → 前端格式
- `ConversationService.start_conversation_stream()`：开始对话
- `ConversationService.continue_conversation_stream()`：继续对话

#### `backend/services/document_service.py`
文档生成与优化的全部逻辑：
- `_load_prd_template()` / `_build_prd_prompt()`：处理 PRD 模板
- `DocumentService.generate_prd_stream()`：流式生成 PRD
- `DocumentService.generate_api_docs_stream()`：流式生成接口文档
- `DocumentService.generate_prompts_stream()`：流式生成提示词套件
- `DocumentService.optimize_document_stream()`：流式优化文档

### 前端

#### `frontend/src/App.tsx`
整个前端的核心，约 650 行。包含：
- 9 个 viewState 的完整状态机
- 所有 API 调用 handler
- localStorage 会话持久化逻辑
- 各阶段 UI 的渲染逻辑

**是整个前端的"大脑"，所有业务决策都在这里。**

#### `frontend/src/types/index.ts`
TypeScript 类型定义集中管理，包含：
- `ViewState`：9 种视图状态的联合类型
- `Message`：消息对象类型
- `DocType`、`DocAction`：文档操作相关类型
- `QuestionConfig`：表单问题配置类型
- 各 API 响应类型

#### `frontend/src/services/api.ts`
封装所有后端 API 调用。核心是 `readStream()` 函数，处理 SSE 流式响应的读取和解析。

#### `frontend/src/components/FormStep.tsx`
需求收集表单组件。支持 4 种输入类型（text/textarea/select/radio），表单验证只检查必填的基础问题。

#### `frontend/src/components/MessageList.tsx`
对话消息列表。用户消息右对齐，AI 消息左对齐并用 `react-markdown` 渲染。过滤掉系统消息和首条 Human 上下文消息，只显示真实对话内容。

#### `frontend/src/components/ChatInput.tsx`
消息输入框。Enter 发送，Shift+Enter 换行，自动扩展高度（上限 160px）。

#### `frontend/src/components/DocumentReview.tsx`
文档审核/编辑组件（PRD、接口文档、提示词三个阶段复用同一组件）。支持流式生成时只读、生成完成后可编辑、一键复制、AI 优化指令输入。
