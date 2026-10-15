# ReqFlow

把一个软件想法整理成可以交付开发的文档：结构化需求 → 澄清对话 → PRD → 接口文档 → 开发提示词。

ReqFlow 面向产品经理和需求分析师。每一步的产物都可以审阅、编辑和回溯版本；PRD 确认为需求基线后才生成下游文档，基线变化时下游文档会被标记为待同步。

## 功能

- 三种起点：从零填写结构化需求、导入已有 PRD，或导入 PRD 和接口文档。
- 结构化需求表：产品、用户、功能清单、页面、技术约束和项目范围。
- 需求澄清：AI 针对缺失信息逐项追问，回答在生成 PRD 前以差异形式回填，由你确认。
- 文档生成与审查：生成 PRD、接口文档和开发提示词，附带审查意见，可按意见优化或直接编辑。
- 需求基线：确认 PRD 后解锁下游文档；修改 PRD 会让基线失效。
- 版本记录：每次生成、优化和编辑都会留下版本，可查看、备注和恢复。
- 方案管理：方案自动保存，可继续、删除，并导出完整交付包。
- 模型、追问问题和生成规范均可配置，记录每次生成的耗时与用量。

## 界面

界面采用工程图纸风格：钢灰底色、细线图框、制图蓝作为唯一强调色。顶栏按 A–E 编号展示五个环节，文档页右侧是版本记录和审查批注。设计令牌在 `frontend/tailwind.config.js`，公共组件类（`sheet`、`btn-primary` 等）在 `frontend/src/index.css`，产品定位记录在 `PRODUCT.md`。

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

1. 在首页选择起点：从零整理需求，或导入已有文档。
2. 回答 AI 的追问，核对回填到需求里的改动。
3. 生成并审阅 PRD，确认为需求基线。
4. 生成、审阅和优化接口文档与开发提示词。
5. 按需保存快照、恢复版本，并导出交付包。

首页位于 `/`，方案列表位于 `/projects`，已保存方案位于 `/projects/:id`。

## 项目结构

```text
HarnessPRD/
├── backend/
│   ├── src/apps/              # API、业务、仓储、Agent/LLM 与任务运行时
│   ├── config/                # 模型能力注册表
│   ├── resources/             # Prompt、问题与文档模板
│   ├── tests/                 # 后端测试
│   └── main.py                # 兼容启动入口
├── frontend/src/
│   ├── components/workspace/ # 顶栏、工作台录入与澄清组件
│   ├── components/           # 文档、版本记录、方案列表等组件
│   ├── index.css             # 全局样式与公共组件类
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
uv run --project backend pytest -c backend/pyproject.toml backend/tests
npm --prefix frontend run build
```

后端架构、任务恢复与 API 说明见 [backend/README.md](backend/README.md)。

后端按资源 API、应用用例、领域规则和基础设施分层；模块边界由 AST 测试保护。故障诊断、SQLite 在线备份及恢复步骤见 [后端运行手册](docs/backend-operations.md)。GitHub Actions 自动执行锁文件、格式、静态规则、全量测试与依赖边界检查。

后端依赖由 `backend/pyproject.toml` 和 `backend/uv.lock` 管理。`backend/requirements.txt` 是供 pip 和 Docker 环境使用的锁定导出；修改依赖后运行：

```bash
uv export --project backend --locked --no-dev --no-hashes --format requirements.txt --output-file backend/requirements.txt
```

首次开发时运行 `sh scripts/install-git-hooks.sh` 安装仓库 Git hooks。PyCharm 可使用共享运行配置 `Backend` 和 `Frontend`。
