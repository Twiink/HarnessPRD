# 产出物进度条与生成 CTA 提示词

点击此处可复制本篇提示词

本篇改造顶栏进度展示与各审阅页的生成按钮：由固定五步「流程进度」改为按 `entryMode` 动态展示的「产出物进度」，用完成状态表达 PRD、接口文档、提示词是否已有内容；同时在 PRD 审阅页分层前进按钮——主路径强调「生成接口文档」，跳过接口文档降为次要操作并带确认提示。

## 使用场景

这份提示词用于在 harnessprd 项目 `frontend/` 改造顶栏进度展示与各审阅页的生成 CTA。

**前置条件**：生成 Job、文档版本、`entryMode` 已可用。

**现状问题：** 顶栏固定展示五个阶段按钮，`enabled` 规则复杂；PRD 审阅页「直接生成提示词」与「生成接口文档」视觉权重接近，主路径推荐顺序不明确。导入路径与主路径的前置阶段不同，但顶栏节点未随 `entryMode` 裁剪。

**改造后的顶栏逻辑：**

```
buildArtifactNodes(entryMode, viewState, content 字段)
  → ArtifactProgressBar（done / active / pending）
  → 仅 done 节点可点击跳转
```

**本次不做：**

- 改造路径选择页、结构化表单
- 删除或改造 RAG 门控（留给 Skill 静默注入专题）
- 文档上下游过期提示、版本 diff、导出 ZIP
- 澄清对话 Job 化
- 修改后端 Job API

### 一、功能目标

- 顶栏由固定五步 Tab，改为 **按 `entryMode` 动态展示的产出物节点**
- 节点状态：`未开始` / `进行中` / `已完成`；仅 **已完成** 的节点可点击跳转
- PRD 审阅页（`entryMode === 'structured'`）：**主按钮**「生成接口文档 →」；**次要**文字链「跳过接口文档，直接生成提示词」+ 确认提示
- 导入 PRD（`entryMode === 'prd'`）：保留「直接生成提示词」为合理并列选项（用户已选捷径）
- 接口文档审阅页：保持单一主按钮「生成提示词 →」
- 抽出 `utils/artifactProgress.ts`，减轻 `AppV2` 内联逻辑
- `npm run build` 通过

### 二、要解决的问题

顶栏始终显示五个阶段按钮，且 `enabled` 规则分散在 `AppV2` 内。PRD 审阅页同时提供「直接生成提示词」与「生成接口文档 →」，两个 forward 操作视觉权重相近。

按 `entryMode`，实际旅程分为三类：

| 旅程 | 应有节点 |
|------|----------|
| 从零创建（`structured`） | 需求 → 澄清 → PRD → 接口文档 → 提示词 |
| 导入 PRD（`prd`） | PRD → 接口文档 → 提示词 |
| 导入 PRD+API（`prompts`） | PRD →（接口文档，若有内容）→ 提示词 |

进度条应反映 **产出物是否已有正文**，而不是固定展示五个阶段名称。

### 三、代码结构

```
frontend/src/
  utils/
    artifactProgress.ts           # 新建：节点定义、状态计算、跳转映射
  components/
    ArtifactProgressBar.tsx       # 新建：顶栏产出物 UI（可选，或内联在 AppV2）
  AppV2.tsx                       # 改造：替换 stageItems，按 entryMode 传 actions
```

### 四、产出物节点模型

```typescript
export type ArtifactId =
  | 'requirements'
  | 'clarification'
  | 'prd'
  | 'api-docs'
  | 'prompts';

export type ArtifactStatus = 'pending' | 'active' | 'done';

export type ArtifactNode = {
  id: ArtifactId;
  label: string;
  status: ArtifactStatus;
  clickable: boolean;
  onClick?: () => void;
};
```

#### 各 `entryMode` 展示的节点

**`structured`（5 个）：**

| id | label | done 条件 |
|----|-------|-----------|
| requirements | 需求 | `formData` 有有效 `product_name` 且曾进入过澄清或已有 PRD |
| clarification | 澄清 | `hasClarificationContent(messages)` |
| prd | PRD | `prdContent.trim()` 非空 |
| api-docs | 接口文档 | `apiDocsContent.trim()` 非空 |
| prompts | 提示词 | `promptsContent.trim()` 非空 |

**`prd`（3 个）：** PRD → 接口文档 → 提示词（无需求、澄清）

**`prompts`（2～3 个）：** PRD →（接口文档，仅当 `apiDocsContent` 非空或 `entryMode` 导入时填过 API）→ 提示词

简化实现：`prompts` 入口固定显示 PRD + 提示词；若 `apiDocsContent` 有内容，中间插入接口文档节点。

