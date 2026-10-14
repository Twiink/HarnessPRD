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
uv sync --project backend
cp backend/.env.example backend/.env
# 编辑 .env 文件，填入你的 API KEY
./scripts/dev-backend.sh
```

### 2. 前端设置

```bash
cd frontend
npm install
../scripts/dev-frontend.sh
```

也可以从项目根目录运行 `./start.sh` 同时启动前后端。

### 开发工具

- 后端依赖由 `backend/pyproject.toml` 和 `backend/uv.lock` 管理；`backend/requirements.txt` 是供旧 pip/Docker 环境使用的锁定导出。修改依赖后运行 `uv export --project backend --locked --no-dev --no-hashes --format requirements.txt --output-file backend/requirements.txt` 更新它。
- 后端质量检查：`uv run --project backend ruff check backend`；格式化：`uv run --project backend ruff format backend`；运行测试：`uv run --project backend pytest`。
- 首次使用时运行 `sh scripts/install-git-hooks.sh` 安装仓库 Git hooks。
- PyCharm 中可直接运行共享配置 `Backend`、`Frontend`。

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
