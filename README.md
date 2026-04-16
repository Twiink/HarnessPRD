# Vibe Coding - 对话式需求收集平台

一个让普通人也能清晰描述软件需求的 AI 驱动工具。

## 功能特点

- 🎯 对话式双向讨论（非单向追问）
- 📋 表单收集 → AI 对话式细化 → 输出 Claude Code 可懂的 PRD
- 🔧 高级选项给程序员用
- 👥 人类审核后继续反馈迭代
- 🌐 网页端，开箱即用
- ⚙️ API KEY 可配置化
- 📝 问题配置化

## 技术栈

- **后端**: Python + FastAPI + LangChain
- **前端**: React + TypeScript
- **部署**: 支持 macOS 本地运行

## 快速开始

### 1. 后端设置

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 文件，填入你的 API KEY
uvicorn main:app --reload
```

### 2. 前端设置

```bash
cd frontend
npm install
npm run dev
```

## API KEY 配置

在 `backend/.env` 文件中配置：

```
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key
```

## 项目结构

```
vibecoding/
├── backend/              # 后端服务
│   ├── api/              # API 路由
│   ├── core/             # 核心配置
│   ├── services/         # 业务逻辑
│   └── main.py          # FastAPI 应用入口
├── frontend/             # 前端应用
│   ├── src/
│   │   ├── components/   # React 组件
│   │   ├── services/     # API 调用
│   │   └── App.tsx       # 主应用
│   └── package.json
└── README.md
```

## 使用流程

1. 用户打开网页
2. 填写基本信息（可选）
3. 与 AI 对话式讨论需求
4. AI 提问 10 个基础问题
5. 用户回答并讨论
6. 生成 Claude Code 可读的 PRD
7. 人类审核后继续反馈迭代

## 基础问题

AI 会提问以下 10 个基础问题：
1. 产品名称
2. 一句话解决的问题
3. 目标用户
4. MVP 必备 3-5 功能
5. v2 功能
6. 页面数量
7. 页面风格
8. 网页/小程序
9. 是否登录
10. 是否数据库