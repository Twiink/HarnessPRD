# Skill 集成过程

> 这篇记录了"把 prd-generator skill 真正接进系统"这件事的过程。在此之前，skill 只是一个目录，并没有真正参与文档生成。

---

## 1. 先说清楚：什么是 skill？

**白话说**：skill 就是一份"标准化的工作手册"。它告诉系统：生成这类文档时，该遵循什么规则、参考什么模板、按什么格式输出。

具体来说，`prd-generator` 这个 skill 包含几类文件：

- `instructions.md`：这次生成要做什么、怎么做
- `references/prd-template.md`：PRD 的标准模板
- `references/writing-rules.md`：写作风格规范
- `references/field-schema.json`：输入数据的字段定义

有了 skill，生成文档的逻辑不再写死在代码里，而是可以被独立维护、随时更新，也可以复用到其他地方。

---

## 2. 集成之前，系统是什么状态？

在开始集成之前，`prd-generator` skill 已经有了目录和文件，但问题是：

- skill 文件存在，**但后端没有真正读取它们**
- schema 定义写了，**但前端录入没有真正对齐它**
- 生成过程还没有变成"围绕 skill 契约运行"——实际上还是老方式

也就是说，skill 只是个"摆在那里的文件夹"，没有真正参与系统运转。

---

## 3. 集成目标

集成这一步要完成三件事：

1. 后端生成 PRD 时，真正读取并使用 skill 文件
2. 前端录入数据，真正对齐 skill 定义的字段结构
3. skill 不依赖任何特定 Agent 平台，作为项目内通用能力包存在

---

## 4. 后端集成做了什么

### 4.1 加载 Skill 文件

在 `document_service.py` 里增加了 `_load_skill_artifact()` 函数，从以下目录加载 skill 文件：

```text
skills/prd-generator/
  ├── instructions.md
  └── references/
        ├── prd-template.md
        ├── writing-rules.md
        └── field-schema.json
```

之前，这些文件只是"放在那里"；现在，后端每次生成 PRD 时都会读取它们。

### 4.2 组装更稳定的 Prompt

新增 `_build_prd_from_summary_prompt()` 函数，把以下内容统一拼成一条 Prompt：

- 结构化摘要（用户填写的需求）
- skill 写作规则
- skill 生成指令
- PRD 模板

**白话说**：相当于给 AI 准备好一套完整的"作业指导书"，而不是只给它一个需求说"帮我写 PRD 吧"。

### 4.3 新增接口

```
POST /api/conversation/generate-prd-from-summary-stream
```

这让结构化摘要第一次成为真正的后端一等输入——后端接口专门为它设计，而不是把摘要混在自然语言里凑合用。

---

## 5. 前端集成做了什么

### 5.1 表单结构对齐 Schema

旧版表单更适合"想到哪填哪"的启发式填写，新版 `/v2` 表单更像"按格式填写的结构化表单"，字段约束更严格，直接对应 skill 里定义的字段。

### 5.2 增加 JSON 预览

为了让用户能够看见"我在前端填的东西，最终变成了什么数据结构"，前端增加了 `requirements_summary` 的 JSON 预览。

**为什么这个预览很重要？**

以前，用户填完表单就发出去了，不知道 AI 收到的到底是什么。现在，用户可以直接看到结构化数据长什么样，这既增加了透明度，也帮助发现格式问题。

---

## 6. 一个重要的设计选择

集成过程中，用户明确表达了一个立场：

> 希望 skill 是"像 OpenClaw 那种通用能力"，而不是强依赖 Codex 或 Claude Code。

这一句话直接影响了 skill 包的组织方式：

- 不使用某个 Agent 平台的私有格式
- 核心逻辑不写死在某个平台的指令格式里
- skill 文件本身要尽量可迁移——换个平台也能用

---

## 7. 这一步最大的意义

Skill 集成完成之后，系统第一次具备了这种能力：

> 不是"网页调用一个 Prompt"，而是"网页调用一个 skill 驱动的文档生成流程"。

外表上看，只是几个文件被读了、接口签名改了一下。但从系统定位来说，它是一次升级：

- 之前：页面通过 Prompt 直接驱动 AI
- 之后：页面通过调用 skill 来驱动 AI，skill 负责所有生成规则

这为后续的"多 skill 扩展""skill 注册中心""跨平台复用"打下了基础。
