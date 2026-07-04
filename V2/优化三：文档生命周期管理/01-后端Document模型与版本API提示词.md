# 后端 Document 模型与版本 API 提示词

点击此处可复制本篇提示词

文档生命周期管理的后端基础，是为 PRD、接口文档、提示词建立「文档槽位 + 版本链」数据模型，并暴露查询、checkpoint、restore 等 HTTP 接口。核心原则：**历史版本只追加、不可原地修改**；**current 版本**由 Job 完成与 Session 自动保存更新（本篇先建表与 API，写入链路见 02 篇）。

## 使用场景

这份提示词用于在 harnessprd 项目 `backend/` 实现 Document 模型与版本 API。只改后端，不动前端。

**前置条件**：`project_sessions`、`generation_jobs`、Session save API 已存在。

**现状问题：** `session_data` 中 `prdContent`、`apiDocsContent`、`promptsContent` 为三个字符串字段，生成或优化直接覆盖，无版本号、无历史列表，也无法把 `run_summary`、`review` 持久化到某一稿上。

**本篇交付范围：**

```
SQLite 表 documents / document_versions
  → document_version_service（槽位与版本 CRUD）
  → api/documents.py（6 个 HTTP 接口）
```

Job 完成写入、Session debounce 同步、老数据迁移见 02 篇；前端侧栏见 03 篇。

**本次不做：**

- 改造 `job_runner` 在 Job 完成时写版本
- 改造 `POST /api/session/save` 同步 current
- 老 Session 数据迁移
- 定稿、diff 接口
- 删除 `session_data` 中的 `prdContent` 等字段
- Celery 或新中间件

### 一、功能目标

- 新增 SQLite 表：`documents`、`document_versions`
- 新增 `services/document_version_service.py`：文档槽位与版本的 CRUD
- 新增 `api/documents.py`：6 个 HTTP 接口
- 在 `init_db()` 中建表
- `doc_type` 枚举：`prd`、`api-docs`、`prompts`

### 二、代码结构

```
backend/
  db/
    database.py                      # 改造：CREATE documents / document_versions
  services/
    document_version_service.py      # 新建：核心业务
  api/
    documents.py                     # 新建：路由
  main.py                            # 改造：注册 documents router
```

### 三、数据模型

#### 表 `documents`

每个 Session、每种 doc_type 唯一一行。

```sql
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    current_version_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(session_id, doc_type)
);
CREATE INDEX IF NOT EXISTS idx_documents_session ON documents(session_id);
```

| 字段 | 说明 |
|------|------|
| `id` | UUID |
| `session_id` | 关联 `project_sessions.id` |
| `doc_type` | `prd`、`api-docs`、`prompts` |
| `current_version_id` | 指向 `document_versions.id`；尚未生成时为空 |

#### 表 `document_versions`

每条记录对应一个版本快照；历史行只 INSERT，不 UPDATE 正文。

```sql
CREATE TABLE IF NOT EXISTS document_versions (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL,
    source_job_id TEXT,
    parent_version_id TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(document_id, version_no)
);
CREATE INDEX IF NOT EXISTS idx_document_versions_document ON document_versions(document_id);
```

| 字段 | 说明 |
|------|------|
| `version_no` | 从 1 递增，按 document 独立编号 |
| `content` | Markdown 正文 |
| `source_kind` | 见第四节枚举 |
| `source_job_id` | 可选，关联 `generation_jobs.id` |
| `parent_version_id` | checkpoint 时指向上一个 current；首版为空 |
| `metadata_json` | JSON，存 `run_summary`、`review`、`change_note` 等 |

本阶段不做定稿状态。当前生效版本以 `documents.current_version_id` 为准。

### 四、`source_kind` 枚举

```python
class VersionSourceKind(str, Enum):
    GENERATE = "generate"       # 首次或整份生成 Job 完成
    OPTIMIZE = "optimize"       # 优化 Job 完成，更新 current，不升 version_no
    AUTO_SAVE = "auto_save"     # Session save、debounce 同步 current
    CHECKPOINT = "checkpoint"   # 用户「保存为新版本」
    RESTORE = "restore"         # 用户「恢复此版本」，基于历史正文升新版
    IMPORT = "import"           # 老数据迁移导入
```

写入规则：

