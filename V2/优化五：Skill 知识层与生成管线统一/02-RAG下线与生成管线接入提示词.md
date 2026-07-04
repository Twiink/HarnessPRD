# RAG 下线与生成管线接入提示词

点击此处可复制本篇提示词

本篇完成 RAG 下线，并将 PRD、接口文档、提示词三条生成管线统一到 Skill 注入：新建 `api-docs-generator` 与 `prompts-generator`，把 `backend/knowledge/api_docs/` 中的规范迁入 skill 目录；接口文档、提示词的生成与优化改经 `skill_loader` 注入，不再经过检索确认页。同时删除 `rag_service`、RAG API 与前端门控 UI，在 `run_summary` 中记录 `injected_skills`。**前置依赖：** 01 篇 loader 与注册表已就绪。

## 使用场景

这份提示词用于在 harnessprd 项目 **后端 + 前端** 完成 RAG 下线，并将三产物生成统一到 Skill 管线。

**前置条件**：`skill_loader`、`config/skills.yaml`、`skills/prd-generator/skill.yaml` 已实现；PRD 已走 loader。

**现状问题：** 接口文档生成依赖 `rag_service` 按 PRD 关键词检索 `knowledge/api_docs/`，前端需展示检索结果并等待用户确认后再开 Job。规范源分散在 knowledge 目录与 prompt 常量中，与 PRD 的 skill 注入路径不一致，且检索结果不稳定。

**改造后的生成链路：**

```
用户点「生成接口文档」
  → 直接 startApiDocs Job（无确认页）
  → document_service.load_skill_bundle("api-docs")
  → 全量注入 reference + example
  → run_summary.injected_skills 记录注入清单
```

**本次不做：**

- `team.yaml`、团队覆盖、上传 UI
- Skill 版本 pin、管理后台
- 真向量 RAG
- 改造澄清对话、文档版本模型
- 删除 `prompts.py` 中所有常量（可保留作 fallback 片段，但生成主路径以 skill 为准）

### 一、功能目标

**后端**

- 新建 `skills/api-docs-generator/`、`skills/prompts-generator/`（含 `skill.yaml` + references）
- 迁移 `backend/knowledge/api_docs/*.md` → `api-docs-generator/references/`
- 更新 `config/skills.yaml` 绑定
- `generate_api_docs_stream`、`generate_prompts_stream` 及优化路径改走 loader
- 删除 `rag_service.py`、`retrieve_api_docs_rag_hits`、相关 import
- 删除 `POST /conversation/retrieve-api-docs-rag`
- `run_summary` 增加 `injected_skills` 字段

**前端**

- 删除 RAG 确认页、`retrieveApiDocsRag` 调用
- 点「生成接口文档」→ 直接 `startApiDocs` Job
- 清理 `ragHits`、`pendingApiDocsPrd`、`isRetrievingRag` 等状态与 Session 字段
- RunSummary 面板可选展示 `injected_skills`（折叠、小字，非门控）

**验收**

- 主路径生成接口文档 **无确认步骤**，生成质量不低于改造前（人工对比 1 次）
- 三产物 Job 完成后的 `run_summary` 含 `injected_skills`

---

## 二、后端：新建 Skill 目录

### 1. `skills/api-docs-generator/`

建议结构：

```
skills/api-docs-generator/
├── skill.yaml
├── instructions.md
└── references/
    ├── team-api-guidelines.md      # 自 knowledge 迁入
    ├── history-copywriting-api.md
    ├── history-task-api.md
    └── writing-rules.md            # 可选：接口文档写作要点（从 prompts 提炼）
```

`skill.yaml` 示例：

```yaml
id: api-docs-generator
version: "1.0.0"
label: 接口文档生成规范
description: 团队 HTTP API 设计规范与历史示例，生成时自动注入，无需用户确认
applies_to:
  - api-docs
  - optimize-api-docs
artifacts:
  - path: instructions.md
    role: instructions
  - path: references/team-api-guidelines.md
    role: reference
  - path: references/history-copywriting-api.md
    role: example
  - path: references/history-task-api.md
    role: example
  - path: references/writing-rules.md
    role: reference
enabled: true
priority: 10
```

