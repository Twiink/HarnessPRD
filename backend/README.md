# HarnessPRD 后端

单机 FastAPI 服务，SQLite 保存会话、文档版本、任务和事件。应用只在 lifespan 启动时加载配置、迁移数据库并恢复任务。

## 启动

```bash
cd backend
uv sync
cp .env.example .env
# 编辑 .env，填写模型服务配置
uv run uvicorn --app-dir src apps.main:app --host 127.0.0.1 --port 8001
```

已有 `uvicorn main:app` 和开发启动脚本仍可使用。生产使用一个进程；代码重载仅用于开发。Uvicorn 命令行地址/端口由命令行决定；`uv run python main.py` 使用 `HOST` / `PORT` 配置。

## 配置与资源

配置来自进程环境变量和 `backend/.env`，环境变量优先。配置不可变，未知 `.env` 字段报错；`/api/config/current` 只返回脱敏信息，HTTP 不更新密钥或全局配置。密钥仅在建立模型客户端时解封，日志和错误脱敏。

| 配置 | 默认值/用途 |
| --- | --- |
| `DATABASE_PATH` | `backend/data/sessions.db` |
| `SQLITE_BUSY_TIMEOUT_MS` | 5000，SQLite 锁等待上限 |
| `JOB_MAX_CONCURRENCY` | 2，单进程最大同时生成数 |
| `JOB_SHUTDOWN_TIMEOUT` | 5 秒，等待执行器取消的上限 |
| `JOB_LEASE_SECONDS` | 30，每租约周期的三分之一续租 |
| `JOB_MAX_ATTEMPTS` | 3，包含首次执行与中断恢复 |
| `JOB_POLL_INTERVAL` | 0.1 秒，队列检查间隔 |
| `RESOURCES_DIR` | `backend/resources`，Prompt 与问题配置 |
| `SKILLS_ROOT` | 项目根目录 `skills/` |
| `SKILLS_CONFIG_PATH` | 项目根目录 `config/skills.yaml` |
| `MODELS_CONFIG_PATH` | `backend/config/models.yaml` |
| `CORS_ORIGINS` | 本机开发来源，以逗号分隔；可信内网需明确列出来源 |

资源路径可以使用绝对路径。默认数据库路径保持不变，既有会话与文档历史无需搬迁。编号迁移自动创建 `schema_migrations`，升级既有表，启用 WAL 与 busy timeout；不会删除已有数据库。升级前按常规方式备份 SQLite（运行中应使用 SQLite backup API）。高于程序支持版本的数据库拒绝启动。

## 模块边界

`src/apps/api/` 定义资源路由和严格请求模型；`services/` 编排用例；`db/repositories/` 负责 SQL。业务异常在 API 边界转换为统一响应：

```json
{"code":"JOB_CONFLICT","message":"该文档已有进行中的任务","request_id":"req_...","retryable":false}
```

`core/lifecycle.py` 持有每个应用的 Resources，包括配置、数据库、JobManager 和业务服务。依赖与请求上下文从 `app.state.resources` 获取资源，测试中的多个应用互相隔离。Agent 实现在 `agents/`；模型工厂、观测、能力和 token 预算在 `llm/`。

## API

正式资源路径直接使用 `/api`，OpenAPI 文档位于 `/docs`。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST / GET | `/api/sessions` | 新建 / 列出会话 |
| GET / PATCH / DELETE | `/api/sessions/{session_id}` | 读取 / 更新 / 删除会话 |
| POST | `/api/jobs` | 持久化提交生成/优化任务，返回 202 和 `job_id` |
| GET | `/api/jobs/{job_id}` | 查询状态、尝试次数和草稿 |
| POST | `/api/jobs/{job_id}/cancel` | 请求取消并返回任务状态 |
| GET | `/api/jobs/{job_id}/events?after=0&limit=500` | 分页读取持久化事件 |
| GET | `/api/jobs/{job_id}/stream` | SSE 历史回放与实时事件 |
| GET | `/api/sessions/{session_id}/documents` | 当前文档槽位 |
| GET | `/api/sessions/{session_id}/documents/{doc_type}/versions` | 文档历史 |
| POST | `/api/sessions/{session_id}/documents/{doc_type}/checkpoint` | 保存快照 |
| POST | `/api/sessions/{session_id}/documents/{doc_type}/restore` | 恢复，正文指定 `version_id` |
| GET | `/api/health/live` / `/api/health/ready` | 存活 / 数据库与任务运行时就绪 |
| GET | `/api/metrics` | 就绪状态、运行任务数、任务状态计数 |

`doc_type` 只能为 `prd`、`api-docs`、`prompts`。旧 `/api/session/*` 与 `/api/conversation/*` 是隐藏适配路由，与正式资源共用业务逻辑。文档备注、单版本内容、交付包导出继续可用。删除会话需要先取消其活跃任务，删除会级联清理关联数据库记录。

提交任务示例：

```json
{"session_id":"...","artifact":"prd","payload":{"requirements_summary":{"product_name":"示例","features":[{"name":"登录"}]}}},"idempotency_key":"request-001"}
```

幂等键也可由 `Idempotency-Key` 请求头提供；同一会话的相同键和请求返回同一个任务。相同键用于不同请求返回 409。生成与优化同一种文档的任务互相冲突，提交检查和写入在同一 SQLite 事务内完成。

## 任务恢复与 SSE

任务从 `queued` 进入 `running`，终态为 `succeeded`、`failed` 或 `cancelled`。执行者持有租约，并用执行者 ID 和尝试次数约束进度与最终写入。优雅关闭会取消并等待任务，将运行任务记录为 `interrupted`；下一次启动重新排队。非正常退出留下的有效租约到期后才恢复，避免抢占仍存活的执行者。超出尝试上限会明确失败并生成终态事件。关闭时先撤销执行所有权，再取消并等待执行器；若执行器持续拒绝停止，在配置的上限后明确报 `JOB_STOP_TIMEOUT`，保留任务句柄用于诊断和再次清理。已撤销所有权的执行器不能再提交文档。

中断恢复从生成起点重新执行，模型调用可能再次发生。最终文档版本按任务 ID 去重；任务成功、文档写入、会话镜像和终态事件在一个事务里提交。失败/取消不会覆盖既有成功文档，未完成草稿可从任务详情获取。

SSE 每条持久化事件含 `id`、`event` 和 JSON `data`；JSON 也包含 `job_id`、`sequence`、`created_at`。恢复连接时传 `Last-Event-ID` 或 `after`，只回放之后的事件。SQLite 操作在工作线程中执行，锁等待不阻塞事件循环；独立读取利用 WAL 不申请写锁。服务先订阅再回放，分页补齐全部终态事件；内存仅唤醒订阅者。终态事件之后发送 `data: [DONE]`。`started` 事件的空草稿表示新尝试开始，客户端应清空上次尝试的累积文本。

## 验证

```bash
cd backend
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
python -m compileall -q src
# 使用环境中已有的 mypy，未给项目添加依赖
mypy --config-file pyproject.toml src/apps
```

应用与运行时测试使用临时 SQLite 和确定性执行器，不调用付费模型服务。真实模型接入需要配置凭据后做人工生成验证。实施计划见 [后端优化计划](../docs/backend-optimization-plan.md)。