| source_kind | 行为 |
|-------------|------|
| `GENERATE`（首次） | INSERT v1，设为 current |
| `GENERATE`（再次整份生成） | INSERT 新版，切换 current，旧版保留 |
| `CHECKPOINT`、`RESTORE` | INSERT 新版，切换 current |
| `OPTIMIZE`、`AUTO_SAVE` | 仅 UPDATE current 行的 `content` 与 `metadata_json`，`version_no` 不变 |

### 五、Service 核心方法

在 `document_version_service.py` 中实现，命名可微调，职责保持一致：

| 方法 | 职责 |
|------|------|
| `ensure_document(session_id, doc_type) -> document` | 无则创建 documents 行 |
| `get_documents_by_session(session_id) -> list` | 三种槽位摘要 |
| `list_versions(session_id, doc_type) -> list` | 版本列表，按 `version_no` 降序 |
| `get_version(session_id, doc_type, version_id) -> version` | 单版详情 |
| `get_current_version(session_id, doc_type) -> version \| None` | 读 current |
| `create_initial_version(...)` | 首版 v1 |
| `update_current_content(...)` | 更新 current 正文，不升号（优化、自动保存） |
| `append_generated_version(...)` | 整份生成完成且已有 current 时升新版 |
| `checkpoint(...)` | 保存为新版本：复制 current 为新 version_no，切换 current |
| `restore_version(...)` | 恢复历史版本：以指定历史版正文 INSERT 新版，切换 current |
| `update_version_note(...)` | 更新某一历史或 current 版本的 `metadata.change_note`，不改正文、不升版 |

**`checkpoint` 逻辑：**

1. `ensure_document`
2. 取 current；若无 current 且请求体带了 `content`，先 `create_initial_version`
3. 新 `version_no = max(version_no) + 1`
4. `parent_version_id` 设为旧 current 的 id
5. INSERT 新版本，正文取参数传入或旧 current 的 content
6. UPDATE `documents.current_version_id`
7. 返回新版本摘要

Phase 1 单用户单 Session，SQLite 单写即可；`checkpoint`、`restore_version` 与 `update_current` 放同一事务。

**`restore_version` 逻辑：**

1. `ensure_document`
2. 校验 `version_id` 属于该 document，且**不是** current
3. 读取该历史版 `content` 与 `metadata_json`
4. 新 `version_no = max(version_no) + 1`
5. `parent_version_id` 设为旧 current 的 id
6. INSERT 新版本：`source_kind=restore`，正文取历史版；`metadata` 写入 `restored_from_version_id`、`restored_from_version_no`，并合并历史版 metadata（如 `review`）
7. UPDATE `documents.current_version_id`
8. 返回新版本摘要与 `content`（供 Session 镜像同步）

**示例：** current 为 v2，恢复 v1 → 产生 v3（正文同 v1），v1、v2 仍在列表且内容不变。

### 六、HTTP API

路由前缀：`/api/session/{session_id}/documents`。

#### 1. `GET /api/session/{session_id}/documents`

返回三种 `doc_type` 的摘要。尚无版本时 `current_version_id` 为 null。

```json
{
  "items": [
    {
      "doc_type": "prd",
      "document_id": "uuid",
      "current_version_id": "uuid",
      "current_version_no": 2,
      "updated_at": "2026-07-07T05:00:00+00:00"
    },
    {
      "doc_type": "api-docs",
      "document_id": "uuid",
      "current_version_id": null,
      "current_version_no": null,
      "updated_at": null
    }
  ]
}
```

#### 2. `GET /api/session/{session_id}/documents/{doc_type}/versions`

版本列表，供侧栏使用。可不返回全文，仅返回 `content_preview`，取正文前 200 字。

```json
{
  "doc_type": "prd",
  "document_id": "uuid",
  "current_version_id": "uuid",
  "versions": [
    {
      "id": "uuid",
      "version_no": 2,
      "source_kind": "checkpoint",
      "created_at": "...",
      "content_preview": "# PRD: ...",
      "is_current": true,
      "change_note": "定稿前备份"
    },
    {
      "id": "uuid",
      "version_no": 1,
      "source_kind": "generate",
      "created_at": "...",
      "content_preview": "...",
      "is_current": false
    }
  ]
}
```

列表项可选返回 `change_note`（来自 `metadata_json`）；无备注时省略。`content_preview` 仅供内部或后续扩展，**前端侧栏不用于展示自动摘要**。

#### 3. `GET /api/session/{session_id}/documents/{doc_type}/versions/{version_id}`

单版详情，含全文 `content` 与 `metadata`，供预览使用。