`instructions.md` 要点：

- 输入：PRD 正文（+ 可选澄清上下文）
- 输出：Markdown 接口文档
- 优先遵循 `team-api-guidelines.md`
- 参考 example 的路径命名、参数表、错误码写法
- **不要逐段复制规范原文到输出**，应内化为接口设计结果

### 2. `skills/prompts-generator/`

```
skills/prompts-generator/
├── skill.yaml
├── instructions.md
└── references/
    ├── prompts-template.md         # Claude Code 提示词套件结构
    └── writing-rules.md
```

`skill.yaml` 绑定 `prompts`、`optimize-prompts`。

从现有 `PROMPTS_GENERATION_PROMPT`（`prompts.py`）提炼模板与规则写入 references；`instructions.md` 说明输入为 PRD + 可选接口文档。

### 3. 迁移 `knowledge/api_docs/`

- 复制三个 md 到 `api-docs-generator/references/`
- 迁移验证通过后 **删除** `backend/knowledge/api_docs/` 目录（或留空 README 指向 skills，二选一，推荐删除避免双源）
- **删除** `backend/services/rag_service.py`

### 4. 更新 `config/skills.yaml`

```yaml
bindings:
  prd:
    skills: [prd-generator]
  optimize-prd:
    skills: [prd-generator]
  api-docs:
    skills: [api-docs-generator]
  optimize-api-docs:
    skills: [api-docs-generator]
  prompts:
    skills: [prompts-generator]
  optimize-prompts:
    skills: [prompts-generator]
```

---

## 三、后端：改造 `document_service.py`

### 1. `generate_api_docs_stream`

**删除：**

```python
from services.rag_service import retrieve_api_docs_context, retrieve_api_docs_hits
# ...
rag_context = retrieve_api_docs_context(...)
rag_section = "接口文档生成前检索到的 RAG 参考资料..."
```

**改为：**

```python
bundle = load_skill_bundle("api-docs")
sections = compose_prompt_sections(bundle)
# 将 instructions、reference、example 拼成 skill_section
```

HumanMessage 结构建议：

```
以下是已确认的产品需求文档（PRD）：

{prd_content}

{可选：澄清对话摘要}

{skill_section — 团队规范与示例，标题如「团队接口规范与参考示例」}

{API_DOCS_GENERATION_PROMPT 或并入 skill instructions}

额外要求：
1. 遵循 skill 中的团队接口规范
2. 参考示例的路径、参数表、错误码写法
3. 规范内化为设计结果，不要逐段复制规范原文
```

行为变化：**始终注入全部 reference + example**（不再按 PRD 关键词做 top_k 筛选）。规范文件体量小且固定，全量注入比关键词检索更稳定、可预期。

### 2. `generate_prompts_stream`

同样 `load_skill_bundle("prompts")`，拼 template + instructions + PRD/API 正文。

### 3. 优化文档 `optimize_*`

若优化路径有独立 prompt 组装，同样 `load_skill_bundle("optimize-api-docs")` 等，至少注入 writing-rules / guidelines。

### 4. 删除 RAG 专用方法

删除 `retrieve_api_docs_rag_hits` 及 `conversation.py` 路由：

```python
@router.post("/retrieve-api-docs-rag")  # 删除
```

全局搜索 `rag_service`、`retrieve_api_docs`、`RagHit` 后端引用并清理。

---

## 四、后端：`run_summary.injected_skills`

在 Job 完成 emit `run_summary` 时，增加字段：

```json
{
  "type": "run_summary",
  "request_id": "...",
  "steps": [...],
  "injected_skills": [
    {
      "skill_id": "api-docs-generator",
      "version": "1.0.0",
      "artifacts": [
        "instructions.md",
        "references/team-api-guidelines.md",
        "references/history-copywriting-api.md"
      ]
    }
  ]
}
```

**实现建议：**

