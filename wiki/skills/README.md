# Skills 文档索引

这组文档讲的不是“某个 Prompt 怎么写”，而是一整套能力是怎么被拆出来、封装起来、再被前后端消费的。

如果只看现在的产品表面，`/v2` 好像只是多了一个结构化表单、多了一个回填 diff、多了几步文档生成。但把这些东西串起来看，你会发现它背后其实已经不是传统的“页面调模型”了，而是在往一套真正可迁移的 `skill-first` 架构走。

这也是这一组文档存在的意义。

它们主要解释几件事：

- 为什么我们不再满足于“写一段 Prompt 让模型生成 PRD”
- 为什么要把 PRD 生成抽成 skill，而不是继续塞在页面逻辑里
- 为什么前端要先做结构化录入，而不是让模型自由理解输入
- 为什么要有“澄清 -> 回填 -> diff -> 确认”这一整段中间流程
- 这套 skill 设计为什么会参考 OpenClaw，但又不强绑定任何一个 Agent 平台
- 它今天怎么和 Claude 协作，未来又怎么兼容更多模型

## 推荐阅读顺序

如果你第一次接触这套设计，建议按下面的顺序看：

| 文档 | 适合什么时候看 |
|------|----------------|
| [00-overview.md](./00-overview.md) | 先建立全局印象：这套 Skills 架构到底解决了什么问题 |
| [01-design-philosophy.md](./01-design-philosophy.md) | 想知道为什么整个设计要从 Prompt 思维切到 skill-first |
| [02-skill-package-structure.md](./02-skill-package-structure.md) | 想理解 skill 包本身长什么样、为什么这么拆 |
| [03-skill-runtime-contracts.md](./03-skill-runtime-contracts.md) | 想理解输入、输出、约束、工作流这些“契约”怎么发挥作用 |
| [04-directory-and-file-resolution.md](./04-directory-and-file-resolution.md) | 想知道系统到底是怎么找到这些 skill 文件并读进去的 |
| [05-frontend-schema-mapping.md](./05-frontend-schema-mapping.md) | 想看前端表单怎么稳定映射到后端 schema |
| [06-v2-workbench-flow.md](./06-v2-workbench-flow.md) | 想理解 `/v2` 为什么更像工作台，而不是普通向导 |
| [07-clarification-loop.md](./07-clarification-loop.md) | 想理解为什么澄清不能省，而且为什么它必须先于 PRD |
| [08-prd-generation-pipeline.md](./08-prd-generation-pipeline.md) | 想看结构化摘要、对话、模板、规则是怎么拼成最终 PRD 的 |
| [09-backfill-diff-and-approval.md](./09-backfill-diff-and-approval.md) | 想看回填、diff、确认这套机制为什么是整条链路的关键 |
| [10-json-failure-modes.md](./10-json-failure-modes.md) | 想看最真实的坑：为什么“让模型吐 JSON”总是容易出问题 |
| [11-model-independence.md](./11-model-independence.md) | 想知道这套东西为什么能不绑某个模型 |
| [12-openclaw-inspiration.md](./12-openclaw-inspiration.md) | 想看 OpenClaw 风格到底给了这套设计什么启发 |
| [13-claude-collaboration.md](./13-claude-collaboration.md) | 想看今天这套系统和 Claude / Claude Code 是怎么协作的 |
| [14-roadmap-and-guidelines.md](./14-roadmap-and-guidelines.md) | 想看未来怎么把这套东西继续做大、做稳、做通用 |

## 这组文档最适合谁

它不是写给“只想知道怎么点按钮”的用户的。它更适合下面几类人：

- 想把 PRD、接口设计、提示词这些能力真正做成独立 skill 的人
- 想把 VibeCoding 接到不止一个模型、一个 Agent 运行时的人
- 想理解 `/v2` 为什么看起来比旧版复杂，但其实更可靠的人
- 想把“AI 生成文档”这件事做成工程系统，而不是 Prompt 技巧的人

## 当前代码入口

如果你准备边看文档边对照代码，下面这些入口最关键：

| 文件 | 作用 |
|------|------|
| [`skills/prd-generator/skill.yaml`](../../skills/prd-generator/skill.yaml) | skill 的能力契约 |
| [`skills/prd-generator/instructions.md`](../../skills/prd-generator/instructions.md) | skill 的执行说明 |
| [`skills/prd-generator/references/field-schema.json`](../../skills/prd-generator/references/field-schema.json) | 输入 schema |
| [`backend/services/document_service.py`](../../backend/services/document_service.py) | skill 文件读取、PRD 生成、回填同步 |
| [`backend/services/conversation_service.py`](../../backend/services/conversation_service.py) | 对话编排 |
| [`backend/services/prompts.py`](../../backend/services/prompts.py) | 通用对话 Prompt 与澄清专用 Prompt |
| [`frontend/src/AppV2.tsx`](../../frontend/src/AppV2.tsx) | `/v2` 工作台本体 |
| [`frontend/src/services/api.ts`](../../frontend/src/services/api.ts) | 前端对 skill 相关接口的调用封装 |