```json
{
  "id": "uuid",
  "version_no": 1,
  "source_kind": "generate",
  "content": "# PRD: ...",
  "source_job_id": "job-uuid",
  "parent_version_id": null,
  "metadata": {
    "run_summary": { },
    "review": { }
  },
  "created_at": "...",
  "is_current": false
}
```

#### 4. `POST /api/session/{session_id}/documents/{doc_type}/versions/checkpoint`

保存为新版本。

请求体字段均可选：

```json
{
  "content": "前端当前编辑器全文；不传则用服务端 current"
}
```

checkpoint **不收集备注**。用户备注通过第 6 个接口事后写入任意版本。

响应：

```json
{
  "version_id": "uuid",
  "version_no": 3,
  "document_id": "uuid"
}
```

**校验：**

- `doc_type` 非法 → 400
- `session_id` 不存在 → 404
- `version_id` 不属于该 document → 404

#### 5. `POST /api/session/{session_id}/documents/{doc_type}/versions/{version_id}/restore`

预览历史版本后「恢复此版本」。以该历史版正文创建**下一版**并设为 current，不修改、不删除任何历史行。

请求体：无（或预留空对象）。

响应：

```json
{
  "version_id": "uuid",
  "version_no": 3,
  "document_id": "uuid",
  "content": "# PRD: ...\n\n恢复自 v1"
}
```

**校验：**

- `version_id` 已是 current → 400
- 历史版无正文 → 400
- 其余同 checkpoint

#### 6. `PATCH /api/session/{session_id}/documents/{doc_type}/versions/{version_id}/note`

为某一版本补充或修改用户备注，写入 `metadata.change_note`；**不修改正文、不升 `version_no`**。

请求体：

```json
{
  "change_note": "定稿前备份"
}
```

传空字符串或省略内容可清空备注。

响应：

```json
{
  "version_id": "uuid",
  "version_no": 2,
  "change_note": "定稿前备份"
}
```

**校验：**

- `version_id` 不属于该 document → 404
- 其余同 checkpoint

### 七、`metadata_json` 约定

```json
{
  "run_summary": {
    "request_id": "req_xxx",
    "total_duration_ms": 47000,
    "total_input_tokens": 28400,
    "steps": []
  },
  "review": {
    "passed": true,
    "summary": "...",
    "issues": []
  },
  "change_note": "用户为版本补充的备注",
  "restored_from_version_id": "uuid",
  "restored_from_version_no": 1
}
```

未产生的字段省略。`merge_metadata` 时，新 Job 的 `run_summary`、`review` 覆盖同名字段；`change_note` 由用户通过备注接口写入或清空，checkpoint / restore **不自动写入**；`restored_from_*` 仅在 restore 写入。

**`review` 写入与展示规则：**

| 动作 | metadata.review |
|------|-----------------|
| 生成 / 重新生成 PRD | 写入本次 Review Agent 结果 |
| 优化 PRD | 不更新，保留该版生成时的 review |
| 手改自动保存 | 不更新 |
| checkpoint / restore | 不继承（新版无 review） |

前端侧栏：有 `metadata.review` 时展示，并标注「基于生成时审查，修改后仅供参考」。每版 generate 各自可有 review，并非仅 v1。

### 八、错误与边界

| 场景 | 行为 |
|------|------|
| 对不存在的 `doc_type` 调 versions | 400 |
| 尚无版本时 list versions | `versions: []` |
| checkpoint 时无 current 且请求体无 content | 400，detail 为无内容可保存 |
| restore 目标是 current | 400 |
| 同一 version_no 重复插入 | 服务层应先算 max+1，依赖 DB UNIQUE 兜底 |

### 九、验收标准

- `init_db` 后存在两张新表
- `GET .../documents` 对新 Session 返回三种 `doc_type`，current 均为空
- 通过 service 单测或临时脚本：`create_initial_version` 后 `version_no=1`，`GET versions` 可见
- `update_current_content` 后 `version_no` 仍为 1，content 已变
- 第二次 `sync_from_job`（generate）后 `version_no=2`，v1 内容不变
- `checkpoint` 后 `version_no` 在已有基础上再 +1，`is_current` 正确
- `restore_version`（在 v1、v2 存在且 current=v2 时恢复 v1）后 `version_no=3`，v3 正文同 v1，v1、v2 不变
- `update_version_note` 后列表与详情中 `change_note` 更新，版本正文与 `version_no` 不变
- 六个 HTTP 接口返回结构符合上文，404、400 正确
