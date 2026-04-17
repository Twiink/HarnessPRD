# VibeCoding Wiki 索引

## 文档列表

| 文档 | 内容摘要 |
|------|---------|
| [00-overview.md](./00-overview.md) | 项目概览：是什么、解决什么问题、功能一览 |
| [01-architecture.md](./01-architecture.md) | 架构设计：整体架构图、分层说明、核心设计决策 |
| [02-tech-stack.md](./02-tech-stack.md) | 技术栈说明：前后端依赖、选型理由 |
| [03-directory-structure.md](./03-directory-structure.md) | 目录结构与文件说明：每个文件的职责 |
| [04-backend-guide.md](./04-backend-guide.md) | 后端开发指南：SSE 实现、LLM 调用、添加新接口 |
| [05-frontend-guide.md](./05-frontend-guide.md) | 前端开发指南：状态机、组件说明、会话持久化 |
| [06-api-reference.md](./06-api-reference.md) | API 接口文档：所有接口的请求/响应格式 |
| [07-workflow.md](./07-workflow.md) | 核心工作流：用户旅程各阶段详解 |
| [08-prompts-design.md](./08-prompts-design.md) | Prompt 设计说明：5 个核心 Prompt 的设计思路 |
| [09-configuration.md](./09-configuration.md) | 配置说明：环境变量、模型选择、自定义表单/模板 |
| [10-deployment.md](./10-deployment.md) | 部署与运维：本地开发、Nginx、Docker、进程管理 |
| [11-developer-guide.md](./11-developer-guide.md) | 开发者指南：常见任务、代码规范、扩展方向、FAQ |
| [skills/README.md](./skills/README.md) | Skills 专题：skill 包设计、schema、回填、模型兼容、工作台流程 |
| [v2record/README.md](./v2record/README.md) | `/v2` 开发记录：开发过程、踩坑、问题定位与复盘 |

## 快速导航

### 我想了解这个项目是什么
→ [00-overview.md](./00-overview.md)

### 我想理解整体架构
→ [01-architecture.md](./01-architecture.md)

### 我想理解新的 Skills 体系
→ [skills/README.md](./skills/README.md)

### 我想看 `/v2` 是怎么一步步做出来的
→ [v2record/README.md](./v2record/README.md)

### 我想快速启动项目
→ [10-deployment.md](./10-deployment.md#本地开发一键启动)

### 我想调用 API
→ [06-api-reference.md](./06-api-reference.md)

### 我想修改 AI 的 Prompt
→ [08-prompts-design.md](./08-prompts-design.md)

### 我想添加新功能
→ [11-developer-guide.md](./11-developer-guide.md#常见开发任务)

### 我想配置不同的 LLM
→ [09-configuration.md](./09-configuration.md)

### 我想部署到生产环境
→ [10-deployment.md](./10-deployment.md#生产部署)

### 我遇到了报错
→ [11-developer-guide.md](./11-developer-guide.md#常见问题)
→ [04-backend-guide.md](./04-backend-guide.md#常见问题)

## 项目结构速览

```
vibecoding/
├── backend/          # FastAPI 后端（Python）
│   ├── api/          # 路由层
│   ├── services/     # 业务逻辑层
│   └── core/         # 配置与静态资源
├── frontend/         # React + TypeScript 前端
│   └── src/
│       ├── App.tsx           # 主应用（状态机）
│       ├── components/       # UI 组件
│       ├── services/api.ts   # API 客户端
│       └── types/            # TypeScript 类型
├── wiki/             # 本文档目录
└── start.sh          # 一键启动脚本
```

## 核心概念

- **ViewState 状态机**：9 个状态驱动前端 UI 切换（见 [05-frontend-guide.md](./05-frontend-guide.md)）
- **SSE 流式响应**：所有 LLM 调用实时流式输出（见 [04-backend-guide.md](./04-backend-guide.md#sse-流式响应原理)）
- **后端无状态**：对话历史由前端 localStorage 维护（见 [01-architecture.md](./01-architecture.md)）
- **Prompt 集中管理**：所有 AI 指令在 `services/prompts.py`（见 [08-prompts-design.md](./08-prompts-design.md)）
