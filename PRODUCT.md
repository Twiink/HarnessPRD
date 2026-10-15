# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

产品经理与需求分析师。他们手上有一个软件想法或一份不完整的需求，需要在交给开发团队之前，把它整理成结构清晰、可评审、可追溯的文档。使用场景以桌面浏览器为主，单人长时间专注工作。

## Product Purpose

ReqFlow 把零散的软件需求整理为完整的开发交付物：结构化需求 → AI 澄清对话 → PRD → 接口文档 → 开发提示词。成功的标志是：用户确认的 PRD 基线与下游文档保持一致，可以直接导出交付包交给开发。

## Positioning

不是一次性生成文档，而是一条有基线的需求流水线：每一步产物都可审阅、可回溯历史版本，PRD 基线变化时下游文档会被标记为待同步。

## Operating Context

- 三种起点：从零填写结构化需求、导入已有 PRD、导入 PRD + 接口文档。
- 澄清对话会把确认结果回填到结构化摘要，用户需要审阅差异后才生效。
- 文档支持反馈优化、人工编辑、快照与历史恢复。
- 方案（项目）可保存、加载、删除，并导出完整交付包。
- 无登录注册，单用户本地/内网使用。

## Capabilities and Constraints

- 前端：React 18、TypeScript、Vite、Tailwind CSS 3、lucide-react 图标、react-markdown。
- 后端：FastAPI + LangChain + SQLite，模型服务通过 `backend/.env` 配置。
- 路由：`/` 工作台，`/projects` 方案列表，`/projects/:id` 已保存方案。
- 界面语言为简体中文。

## Brand Commitments

- 产品名称：ReqFlow（替代旧名 "Vibe Coding"）。
- 期望感受：现代、高效、智能；避免明显的 AI 生成痕迹。
- 所有前端页面风格统一。

## Evidence on Hand

无真实客户、用户评价或指标数据，界面中不得编造。

## Product Principles

1. 流程可见：用户始终知道自己处在哪一步、下一步是什么。
2. 文档优先：PRD 与接口文档是主角，界面为阅读和编辑让路。
3. 确认后才生效：AI 的改动以差异呈现，由用户决定。
4. 可追溯：基线、版本、历史清晰可查。
