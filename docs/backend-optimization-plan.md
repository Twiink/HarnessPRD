# HarnessPRD 后端工程化优化计划

## 边界与约束

参考 `/Users/mac/ProjectStation/AgentTemplate` 的生命周期、资源容器、仓储与任务恢复设计，保持单机 SQLite、本机或可信内网部署。仅修改后端。API 目录直接使用 `api/`，正式接口统一 `/api/...`，不增加版本段。保留现有数据、文档历史、恢复、备注、需求基线与交付导出；不新增依赖。

## 目录与依赖方向

```text
backend/
├── src/apps/
│   ├── main.py
│   ├── api/             # 资源路由、请求模型、依赖、错误转换
│   ├── core/            # 配置、生命周期、日志、领域错误、请求上下文
│   ├── db/              # 连接、编号迁移、repositories/
│   ├── domain/          # sessions、documents、jobs 契约
│   ├── runtime/         # job_manager、job_executor、recovery、events
│   ├── llm/             # factory、registry、metrics、token_budget
│   ├── agents/          # Writer 与各类 Review Agent
│   └── services/        # 业务用例编排与纯业务逻辑
├── config/
├── resources/
└── tests/
```

Service 不拼接 SQL，不依赖 FastAPI 异常。数据库读写统一进入 Repository，跨表写入加入同一事务。保留旧 HTTP 路由作为薄适配层，业务和运行时只保留一份实现。

## 实施步骤

1. 固定现有行为：运行原有 40 项测试，为生命周期、迁移、任务恢复与协议补充回归测试。
2. 迁移到 `src/apps`；引入 `create_app()`、lifespan、`app.state.resources`。导入不创建数据库、不启动任务；关闭时取消并等待后台任务。增加存活、就绪、基础指标接口。
3. 配置使用 Pydantic v2 `SettingsConfigDict`、`SecretStr`、拒绝未知字段；通过配置注入模型注册表、Prompt、Skill 路径。HTTP 不再修改密钥或进程级配置，响应、日志与错误脱敏；收紧 CORS。
4. SQLite 使用 WAL、busy timeout、统一事务、编号迁移和 `schema_migrations`。保留既有数据；Session、Document、Job、Event 使用独立 Repository。
5. JobManager 管理提交、并发、租约、重试、取消、关闭和恢复；API 不直接启动任务。任务增加 `attempt_count`、`worker_id`、`lease_until`、`started_at`、`finished_at`、`error_code`、`cancel_requested`、`idempotency_key`。
6. 状态机为 `pending -> queued -> running -> succeeded/failed/cancelled`，中断任务 `interrupted -> queued`。过期租约可恢复；限制重试次数；最终状态、文档写入、Session 镜像和终态事件原子提交。任务重试不会重复生成文档版本。
7. 持久化 `job_events(job_id, sequence, event_type, payload_json, created_at)`。SSE 从数据库回放后等待新事件，支持事件 ID 与 `Last-Event-ID`，解决历史回放与实时订阅之间的竞态。
8. 按资源拆分 API 模型，默认拒绝未知字段；Enum/Literal 限制任务、文档、状态。统一错误包含 `code`、`message`、`request_id`、`retryable`。
9. Agent 进入 `agents/`，LLM 工厂、观测、模型能力、token 预算独立；移除跨 Service 私有函数调用。Prompt/Skill 路径可配置，纯解析与质量门禁继续独立测试。
10. 完成后端运行文档、格式化、静态与类型检查、恢复/并发/幂等/取消/SSE 测试。

## 正式接口

```text
POST   /api/sessions
GET    /api/sessions
GET    /api/sessions/{session_id}
PATCH  /api/sessions/{session_id}
DELETE /api/sessions/{session_id}
POST   /api/jobs
GET    /api/jobs/{job_id}
POST   /api/jobs/{job_id}/cancel
GET    /api/jobs/{job_id}/events
GET    /api/jobs/{job_id}/stream
GET    /api/sessions/{session_id}/documents
GET    /api/sessions/{session_id}/documents/{doc_type}/versions
POST   /api/sessions/{session_id}/documents/{doc_type}/checkpoint
POST   /api/sessions/{session_id}/documents/{doc_type}/restore
```

