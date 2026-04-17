# Skill 包结构：为什么要拆成 `skill.yaml`、`instructions.md` 和 `references/`

第一次看到 `skills/prd-generator/` 这个目录时，很多人会有一个很直接的疑问：

为什么不就写一个 Prompt 文件完事？  
为什么还要拆出 `skill.yaml`、`instructions.md`、`references/` 这么多层？

这个问题问得很好，因为这恰好能看出 skill 设计和普通 Prompt 封装的分界线。

## 先看当前结构

现在的 `prd-generator` 长这样：

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

表面上看这只是文件组织问题，实际上每一层都在回答不同的问题。

## `skill.yaml`：回答“这是什么能力”

`skill.yaml` 最像能力说明书的封面页。

它不负责教模型怎么一步一步思考，也不负责存放模板细节。它的作用更像是把这项能力的边界先钉死。

比如在这里，你能看到：

- 这个 skill 叫什么
- 它接受什么输入
- 输出什么格式
- 默认约束是什么
- 工作流大概有哪些步骤

为什么它必须单独存在？因为这些信息不只是给模型看的，也是给运行时看的。

如果没有它，系统就只能靠某段 Prompt 自己“顺便”说明：

- 输入大概长什么样
- 输出大概长什么样
- 哪些规则比较重要

这样做短期没问题，长期一定会乱。

## `instructions.md`：回答“这项能力应该怎么执行”

`instructions.md` 更像真正写给模型看的操作说明书。

它和 `skill.yaml` 的关系，有点像这样：

- `skill.yaml` 负责定义契约
- `instructions.md` 负责定义过程

在这里面，最重要的不是“多详细”，而是“多清楚”。

比如：

- 先校验输入
- 再规整需求
- MVP 功能要优先落成表格
- 技术规格里要区分确定项和建议项
- 缺失信息统一写 `待确认`

这些东西如果都塞进 `skill.yaml`，会显得过于结构化、读起来僵；  
如果全塞进一个巨大 Prompt，又会和运行时约束混在一起。

所以拆出来反而更自然。

## `references/`：回答“执行这项能力需要参考什么”

这部分是很多 skill 设计里最容易被忽略，但其实最值钱的一层。

因为一项能力真正稳定下来之后，最宝贵的往往不只是 Prompt 本身，而是：

- 输入 schema
- 输出模板
- 写作规则
- 真实示例

这些东西如果继续埋在 Prompt 里，维护成本会很高。

而一旦单独放进 `references/`：

- 前端可以直接对齐 schema
- 后端可以直接读取模板
- 例子可以被复用做测试
- 运行时也更容易做动态装载

这时 skill 就开始像一个真正的“能力包”，而不是“提示词文本”。

## 为什么 `examples/` 也很重要

很多系统只会写规则，不会写例子。  
这其实会让能力长期处于一种“大家大概知道想要什么，但没人说得特别准”的状态。

示例的价值在于，它把抽象要求落到了真实输入输出上。

比如看到：

- `friend-circle-copywriter.input.json`
- `friend-circle-copywriter.output.md`

你马上就能知道：

- 输入应该收敛到什么粒度
- 输出应该控制在什么风格
- 这套 skill 生成出来的东西到底算不算合格

这比单纯写一堆原则有效得多。

## 这种拆法的真正意义

如果把 skill 包理解成一个独立产品，那么这几层大概对应的是：

- `skill.yaml`：产品简介与接口说明
- `instructions.md`：操作手册
- `references/`：附件、模板、样例、规范

这也是为什么它比“单个 Prompt 文件”更接近 OpenClaw 那种通用 skill 的味道。

因为它不是把所有东西都压成一句“请你做 X”，而是开始认真回答：

> 这项能力到底由哪些信息构成？

一旦这个问题被回答清楚，skill 才真正具备独立性。
