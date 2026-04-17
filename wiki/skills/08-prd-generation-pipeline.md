# PRD 生成流水线

## 1. 当前流水线

PRD 生成不是单一步骤，而是一个组合流程：

```text
requirements_summary
+ clarification conversation
+ skill references
+ PRD template
= final PRD
```

## 2. 输入层

主要输入有两类：

1. `requirements_summary`
2. `conversation_messages`

前者是结构化骨架，后者是人工澄清后的补充语义。

## 3. Skill 参考层

生成前会读取这些 skill 文件：

- `references/prd-template.md`
- `references/writing-rules.md`
- `instructions.md`

这些文件告诉模型：

- 文档应该长什么样
- 文风应该如何控制
- 写作过程中哪些事情不能做

## 4. Prompt 组装层

当前在：

[`backend/services/document_service.py`](../../backend/services/document_service.py)

里通过 `_build_prd_from_summary_prompt()` 完成组装。

它会把：

- 结构化摘要 JSON
- 写作规则
- 技能说明
- 模板

拼成一条更明确、更低自由度的生成指令。

## 5. 为什么这比旧模式更稳

旧模式更像：

```text
对话历史 -> PRD
```

新模式更像：

```text
结构化对象 -> 模板化文档
```

这让模型自由发挥的空间显著减少。

## 6. 对话在这里扮演什么角色

对话不是主输入，而是**摘要的补充上下文**。

系统提示词已经明确要求：

> 如果存在补充对话，请优先采用对话中已澄清的内容。

这意味着：

- 结构化摘要负责“骨架”
- 对话负责“修正和补充”

## 7. 为什么 PRD 生成要放在回填之后

因为如果回填还没确认，PRD 可能会基于一份用户未同意的结构化摘要生成。

这会让用户觉得：

- 系统擅自修改了需求
- 文档看起来对，但自己并没有真正确认过

所以正确顺序必须是：

```text
回填 diff -> 用户确认 -> PRD
```

## 8. 当前实现边界

当前 PRD 生成还没有做严格 AST 级验证或后处理重写，它仍然依赖模型产出最终 Markdown。

但因为已经把：

- 输入收敛
- 模板固定
- 规则外置
- 流程显式化

所以它比传统 prompt-only 方案稳很多。
