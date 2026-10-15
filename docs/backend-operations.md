# 后端运行手册

## 启动与资源

使用单进程：`uv run --project backend uvicorn --app-dir backend/src apps.main:app --host 127.0.0.1 --port 8001`。开发脚本仍使用 reload。服务停止时等待后台任务和模型调用关闭；不要使用多 worker 绕过单机容量限制。

启动先验证 Prompt、PRD 模板、问题配置、模型能力注册表及 Skill 绑定和必需文件，随后迁移数据库并恢复任务。可选 example 缺失只记录警告。资源错误使用 `INVALID_RESOURCES` 拒绝启动，不会把无法生成的服务报告为 ready。启动校验不连接模型供应商；凭据和供应商可用性仍由实际调用验证。

## 容量与超时

| 环境变量 | 默认值 | 行为 |
| --- | --- | --- |
| `JOB_MAX_CONCURRENCY` | 2 | 同时运行的 Job 数及应用共享的模型调用容量 |
| `JOB_MAX_QUEUED` | 100 | 等待执行的任务上限，幂等重放不占新名额 |
| `JOB_RUN_TIMEOUT` | 1200 秒 | 单次任务尝试和即时 SSE 用例的执行总时限 |
| `LLM_CALL_TIMEOUT` | 180 秒 | 普通模型调用、模型容量等待的时限；SDK 显式连接/读取超时 |
| `LLM_STREAM_IDLE_TIMEOUT` | 120 秒 | 等待下一个模型流片段的时限 |
| `JOB_MAX_ATTEMPTS` | 3 | 包括首次执行在内的最大尝试数 |
| `JOB_SHUTDOWN_TIMEOUT` | 5 秒 | 每个运行时关闭的有界等待 |
| `JOB_HEALTH_FAILURE_SECONDS` | 30 秒 | 持续调度失败达到此时长后就绪降级 |
| `JOB_PROGRESS_FLUSH_INTERVAL` | 0.25 秒 | 增量进度的最长正常合并间隔 |
| `JOB_PROGRESS_FLUSH_BYTES` | 4096 | 达到此字节数立即写入进度 |

首个可见片段、阶段转换及终态立即刷新。合并后的事件保持连续序号，仍可通过 `Last-Event-ID` 或 `after` 回放；历史事件不会自动删除。非正常退出可能丢失最后一小段尚未刷盘的进度，任务按既有恢复规则重新执行。

超时先撤销任务执行所有权再取消，迟到输出无法落成文档。执行器或供应商若拒绝取消，会继续占有相应容量；关闭超时明确报错并保留诊断信息。SDK 关闭隐式重试，Job 使用统一的次数限制；对话即时调用失败直接返回错误，由用户决定重试。

## 健康状态与故障

- `/api/health/live` 表示服务进程响应；`/api/health/ready` 检查数据库结构与任务调度健康。探针不执行付费调用，也不测试供应商在线状态。
- `/api/metrics` 的 `runtime` 包含连续失败、最近成功调度、最后错误类型及超时执行器信息。短暂锁等待不会立即让探针抖动；持续故障超过阈值返回 503，恢复调度后自动转绿。
- `DB_BUSY`：SQLite 锁竞争，可重试 503，并带 `Retry-After`。检查是否有外部工具长时间持有写事务。
- `QUEUE_FULL` / `LLM_BUSY`：等待已有工作完成后重试；相同幂等键重放不会额外创建任务。
- `JOB_RUN_TIMEOUT` / `LLM_CALL_TIMEOUT` / `LLM_STREAM_IDLE_TIMEOUT`：检查供应商延迟及模型输出规模。草稿和事件仍保留，失败不覆盖成功文档。
- `JOB_STOP_TIMEOUT` / `LLM_STOP_TIMEOUT`：底层调用未响应取消，检查运行时日志；退出并重启进程前保存诊断。不要因客户端断开而假定任务已停止。

日志使用 request_id、session_id、job_id 定位，异常堆栈经过凭证脱敏。排障时不要把密钥写入 issue 或命令行。

## 文档与来源

基线绑定实际 PRD 版本、编号和正文 SHA-256；兼容浏览器的前 16 位 hash。普通保存、恢复、快照及优化改变正文时，旧确认和旧审查结论失效；备注变更保留结论。已有正文显式清空返回 422，省略字段保留原文。

生成提交时固定真实输入来源与 hash；排队或生成期间上游内容改变，不会重写来源记录。旧记录没有 hash 时保留原版本号判断。交付 ZIP 从同一只读快照收集材料，释放事务后压缩，未评估或过期的结论在交付信息中明确展示。

## SQLite 在线备份

在项目根目录执行，目标必须是新路径：

```bash
uv run --project backend python scripts/sqlite-backup.py backup backend/data/sessions.db /absolute/path/backups/sessions-20261015.db
```

脚本使用 SQLite backup API，包含 WAL 中已提交数据，执行完整性检查后原子发布。不要在运行中仅复制 `.db` 文件而遗漏 WAL。数据库暂不可读超过 30 秒时失败，可通过 `--timeout` 调整；失败不发布半成品，也不会覆盖目标。

## 恢复演练

1. 停止服务，保留当前数据库及关联文件作为回退副本。
2. 将备份恢复到一个新的数据库路径：

```bash
uv run --project backend python scripts/sqlite-backup.py restore /absolute/path/backups/sessions-20261015.db /absolute/path/recovery/sessions.db
```

3. 将 `DATABASE_PATH` 指向新路径后启动。检查 ready、会话列表、文档历史及任务事件，再恢复正常使用。高于程序支持版本的数据库会拒绝启动。
4. 在线备份可能包含备份时仍运行的任务；恢复后遵守租约到期和重试上限，可能再次调用模型。演练环境应使用本地替身执行器，或先取消活跃任务再制作演练备份。

本地测试验证 WAL 在线备份、恢复、完整性校验及拒绝覆盖。生产备份目标、保存周期和异地保管由部署环境配置。
