# Job 完成写入与自动保存提示词

点击此处可复制本篇提示词

本篇把 01 的 Document 版本层接入现有 Job 与 Session 链路：Job 完成时写入或更新 current 版本；Session debounce 保存时同步 current 正文；老 Session 首次访问时自动迁移为 v1。前端 debounce 自动保存流程不变，后端落库目标从覆盖三个字符串改为更新 current 版本，同时保留 `session_data` 镜像字段。

## 使用场景

这份提示词用于在 harnessprd `backend/` 把 Document 版本层与 Job、Session 打通。只改后端，不动前端。

**前置条件**：`documents`、`document_versions` 表与 `document_version_service`、6 个 Document API 已可用。

**改造后的写入链路：**

```
生成 / 优化 Job 完成
  → sync_from_job（写 current 或升新版 + metadata）
  → sync_session_on_job_complete（写 session_data 镜像）

用户手改 debounce save
  → POST /api/session/save
  → _sync_session_content_to_documents（auto_save → current）

老 Session 首次 save / get
  → _migrate_session_documents_if_needed（import → v1）
```

**本次不做：**

- 前端版本侧栏与 checkpoint 按钮
- 定稿、恢复、diff
- 删除 `session_data` 里的 `prdContent` 等字段
- 改造澄清对话与 Job 创建协议

### 一、功能目标

- `job_runner`：Job `completed`，或 `failed` 但仍有 partial 时，调用 document service 更新 current
- `session_service.save_session`：若 `session_data` 含 `prdContent`、`apiDocsContent`、`promptsContent`，同步到对应 current 版本，`source_kind` 为 `auto_save`
- 老 Session 迁移：`get_session` 或 `save_session` 时，若 Session 有正文但无 document 记录，导入为 v1，`source_kind` 为 `import`
- 双写：`session_data` 三字段与 current 版本的 content 保持一致
- Job 完成时把 `run_summary`、`review` 写入版本 metadata

### 二、artifact 与 doc_type 映射

与现有 Job、Session 字段一致：

| Job artifact | doc_type | Session 字段 |
|--------------|----------|----------------|
| `prd` | `prd` | `prdContent` |
| `optimize-prd` | `prd` | `prdContent` |
| `api-docs` | `api-docs` | `apiDocsContent` |
| `optimize-api-docs` | `api-docs` | `apiDocsContent` |
| `prompts` | `prompts` | `promptsContent` |
| `optimize-prompts` | `prompts` | `promptsContent` |

```python
ARTIFACT_TO_DOC_TYPE = {
    "prd": "prd",
    "optimize-prd": "prd",
    "api-docs": "api-docs",
    "optimize-api-docs": "api-docs",
    "prompts": "prompts",
    "optimize-prompts": "prompts",
}
```

### 三、Job 完成时写版本

在 `job_runner.py` 中，于现有 `sync_session_on_job_complete`、`sync_session_on_optimize_complete` 之前或之后调用：

```python
document_version_service.sync_from_job(
    session_id=job["session_id"],
    doc_type=ARTIFACT_TO_DOC_TYPE[job["artifact"]],
    content=final_content,
    source_kind="generate" if not job["artifact"].startswith("optimize-") else "optimize",
    source_job_id=job["id"],
    metadata=build_metadata_from_job(job),
)
```

#### `sync_from_job` 逻辑

```
ensure_document(session_id, doc_type)
current = get_current_version(...)

若 current 为空：
  create_initial_version(..., source_kind=generate 或 optimize)  → v1
否则若 source_kind == generate：
  append_generated_version(...)  → 升新版，旧版进历史
否则：
  update_current_content(..., source_kind=optimize)   → 不升 version_no
```

整份生成（PRD / 接口文档 / 提示词）每次 Job 完成升新版；优化 Job 只更新 current，不升 `version_no`。

#### `build_metadata_from_job(job)`

从 Job 行提取：

- `result_json` 或 runner 内存中的 `run_summary` → `metadata.run_summary`
- `review_json` → `metadata.review`
- 优化类 Job 无 review 则省略

若 runner 在 `done` 事件里已有 summary dict，优先用内存最新值写库。

#### Job `failed` 但有 `draft_content`

与今天 Session 行为一致：若有非空 partial，仍写入版本层，`source_kind` 与完成路径相同（generate 升新版、optimize 更新 current），便于用户刷新后看到半成品。metadata 可加 `job_status: failed`。

### 四、Session save 同步 current

