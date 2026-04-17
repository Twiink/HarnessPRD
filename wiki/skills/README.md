# Skills 文档索引

这组文档专门解释 VibeCoding 新一代 `skill-first` 设计，重点覆盖：

- 为什么要从“prompt 驱动”升级到“skill + schema + workflow 驱动”
- `skills/` 目录如何组织、如何被解析、如何保持平台无关
- 前端结构化表单如何映射到后端 schema
- 为什么需要“澄清对话 -> 结构化回填 -> diff 预览 -> PRD 生成”的闭环
- 回填中最容易出现的 JSON 问题，以及当前怎么兜底
- 这套设计如何兼容多个模型、多个 Agent 运行时
- 当前与 Claude / Claude Code 协作时的实际工作方式

## 阅读顺序

| 文档 | 内容 |
|------|------|
| [00-overview.md](./00-overview.md) | 总览：这套 Skills 架构到底解决了什么问题 |
| [01-design-philosophy.md](./01-design-philosophy.md) | 设计理念：为什么强调 skill-first、schema-first、workflow-first |
| [02-skill-package-structure.md](./02-skill-package-structure.md) | 技能包结构：`skill.yaml`、`instructions.md`、`references/` 各自负责什么 |
| [03-skill-runtime-contracts.md](./03-skill-runtime-contracts.md) | 运行时契约：输入/输出/约束/工作流如何定义和消费 |
| [04-directory-and-file-resolution.md](./04-directory-and-file-resolution.md) | 目录解析与文件解析：系统怎么找到 skill、模板、schema 和示例 |
| [05-frontend-schema-mapping.md](./05-frontend-schema-mapping.md) | 前端结构化录入：表单如何稳定映射到 schema |
| [06-v2-workbench-flow.md](./06-v2-workbench-flow.md) | `/v2` 工作台：完整链路、跳步能力、阶段导航、会话恢复 |
| [07-clarification-loop.md](./07-clarification-loop.md) | 澄清对话：为什么不能一开始就生成 PRD，以及怎么限制 AI 只做澄清 |
| [08-prd-generation-pipeline.md](./08-prd-generation-pipeline.md) | PRD 生成流水线：结构化摘要、对话补充、模板约束如何组合 |
| [09-backfill-diff-and-approval.md](./09-backfill-diff-and-approval.md) | 回填机制：从对话回写 schema、diff 预览、确认后生成 |
| [10-json-failure-modes.md](./10-json-failure-modes.md) | JSON 故障手册：最常见的问题、修复策略、接口错误设计 |
| [11-model-independence.md](./11-model-independence.md) | 模型独立性：怎么兼容 Claude、OpenAI 以及未来其他模型 |
| [12-openclaw-inspiration.md](./12-openclaw-inspiration.md) | OpenClaw 启发：这套设计如何借鉴“通用 skill”思路 |
| [13-claude-collaboration.md](./13-claude-collaboration.md) | 当前与 Claude 协作：现状、边界、为什么这套文档仍然需要平台无关 |
| [14-roadmap-and-guidelines.md](./14-roadmap-and-guidelines.md) | 演进路线：接下来怎么把这套系统做得更稳、更强、更通用 |

## 适合谁看

- 想理解这套 `skills` 方案设计全貌的人
- 准备继续做 skill 运行时或 skill 市场的人
- 要把 VibeCoding 接到不同模型或不同 Agent 平台的人
- 想把“PRD -> API -> Prompts”这一套做成独立能力包的人

## 当前代码对应位置

| 目录/文件 | 作用 |
|-----------|------|
| [`skills/prd-generator/skill.yaml`](../../skills/prd-generator/skill.yaml) | 技能包元信息与契约 |
| [`skills/prd-generator/instructions.md`](../../skills/prd-generator/instructions.md) | 技能执行说明 |
| [`skills/prd-generator/references/field-schema.json`](../../skills/prd-generator/references/field-schema.json) | 输入 schema |
| [`backend/services/document_service.py`](../../backend/services/document_service.py) | 技能参考文件加载、PRD 生成、回填同步 |
| [`backend/services/conversation_service.py`](../../backend/services/conversation_service.py) | 对话编排 |
| [`backend/services/prompts.py`](../../backend/services/prompts.py) | 对话与澄清 Prompt |
| [`frontend/src/AppV2.tsx`](../../frontend/src/AppV2.tsx) | `/v2` 工作台、结构化录入、回填 diff、阶段导航 |
| [`frontend/src/services/api.ts`](../../frontend/src/services/api.ts) | 前端 API 编排 |
