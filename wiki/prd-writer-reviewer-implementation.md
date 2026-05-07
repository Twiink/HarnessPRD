# V2 PRD Writer + Reviewer 多 Agent 改造总结

## 范围

本文只说明 `/v2` 页面中的 PRD 生成链路。

这次改造覆盖的是：

- 结构化需求摘要
- 澄清对话
- 基于 summary 生成 PRD

不讨论旧版 `/` 页面。

## 目标

将 `/v2` 原本“单次生成 PRD”的流程升级成两个独立 agent 协作：

- `Writer Agent`：负责起草和重写 PRD
- `Review Agent`：负责审查 PRD 草稿并输出结构化审查意见

目标是让 `/v2` 在不改变主交互路径的前提下，提高 PRD 的完整性和可执行性。

## V2 最终流程

`/v2` 里，用户完成结构化需求填写和澄清后，PRD 生成流程变成：

1. 前端触发 `/api/conversation/generate-prd-from-summary-stream`
2. `Writer Agent` 基于 `requirements_summary` 和澄清对话生成 `draft_v1`
3. `Review Agent` 审查 `draft_v1`
4. 如果审查通过：
   - 直接返回 `draft_v1`
5. 如果审查未通过：
   - `Writer Agent` 根据 review 结果重写一次
   - 返回 `draft_v2`

也就是：

`writer -> reviewer -> writer(rewrite once if needed)`

## 为什么这已经是多 Agent

这里没有做多进程或多服务拆分，但已经满足独立 agent 的工程定义：

- 独立 system prompt
- 独立模型调用
- 独立职责边界
- 独立输出契约

职责划分保持很简单：

- `Writer Agent` 只负责写，不负责审查
- `Review Agent` 只负责审查，不负责改稿

## 后端改造

### 新增文件

- `backend/services/prd_writer_agent.py`
- `backend/services/prd_review_agent.py`

### 主要改动

在 `backend/services/prompts.py` 中新增了：

- `PRD_WRITER_SYSTEM_PROMPT`
- `PRD_REVIEWER_SYSTEM_PROMPT`
- `PRD_REVIEW_PROMPT_TEMPLATE`
- `PRD_REWRITE_PROMPT_TEMPLATE`

在 `backend/services/document_service.py` 中，重点改造了：

- `generate_prd_from_summary_stream()`

这条接口现在会：

1. 先发 `writer_started`
2. 流式输出 writer 草稿
3. 再发 `review_started`
4. 返回 review JSON
5. 必要时发 `rewrite_started`
6. 流式输出修订版
7. 最后返回 `done`

## 前端改造

### 主要涉及文件

- `frontend/src/AppV2.tsx`
- `frontend/src/services/api.ts`
- `frontend/src/components/DocumentReview.tsx`
- `frontend/src/types/index.ts`

### 主要能力

`/v2` 前端现在支持：

- 感知 PRD 生成阶段切换
- 展示 Writer / Reviewer 的状态文案
- 展示 Review Agent 的结构化审查结果
- 在 review 不通过时展示重写过程

## SSE 事件协议

`/v2` 的 PRD 生成流现在使用以下事件。

### phase

用于通知前端当前阶段。

示例：

```json
{ "type": "phase", "phase": "writer_started" }
{ "type": "phase", "phase": "review_started" }
{ "type": "phase", "phase": "rewrite_started" }
```

### text_delta

用于流式返回 PRD 正文增量。

之所以不用 `chunk`，是为了避免和 RAG chunk 混淆。

示例：

```json
{ "type": "text_delta", "phase": "writer", "content": "# PRD: ..." }
{ "type": "text_delta", "phase": "rewrite", "content": "## 1. 产品概述" }
```

### review

用于返回 Review Agent 的结构化审查意见。

示例：

```json
{
  "type": "review",
  "phase": "review",
  "content": {
    "passed": false,
    "summary": "PRD 主体完整，但存在高优先级问题",
    "issues": [
      {
        "severity": "high",
        "section": "MVP 功能",
        "problem": "功能边界不清晰",
        "suggestion": "补充触发条件和异常场景"
      }
    ]
  }
}
```

### done

用于返回最终 PRD 和审查结果。

示例：

```json
{
  "type": "done",
  "final_prd": "...",
  "review": { "...": "..." },
  "revision_applied": true
}
```

## V2 页面上的用户体验

用户在 `/v2` 中点击生成 PRD 后，会看到以下状态流转。

审查通过时：

`idle -> writing -> reviewing -> done`

审查未通过时：

`idle -> writing -> reviewing -> rewriting -> done`

对应文案：

- `Writer Agent 正在起草...`
- `Review Agent 正在审查...`
- `Writer Agent 正在修订...`

PRD 页面下方还会展示：

- 审查结论摘要
- 是否通过
- 问题列表
- 每个问题的严重级别、章节、问题描述和修改建议

## 当前取舍

这一版刻意保持简单，没有加入：

- 多 reviewer 并行
- reviewer 自动改稿
- 多轮 review/rewrite 循环
- 版本 diff 展示
- 用户手动确认后再决定是否重写

现在的策略是：

- review 通过就直接结束
- review 不通过就自动重写 1 次

## 本地验证

已完成验证：

- Python 相关文件通过 `py_compile`
- 前端通过 `npm run build`

## 后续可选增强

如果继续围绕 `/v2` 迭代，推荐优先级：

1. 增加“只审查不自动重写”的开关
2. 支持用户在 review 面板中确认后再触发重写
3. 为 review JSON 增加更严格的 schema 校验
4. 将 `/v2` 的 API 文档生成也升级成 writer/reviewer 模式
