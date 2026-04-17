# Skill 集成过程

## 1. 一开始的问题

在开始做 `/v2` 时，`prd-generator` skill 已经有了第一版目录结构，但它还只是一个“设计骨架”，并没有真正接入系统主链路。

最初的问题是：

- skill 文件存在，但后端没有实际消费它们
- schema 定义存在，但前端没有真正对齐
- 生成过程还没有真正变成“围绕 skill 契约运行”

## 2. 集成目标

Skill 集成主要想完成三件事：

1. 后端生成 PRD 时真正读取 skill 文件
2. 前端录入对齐 skill 的 schema
3. skill 不依赖某个 Agent 平台，而是项目内通用能力包

## 3. 后端集成做了什么

### 3.1 Skill 文件加载

在 `document_service.py` 里增加了 `_load_skill_artifact()`，从：

```text
skills/prd-generator/
```

中读取：

- `instructions.md`
- `references/prd-template.md`
- `references/writing-rules.md`
- `references/field-schema.json`

### 3.2 基于 summary 的 PRD Prompt 组装

新增 `_build_prd_from_summary_prompt()`，把：

- 结构化摘要
- skill 写作规则
- skill 指令
- PRD 模板

统一组装进一条更稳定的 Prompt。

### 3.3 新接口

新增：

`/generate-prd-from-summary-stream`

这让结构化摘要第一次成为真正的后端一等输入。

## 4. 前端集成做了什么

### 4.1 表单结构对齐 schema

旧版表单更适合“启发式输入”，新版 `/v2` 表单更适合“准 schema 输入”。

### 4.2 JSON 预览

为了让这套 skill 契约可见，前端增加了：

- `requirements_summary` JSON 预览

这一步非常关键，因为它让用户第一次看到：

> 页面里录入的数据，最终到底变成了什么结构化对象。

## 5. 集成时的一个重要选择

用户明确表示，希望 skill 是“像 OpenClaw 那种通用能力”，而不是强依赖 Codex 或 Claude Code。

这直接影响了 skill 包的组织方式：

- 不做平台私有格式
- 不把核心逻辑写死在某个 Agent 平台指令里
- 尽量让 skill 文件本身可迁移

## 6. 这一步的最大收获

Skill 集成完成之后，系统第一次具备了这样一种能力：

> 不是“网页调用一个 Prompt”，而是“网页调用一个 skill 驱动的文档生成流程”。

这一步虽然外表看起来只是几个文件与接口改动，但对整个项目定位其实是一次升级。