## 验收

- 应用导入无数据库/任务副作用，资源按应用隔离。
- 重启后的未完成任务恢复执行或明确失败，取消与关闭没有遗留后台任务。
- 迁移保留已有 Session、Job、Document 数据，重复迁移幂等。
- 并发提交可防止同一文档的冲突任务，幂等键重放不会新建任务。
- 最终写入原子且幂等，同一任务不产生重复文档版本。
- SSE 事件有持久化 ID，断线可补发，并正确结束终态流。
- 所有正式路由和目录均无版本段，旧路由只做适配。
- 配置、请求校验、错误、日志均不泄露密钥。
- 原有测试和新增回归、Ruff lint/format、类型检查通过。

## 基线

2026-10-14：`uv run pytest -q` 为 40 passed，存在一项 Pydantic 配置弃用警告。已有 `.gitignore` 改动保持原样。

## 实施结果

2026-10-14：步骤 1–10 已完成。实现位于 `backend/src/apps`，Prompt、模板和问题配置位于 `backend/resources`；原数据库默认路径保持 `backend/data/sessions.db`。后端开发脚本已适配新入口，`backend/main.py` 保留启动兼容入口。

- `create_app()` 与 lifespan 装配应用级 Resources；导入不解析配置、不连接数据库、不启动任务。多个应用的配置和数据库互相隔离。
- SQLite 编号迁移、WAL、busy timeout、四类 Repository 已落地。既有表和文档历史保留，旧 `completed` 任务迁移为 `succeeded`；历史终态任务补充持久化快照事件。
- 任务提交、文档冲突与幂等键检查使用事务；进度和最终化受执行者 ID、尝试次数与租约约束。任务结果、文档版本、会话镜像和终态事件原子提交。
- 支持优雅关闭后的中断恢复、进程非正常退出后的租约恢复、次数受限的传输错误重试、取消，以及并发任务的会话镜像同步。
- SQLite 锁等待在工作线程中执行，读取不申请写锁；续租失败停止旧执行者。关闭先撤销所有权再等待取消，默认等待上限 `JOB_SHUTDOWN_TIMEOUT=5` 秒；执行器持续拒绝停止时明确报告 `JOB_STOP_TIMEOUT` 并保留句柄供清理。
- SSE 支持持久化序号、事件分页、`Last-Event-ID`、历史回放和终态补发；内存只用于唤醒，终态补发会读取全部分页。
- 正式路由直接使用 `/api/...`。旧会话/对话路径作为隐藏适配；任务提交返回 202，成功状态为 `succeeded`，配置更新接口返回 405。
- 配置不可变、拒绝未知字段，密钥使用 `SecretStr`；错误与日志脱敏。Agent、模型工厂、观测、能力、Token 预算和公共消息构建已分离。

验收结果：

| 检查 | 结果 |
| --- | --- |
| 后端完整测试 | 152 passed |
| Ruff 规则检查 | 通过 |
| Ruff 格式检查 | 109 个文件通过 |
| Mypy | 67 个源文件通过 |
| Python 编译、Shell 语法、Git 空白检查 | 通过 |
| 依赖锁文件一致性 | 通过，未新增依赖 |
| 真实进程直接退出后的恢复 | 通过，事件保留且最终文档只写一版 |
| SQLite 锁冲突、取消、终态分页复现 | 回归测试通过 |

模型流程使用确定性替身验证，未调用真实模型供应商。当前工作区没有运行中的 SQLite 数据库，旧库迁移通过包含历史任务、重复关联版本和孤立任务的测试数据验证。中断恢复采用重新生成的方式，可能再次产生模型调用。

运行配置、接口合同和恢复语义见 `backend/README.md`。
