# 基线追溯、下游 Review 与交付包提示词

点击此处可复制本篇提示词

本篇实现交付质量闭环的三项能力：**需求基线确认**（解锁下游生成）、**上下游版本追溯**（PRD 变更后提示过期）、**接口文档与提示词 Review Agent**（各一次，不自动 Rewrite），并提供 **交付包 ZIP** 导出（含 `manifest.json` 汇总质量信息）。

## 使用场景

这份提示词用于 harnessprd 项目 `frontend/`、`backend/services/`、`backend/api/` 改造基线门禁、Review 扩展与导出能力。

**前置条件**：文档版本链、Generation Job、`prd_review_agent` 模式、`delivery_guards` 骨架（01 篇）、`quality_gate`（02 篇）已可用。

**现状问题：** 接口文档与提示词可在 PRD 未确认时直接生成，上下游版本无关联记录；PRD 更新后用户无法感知 api-docs / prompts 可能已过期。api-docs、prompts 缺少 Review 环节；无统一导出交付物入口。

**改造后的下游生成前置条件：**

```
review-prd 页
  → 用户确认需求基线（绑定 current PRD version_id）
  → 解锁「生成接口文档 / 提示词」
  → Job 完成时写入 derived_from
  → PRD 升版后展示过期提示（inform only，不阻断）
```

**本次不做：**

- 接口文档 / 提示词自动 Rewrite
- PRD 第二次 LLM Review
- REQ-ID、PRD 版本 diff、OpenAPI YAML 导出
- 导入 PRD 路径强制澄清（导入路径仅尽量对齐基线 UX，不阻断）
- 改造 v1 `App.tsx`

---

### 一、需求基线确认

#### 功能目标

- Session 字段：`prdBaselineConfirmed`、`prdBaselineConfirmedAt`、`prdBaselineVersionId`
- `review-prd` 页 banner：未确认时提示；按钮「确认需求基线」
- 未确认时 disable：「生成接口文档 →」「跳过接口文档，直接生成提示词」
- 确认时绑定当前 PRD current 版本的 `version_id` + `version_no`
- 下列操作 **撤销确认**：PRD 手改 debounce 保存（相对确认版有 diff）、重新生成 PRD、restore 到其他 PRD 版本、optimize PRD 完成

#### 数据模型

```typescript
// V2SessionData 扩展
prdBaselineConfirmed?: boolean;
prdBaselineConfirmedAt?: string | null;
prdBaselineVersionId?: string | null;
prdBaselineVersionNo?: number | null;
```

```json
// document_versions.metadata 可选镜像
{
  "baseline_confirmed": true,
  "baseline_confirmed_at": "2026-07-07T12:00:00+08:00"
}
```

#### UI（`BaselineConfirmBanner.tsx`）

```
┌────────────────────────────────────────────────┐
│ 需求基线尚未确认                                 │
│ 请通读 PRD。确认后将解锁接口文档与提示词生成。      │
│ [确认需求基线]                                   │
└────────────────────────────────────────────────┘
```

- 已确认：绿色短提示「已确认需求基线 · 基于 PRD v2 · 2026-07-07」
- Review 有 high issues 时：确认按钮旁小字「仍有 N 个审查问题，确认即表示接受风险」

#### 交付守卫扩展

```typescript
case 'generate_api_docs':
case 'generate_prompts':
  if (!ctx.prdBaselineConfirmed) {
    return { allowed: false, reason: '请先确认需求基线' };
  }
  if (!ctx.prdContent?.trim()) {
    return { allowed: false, reason: 'PRD 内容为空' };
  }
  return { allowed: true };
```

后端 `delivery_guards.assert_can_create_job` 对 `api-docs`、`prompts` artifact 同等校验。

#### 撤销确认逻辑

```typescript
function shouldRevokeBaseline(
  confirmedVersionId: string | null,
  currentVersionId: string | null,
  confirmedContentHash: string | null,
  currentContent: string,
): boolean;
```

- 版本 id 变化 → 撤销
- 同版本 content hash（如 sha256 前 16 位）变化 → 撤销
- hash 可在确认时存 session `prdBaselineContentHash`

---

### 二、上下游追溯与过期提示

#### 功能目标

- 创建 api-docs / prompts 版本时写入 `metadata.derived_from`
- api-docs review 页：若 PRD current `version_no` > derived `prd_version_no`，展示 amber banner
- prompts review 页：分别比较 PRD；若有 api-docs 则也比较 api-docs 版本
- **inform only**，不阻断编辑与导出

#### metadata 结构

```json
{
  "derived_from": {
    "prd_version_id": "uuid",
    "prd_version_no": 2,
    "api_docs_version_id": "uuid",
    "api_docs_version_no": 1
  }
}
```

- 仅 prompts 时：`api_docs_*` 可省略
- 跳过 API 生成 prompts：`derived_from.api_docs_skipped: true`

写入时机：`job_runner` 在 api-docs / prompts Job **完成创建新版本时**，读 session 当前 PRD（及 api-docs）的 current version 快照。

#### UI（`StaleArtifactBanner.tsx`）

```
⚠ PRD 已更新至 v3，当前接口文档基于 v2。建议重新生成或手动核对。
[重新生成接口文档]
```

- 顶栏 Artifact 节点可选小 amber 点（`title` tooltip），非必须
- 「重新生成」走现有 Job 流程，生成前仍须基线已确认（对新 PRD 重新确认后）

#### 辅助 API（可选）

`GET /api/session/{id}/artifact-lineage` 返回三文档 current 版本与 derived_from 摘要，供前端算 stale；或在 session load 时后端算好 `stale_flags` 写入 detail 响应。**本期前端用已有 version list + session 字段即可，不强制新 API。**

