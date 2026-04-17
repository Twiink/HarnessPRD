# Skill 运行时契约

## 1. 什么叫运行时契约

运行时契约的意思是：

> skill 不是一堆散乱文件，而是一套运行时可以稳定消费的输入/输出/约束定义。

在 `prd-generator` 里，这个契约主要由 `skill.yaml` 决定。

## 2. 输入契约

### 2.1 当前约定

- 输入格式：`json`
- 主 schema：`references/field-schema.json`
- 最低必填：`product_name`、`product_goal`、`target_users`、`platform`、`mvp_features`

### 2.2 为什么不要求用户填满所有字段

因为 skill 的目标不是要求人一次写完，而是：

- 先拿到足够稳定的结构化骨架
- 再通过澄清对话补齐模糊点

所以契约强调的是“可合法消费”，不是“一次填满全部信息”。

## 3. 输出契约

### 3.1 当前约定

- 输出格式：Markdown
- 模板来源：`references/prd-template.md`
- 风格要求：
  - concise
  - execution-oriented
  - low-redundancy
  - structured-first

### 3.2 输出不是自由文本

虽然最终表现形式是 Markdown，但它其实是：

- 有固定章节
- 有固定表格
- 有固定字段语义

所以它更接近“模板化结构化文档”，不是普通自然语言作文。

## 4. 约束契约

`skill.yaml` 里还写了显式约束，例如：

- 不编造业务事实
- MVP 功能优先表格化
- 技术规格区分确定项和建议项
- 保持固定章节结构

这些约束的意义在于：即使模型更换了，也要尽量维持同样的结果边界。

## 5. 工作流契约

`workflow` 当前定义为：

```yaml
workflow:
  - validate_input
  - normalize_requirements
  - deduplicate_content
  - map_to_template
  - render_prd
```

这很重要，因为它说明：

- 不是拿输入直接丢给模型
- 中间应该经过“校验、规整、去重、模板映射”这些逻辑概念

即使今天这些步骤还没有全部做成显式代码，它们也已经作为契约存在。

## 6. 质量检查契约

当前还定义了 `quality_checks`：

- 必要章节齐全
- MVP 为表格
- 范围内/范围外不冲突
- 缺失重要信息写 `待确认`

这让未来扩展自动验证时，有了天然落点。

## 7. 为什么这对多运行时兼容很关键

只要不同运行时都遵守这套契约：

- Codex 可以消费
- Claude Code 可以消费
- OpenClaw 风格运行时可以消费
- 自研后端也可以消费

兼容的关键不是“同一个 prompt”，而是“同一个 contract”。