改造 `services/session_service.py` 的 `save_session`，在 `conn.commit` 之前：

```python
_migrate_session_documents_if_needed(session_id, normalized)
_sync_session_content_to_documents(session_id, normalized)
```

#### `_sync_session_content_to_documents`

对三种字段分别处理：

| Session 字段 | doc_type | 条件 |
|--------------|----------|------|
| `prdContent` | `prd` | 非空字符串 |
| `apiDocsContent` | `api-docs` | 非空 |
| `promptsContent` | `prompts` | 非空 |

对每个有内容的字段：

```
current = get_current_version(...)
若 current 为空：
  create_initial_version(..., source_kind=auto_save)
否则若 content != current.content：
  update_current_content(..., source_kind=auto_save)
```

防抖在前端，后端每次 save 可能较频繁，直接 UPDATE current 行即可；**不要**每次 save 都调用 `checkpoint`。

空字符串不创建版本，也不删除已有版本。本阶段可不支持清空文档。

#### 与 Job 双写的顺序

Job 完成：

1. `document_version_service.sync_from_job(...)`
2. `sync_session_on_job_complete(...)` 写 `session_data` 镜像

Session save：

1. 写 `project_sessions.session_data`
2. `_sync_session_content_to_documents`

避免循环：`update_current` 里不要再调 `save_session`。

### 五、老 Session 迁移

函数 `_migrate_session_documents_if_needed(session_id, session_data)`：

对 `prd`、`api-docs`、`prompts`：

```
若 session_data 对应 Content 非空
且 documents 表无 current_version：
  create_initial_version(content, source_kind=import)
```

只迁移一次；已有 current 则跳过。

推荐在 `save_session` 时触发迁移，减少只读 GET 的副作用。打开旧方案应直接出现 v1，无需用户操作。

### 六、`sync_session_on_job_complete` 对齐

现有逻辑设置 `prdContent` 等字段，保留不变。Job 路径上保证：

```
document current.content 与 session_data.prdContent 一致
```

`get_session` 返回时，仍以 `session_data` 为前端主读源。若发现不一致，以 document current 为准覆盖镜像并写回 DB。

可在 `get_session` 增加：

```python
_refresh_session_content_from_documents(session_id, session_data)
```

### 七、写入顺序

**生成或优化 Job 完成：**

```
job_runner finish
  → sync_from_job（document current + metadata）
  → sync_session_on_job_complete（session_data + viewState）
```

**用户手改 debounce save：**

```
POST /api/session/save
  → save_session JSON
  → _sync_session_content_to_documents（auto_save → current）
```

**用户点「保存为新版本」：**

```
POST .../checkpoint
  → checkpoint() 升 version_no
```

在 `checkpoint` API handler 末尾，把新 current 的 content 写回 `session_data` 对应字段，保持一致。

### 八、代码改动清单

| 文件 | 改动 |
|------|------|
| `services/document_version_service.py` | 新增 `sync_from_job`、`maybe_migrate_from_session` |
| `services/job_runner.py` | 完成或失败 partial 时调 `sync_from_job` |
| `services/session_service.py` | `save_session`、`get_session` 挂迁移与 auto_save 同步 |
| `api/documents.py` | `checkpoint` 成功后同步 session 镜像 |

**不要改：**

- `document_service` 内 LLM generator
- Job SSE 事件格式
- 前端 `debouncedSaveSession` 调用方式

### 九、验收标准

- 新 Session 生成 PRD Job 完成后：DB 有 `documents(prd)`、`document_versions(version_no=1)`，content 与 `session_data.prdContent` 一致
- 同一 PRD 连续两次优化 Job 完成：`version_no` 仍为 1，content 已更新两次；metadata 中 `run_summary` 为最后一次
- 手改 PRD 触发 debounce save：`version_no` 仍为 1，content 为手改后文本
- 老 Session 仅有 `prdContent`、无 documents：首次 `get_session` 或 `save_session` 后出现 v1，`source_kind=import`
- Job failed 且 `draft_content` 非空：current 有 partial，Session 镜像一致
- `checkpoint` 后：`version_no` 加一，旧版 content 不变

### 十、调试建议

实现期可打临时日志，合并前删除或降为 debug：

```python
logger.info("document_sync", extra={
    "session_id": session_id,
    "doc_type": doc_type,
    "action": "update_current|create_initial|checkpoint",
    "version_no": version_no,
    "source_kind": source_kind,
})
```

便于对照 Job id 与版本变化。