---

### 三、接口文档 Review Agent

#### 功能目标

- 新建 `api_docs_review_agent.py`，模式对齐 `prd_review_agent.py`
- `generate_api_docs_stream` 正文完成后：`review_started` → Review → `review` 事件 → `done`
- 结果写入 Job `review` 与 version `metadata.review`
- **不** Rewrite；`passed: false` 仍交付，UI 展示 issues

#### Review 重点（system prompt 要点）

1. PRD 中 MVP 功能是否在接口文档中有对应覆盖（启发式，允许合并 endpoint）
2. 是否出现 PRD 未提及的接口或字段（编造）
3. 路径命名、响应结构是否符合 skill 团队规范（语义层）
4. 核心 / 边缘接口划分是否合理

输出 JSON：`{ passed, summary, issues: [{ severity, section, problem, suggestion }] }`

JSON 解析失败走现有 repair/regenerate 模式（`LlmStep.JSON_REPAIR`）。

#### job_runner phase

```python
PHASE_FROM_EVENT = {
    ...
    "api_review_started": "reviewing",
}
```

前端 `generating-api-docs` Stepper 在 reviewing 阶段显示「正在审查接口文档…」（与 PRD Review 阶段指示一致）。

---

### 四、提示词 Review Agent

#### 功能目标

- 新建 `prompts_review_agent.py`
- `generate_prompts_stream` 完成后同样 Review 一次
- 审查重点：
  1. 功能开发类提示词条数与 PRD MVP 数量是否大致一致
  2. 每条是否自包含（不依赖「见上文」）
  3. 是否与 PRD 术语 / 范围一致
  4. 5 类章节是否都有实质内容（非空标题）

同样 **不 Rewrite**。

---

### 五、交付包导出

#### 功能目标

- `GET /api/session/{id}/export` 或 `POST /api/session/{id}/export-delivery` 返回 `application/zip`
- 前端 `review-prompts`（及可选 PRD / api-docs 页）按钮「导出交付包」
- ZIP 结构：

```
{product-name}-delivery.zip
├── README.md
├── manifest.json
├── PRD.md
├── API-Docs.md          # 无则省略或空文件说明
└── Prompts.md
```

#### manifest.json 示例

```json
{
  "product_name": "朋友圈文案助手",
  "session_id": "...",
  "exported_at": "2026-07-07T12:00:00+08:00",
  "entry_mode": "structured",
  "documents": {
    "prd": {
      "version_no": 2,
      "version_id": "...",
      "baseline_confirmed_at": "...",
      "quality_gate": { "passed": true, "score": 91 },
      "review": { "passed": true, "summary": "..." }
    },
    "api_docs": {
      "version_no": 1,
      "derived_from": { "prd_version_no": 2 },
      "quality_gate": { ... },
      "review": { ... }
    },
    "prompts": { ... }
  },
  "stale_warnings": []
}
```

#### README.md 模板（后端生成）

- 三文档阅读顺序
- 各文档版本号与生成时间
- quality_gate / review 未通过项摘要
- stale_warnings 文案
- 一句「由 harnessprd 导出」

#### 前端

- 下载触发 browser blob；文件名 `{productName}-delivery.zip`
- 至少一份文档非空才 enable；全空 disable

---

### 六、代码结构

```
backend/
  services/
    api_docs_review_agent.py       # 新建
    prompts_review_agent.py        # 新建
    delivery_export_service.py     # 新建：组 ZIP
    delivery_guards.py             # 扩展基线规则
    document_service.py            # 改造：api/prompts 流末尾 Review
    job_runner.py                  # derived_from、review phase
  api/
    session.py 或 export.py         # 导出路由

frontend/src/
  components/
    BaselineConfirmBanner.tsx
    StaleArtifactBanner.tsx
  AppV2.tsx                        # 基线 state、actions disable、导出按钮
  utils/deliveryStage.ts           # 扩展 guards
```

---

### 七、导入路径（`entryMode: prd` / `prompts`）

- 无澄清就绪度评估；PRD review 页同样展示基线确认，用于解锁下游生成
- 用户导入 PRD 后若已有正文，首次进入 `review-prd` 时 `prdBaselineConfirmed=false`
- 不强制重新走结构化表单

---

### 八、错误与边界

- 导出时某文档仅有 session 字符串无 version row：用 current content 仍写入 md，manifest 记 `"version_no": null`
- Review 超时/失败：Job 可 `failed` 或 `completed` + review 记 error；**建议 completed + review.passed=false**，避免丢正文
- 跳过 API：`derived_from.api_docs_skipped=true`，manifest 注明

---

### 九、验收标准（本篇）

1. PRD 未确认基线时，「生成接口文档」disabled；确认后 unlock
2. 手改 PRD 后基线自动失效，banner 复现
3. api-docs 生成后 metadata 含 `derived_from`；PRD 升版后 review-api-docs 见过期 banner
4. api-docs、prompts Job 有 Review phase 与 `metadata.review`
5. Review 不通过仍可见正文，issues 展示
6. 导出 ZIP 含 3 个 md（有则写）、manifest、README；manifest 含 quality_gate 摘要
7. 后端未确认基线创建 api-docs Job 返回 400
8. `npm run build` 通过

---

### 十、实现顺序建议

1. 基线 session 字段 + Banner + `delivery_guards` + 前端 disable
2. `derived_from` 写入 + `StaleArtifactBanner`
3. `api_docs_review_agent` 接入 Job
4. `prompts_review_agent` 接入 Job
5. `delivery_export_service` + 导出按钮
6. 全链路手工验收 + 04 测试文档勾检

**可分两个 PR：** PR-A 基线+追溯+Review；PR-B 导出。
