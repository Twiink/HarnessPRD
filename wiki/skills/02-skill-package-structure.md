# Skill 包结构

## 1. 当前目录

当前 `prd-generator` 的目录如下：

```text
skills/prd-generator/
├── skill.yaml
├── instructions.md
└── references/
    ├── field-schema.json
    ├── prd-template.md
    ├── writing-rules.md
    └── examples/
        ├── friend-circle-copywriter.input.json
        └── friend-circle-copywriter.output.md
```

## 2. `skill.yaml`

位置：

[`skills/prd-generator/skill.yaml`](../../skills/prd-generator/skill.yaml)

它定义的是**能力契约**，不是具体实现代码。

### 2.1 它负责什么

- skill 名称
- skill 描述
- 输入格式与 schema
- 输出格式与模板
- 默认约束
- 工作流步骤
- 质量检查项

### 2.2 为什么它重要

因为运行时不应该靠猜：

- 这个 skill 要什么输入？
- 输出什么？
- 缺失值怎么表示？
- 执行时最重要的约束是什么？

这些都应该能从一个机器可读文件里拿到。

## 3. `instructions.md`

位置：

[`skills/prd-generator/instructions.md`](../../skills/prd-generator/instructions.md)

它定义的是**执行说明**。

### 3.1 它负责什么

- 输入契约的解释
- 输出契约的解释
- 按章节的生成规则
- 去重规则
- 写作风格约束
- 最终检查清单

### 3.2 为什么不直接全塞进 `skill.yaml`

因为：

- `skill.yaml` 更适合结构化元信息
- `instructions.md` 更适合人和模型共同阅读

两者分离后，skill 的结构和执行逻辑都会更清楚。

## 4. `references/`

`references/` 是 skill 的知识附件。

### 4.1 `field-schema.json`

定义输入结构与字段形态，是前后端都依赖的核心文件。

### 4.2 `prd-template.md`

定义输出 PRD 的标准章节结构，是生成结果的“骨架”。

### 4.3 `writing-rules.md`

定义文风和写作边界，例如：

- 少空话
- 少重复
- MVP 用表格
- 不要编造业务事实

### 4.4 `examples/`

提供一组真实输入输出，用来：

- 帮助理解 skill 期待的输入长什么样
- 验证 skill 的输出是不是在预期区间内
- 为未来自动评估做样例基础

## 5. 为什么这套结构是可迁移的

因为没有任何一个核心文件天然绑定到某个 SDK：

- `skill.yaml` 是通用配置
- `instructions.md` 是普通 Markdown
- `field-schema.json` 是标准 JSON Schema
- `prd-template.md` 是普通 Markdown 模板

只要一个运行时具备：

1. 读取文件
2. 组装 Prompt
3. 调模型
4. 返回结果

它就可以消费这套 skill。