#### `active` 状态判定

根据当前 `viewState`：

| viewState | active 节点 |
|-----------|-------------|
| `form` + structured | requirements |
| `chatting` | clarification |
| `generating-prd` / `review-prd` | prd |
| `generating-api-docs` / `review-api-docs` | api-docs |
| `generating-prompts` / `review-prompts` | prompts |

#### `clickable` 规则

- `status === 'done'` → 可点击，`onClick` 跳到对应 `review-*` 或 `form` / `chatting`
- `status === 'active'` → 不可点（当前页）
- `status === 'pending'` → 不可点，`title` 提示「尚未生成」

**禁止** 点击未生成的接口文档/提示词节点空跳。

### 五、顶栏 UI 规格

替换原「流程进度」区域（`stageItems.map` 一段）：

```
产出物    [ 需求 ✓ ] [ 澄清 ✓ ] [ PRD ● ] [ 接口文档 ○ ] [ 提示词 ○ ]
```

样式建议：

| status | 样式 |
|--------|------|
| done | 绿色浅底 + ✓，可 hover |
| active | 深色底白字（与现有 active 样式一致） |
| pending | 灰色，不可点 |

左侧文案由「流程进度」改为 **「产出物」**。

将计算逻辑放在 `buildArtifactNodes(entryMode, viewState, sessionSnapshot)` 纯函数中，`AppV2` 只消费结果。

### 六、PRD 审阅页 CTA 分层

在 `viewState === 'review-prd'` 的 `DocumentReviewWithVersions` 的 `actions` 中，**按 `entryMode` 分支**：

#### `entryMode === 'structured'`（主路径）

```typescript
[
  { label: '返回对话' | '返回入口', variant: 'secondary', ... },
  { label: '结束任务', variant: 'ghost', ... },
  // 次要：文字链，不是与主按钮同级的 secondary 大按钮
  { label: '跳过接口文档，直接生成提示词', variant: 'link', onClick: confirmSkipApiDocs },
  { label: '生成接口文档 →', variant: 'primary', onClick: retrieveRagBeforeApiDocs },
]
```

`confirmSkipApiDocs` 流程：

1. `window.confirm('跳过接口文档时，提示词可能缺少 API 细节。是否继续？')`
2. 确认后调现有 `generatePrompts(prdContent, '')`

若 `DocumentReview` 不支持 `variant: 'link'`，用 `ghost` 小字号按钮或 `button` + `text-sm text-slate-500 underline` 样式，**视觉权重明显低于 primary**。

#### `entryMode === 'prd'`（导入 PRD）

用户已选择捷径，可保留两个 forward 按钮，但文案区分主次：

- 主：`生成接口文档 →`
- 次：`直接生成提示词`（`secondary`，可不加 confirm，或轻量 confirm）

#### `entryMode === 'prompts'`

一般从导入向导直进审阅，PRD 页 actions 与 `prd` 类似即可。

### 七、其他审阅页（保持或微调）

| 页面 | actions |
|------|---------|
| `review-api-docs` | 返回 PRD、结束任务、**生成提示词 →**（primary） |
| `review-prompts` | 返回接口文档或 PRD、结束任务；无 forward |

接口文档页 **不要** 增加「跳过提示词」类按钮。

### 八、删除与替换

- 删除或废弃 `getStageIndex` 若仅服务旧 `stageItems`；改为从 `artifactProgress` 推导
- 删除 `stageItems` useMemo 整块，换成 `artifactNodes`
- `currentStageIndex` 若仍被 GenerationStepper 使用，保留 PRD 生成阶段内部逻辑，不与顶栏混用

**不要改动：**

- `useGenerationJob`、RAG 检索函数本体
- 澄清页按钮
- 表单字段

### 九、边界情况

| 场景 | 预期 |
|------|------|
| 主路径 PRD 页点跳过 | confirm 后进入 `generating-prompts`，顶栏接口文档仍为 pending |
| 仅有 PRD、无 API 时看提示词页「返回」 | 回到 `review-prd`（与改造前一致） |
| 导入路径顶栏 | 不显示需求、澄清节点 |
| 刷新后 | 节点 done 状态与内容字段一致 |

### 十、验收标准

- 顶栏文案为「产出物」，节点随 `entryMode` 变化
- 未生成的节点不可点击
- 主路径 PRD 页：只有一个深色主按钮「生成接口文档 →」；跳过为次要样式且需 confirm
- 导入 PRD 页：两个 forward 按钮仍可用
- 接口文档页：仅「生成提示词 →」前进
- 澄清、三种文档生成 Job、刷新重连、版本侧栏不受影响
- `npm run build` 通过