- `skill_loader` 提供 `bundle_to_injected_meta(bundle) -> list[dict]`
- `document_service` 生成函数返回时附带 meta，或 runner 在调用前取 bundle 传入 collector
- `RunMetricsCollector` / `job_runner._finish_run_summary` 合并进 `summary.to_dict()`
- 同步写入 `document_versions.metadata`（若已有 `run_summary` 合并逻辑，一并带上 `injected_skills`）

澄清、纯对话类 `run_summary` **可无**此字段（optional）。

---

## 五、前端：删除 RAG 门控

### 1. 删除的状态与 Session 字段

| 移除项 | 位置 |
|--------|------|
| `ragHits` | `AppV2` state、`sessionService` |
| `pendingApiDocsPrd` | 同上 |
| `isRetrievingRag` | `AppV2` |
| `showApiDocsRagGate` | 派生变量 |
| RAG 确认页 JSX | `AppV2` 大块 UI（标题、hits 列表、确认按钮） |
| `retrieveApiDocsRag` | `api.ts` |
| `RagHit` 类型 | 若无其他引用则删 `types/index.ts` |

### 2. 生成接口文档流程

**改造前：**

```
点「生成接口文档」
  → retrieveApiDocsRag
  → 展示确认页
  → 用户点「开始生成」
  → jobGen.startApiDocs(prd)
```

**改造后：**

```
点「生成接口文档」
  → setViewState('generating-api-docs')
  → jobGen.startApiDocs(prd)   // 直接开 Job
```

删除 `retrieveApiDocsRag` 中间函数；`generateApiDocs`（或等价 handler）简化为直接调 Job。

### 3. Session 持久化

`buildSessionSnapshot` / `loadSession` 不再读写 `ragHits`、`pendingApiDocsPrd`。老 Session 里若带这些字段，加载时 **忽略** 即可，不必迁移。

### 4. RunSummary 展示（可选但推荐）

在 `RunSummaryPanel` 或折叠区底部：

```
参考规范：api-docs-generator (v1.0.0) · 3 个文件
```

点击可展开文件名列表；**不要**做成第二道确认门控。

---

## 六、代码结构变更汇总

```
删除：
  backend/services/rag_service.py
  backend/knowledge/api_docs/          # 内容已迁走
  backend/api/conversation.py          # retrieve-api-docs-rag 路由
  frontend RAG 门控 UI 与相关 API

新增：
  skills/api-docs-generator/**
  skills/prompts-generator/**

改造：
  config/skills.yaml
  backend/services/document_service.py
  backend/services/job_runner.py       # run_summary 字段
  backend/services/llm_metrics.py    # RunSummary 类型（若需）
  frontend/src/AppV2.tsx
  frontend/src/services/api.ts
  frontend/src/services/sessionService.ts
  frontend/src/components/RunSummaryPanel.tsx  # 可选
```

---

## 七、与优化四验收的关系

优化四测试验收中「RAG 门控仍出现」的预期 **在本篇完成后应反转**：主路径生成接口文档 **不再** 出现确认页。更新回归用例时注意。

---

## 八、验收标准（本篇）

1. 点「生成接口文档」后 **直接进入** `generating-api-docs`，无资料确认页
2. 接口文档正文含规范风格（如 `/api/v1`、统一响应包裹），与改造前质量可比
3. 生成提示词正常，结构符合 prompts skill 模板
4. `curl` 或浏览器网络面板：**无** `/retrieve-api-docs-rag` 请求
5. 后端 **无** `rag_service` import
6. Job 完成 `run_summary.injected_skills` 非空（api-docs / prompts / prd 生成均应有）
7. PRD 生成回归仍通过（loader 未被本篇破坏）
8. 优化文档 Job 仍正常，刷新可重连

```bash
cd frontend && npm run build
cd backend && uvicorn main:app --reload  # 启动无 ImportError
```

---

## 九、实现顺序建议

1. 新建两个 skill 目录，迁入 md，更新 `skills.yaml`
2. 改 `document_service` 生成与优化路径
3. 删 `rag_service` 与 API 路由
4. `injected_skills` 接入 run_summary 与 version metadata
5. 前端删门控、直连 Job
6. RunSummary 可选展示
7. 全流程手工走一遍：PRD → 接口文档 → 提示词
