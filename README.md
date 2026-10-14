# Vibe Coding — 需求与文档工作台

一个帮助用户清晰描述软件需求、生成完整开发文档的 AI 工具。

## 功能

- 结构化需求表单：整理产品、用户、完整功能清单、页面、技术约束和项目范围。
- 需求澄清：通过双向对话补齐需求，并将确认结果回填到结构化摘要。
- 多种录入方式：填写需求、导入已有 PRD，或导入提示词与相关文档。
- 文档生成与审查：生成 PRD、接口文档和开发提示词，支持反馈优化与人工编辑。
- 需求基线：确认 PRD 后生成下游文档，需求变化时提示同步。
- 文档历史：保存快照、预览、备注和恢复历史记录。
- 方案管理：保存、加载和删除方案，恢复生成进度，导出完整交付包。
- 可配置模型、问题和生成规范，记录生成过程与用量。

## 技术栈

- 后端：Python、FastAPI、LangChain、SQLite。
- 前端：React、TypeScript、Vite、Tailwind CSS。
- 开发工具：uv、Ruff、pytest、npm。

## 快速开始

```bash
uv sync --project backend
cp backend/.env.example backend/.env
# 编辑 backend/.env，配置模型服务与 API Key
cd frontend
npm install
cd ..
./start.sh
```

也可以分别运行 `./scripts/dev-backend.sh` 和 `./scripts/dev-frontend.sh`。

模型服务通过 `backend/.env` 配置，支持 `ANTHROPIC_API_KEY`、`OPENAI_API_KEY` 及相应服务地址。完整配置项见 `backend/.env.example`。

## 使用流程

1. 在首页选择录入方式，填写完整需求或导入已有文档。
2. 与 AI 澄清需求，确认结构化摘要。
3. 生成并审阅 PRD，确认需求基线。
4. 生成、审阅和优化接口文档与开发提示词。
5. 按需保存快照、恢复历史记录，并导出交付包。

首页位于 `/`，方案列表位于 `/projects`，已保存方案位于 `/projects/:id`。

## 项目结构

```text
HarnessPRD/
├── backend/
│   ├── api/                  # 会话、文档、生成任务与配置接口
│   ├── core/                 # 应用配置、问题与文档模板
│   ├── services/             # 需求澄清、生成、审查、历史与导出
│   ├── tests/                # 后端测试
│   └── main.py               # 后端入口
├── frontend/src/
│   ├── components/workspace/ # 工作台录入与澄清组件
│   ├── components/           # 文档、历史、方案列表等组件
│   ├── services/             # API 调用与会话持久化
│   ├── hooks/                # 生成任务、观测与文档历史
│   ├── utils/                # 需求转换与流程状态
│   └── App.tsx               # 应用入口
├── skills/                   # PRD、接口文档与提示词生成规范
├── config/                   # 生成规范注册表
├── scripts/                  # 开发启动与 Git hooks
└── start.sh                  # 同时启动前后端
```

## 开发与验证

```bash
uv run --project backend ruff check backend
uv run --project backend pytest
npm --prefix frontend run build
```

后端依赖由 `backend/pyproject.toml` 和 `backend/uv.lock` 管理。`backend/requirements.txt` 是供 pip 和 Docker 环境使用的锁定导出；修改依赖后运行：

```bash
uv export --project backend --locked --no-dev --no-hashes --format requirements.txt --output-file backend/requirements.txt
```

首次开发时运行 `sh scripts/install-git-hooks.sh` 安装仓库 Git hooks。PyCharm 可使用共享运行配置 `Backend` 和 `Frontend`。
