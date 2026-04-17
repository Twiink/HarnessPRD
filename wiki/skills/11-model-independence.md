# 模型独立性设计

## 1. 什么叫模型独立

模型独立不是说“完全不考虑模型差异”，而是说：

> 核心能力定义不能写死在某一个模型品牌或 SDK 上。

## 2. 当前已经独立的部分

### 2.1 skill 包结构

`skill.yaml`、`instructions.md`、`references/` 都是模型无关的。

### 2.2 输入 schema

`field-schema.json` 是标准 JSON Schema，不依赖 Claude/OpenAI 专属格式。

### 2.3 工作台逻辑

前端 `/v2` 的结构化录入、diff 预览、阶段导航、状态恢复都不依赖具体模型。

### 2.4 服务层抽象

后端通过：

[`backend/services/llm_factory.py`](../../backend/services/llm_factory.py)

来切换 Anthropic / OpenAI。

## 3. 当前还不完全独立的部分

### 3.1 Prompt 仍然是自然语言 Prompt

这意味着模型差异仍会影响：

- 文风
- JSON 稳定性
- 是否过度总结
- 是否容易跑题

### 3.2 缺少 adapter 层

当前 skill 包还没有独立的：

- `adapters/claude.md`
- `adapters/openai.md`
- `adapters/openclaw.md`

## 4. 为什么这不矛盾

模型独立不是“一步到位”，而是“先把真正模型无关的东西抽出来”。

当前已经抽出来的部分是最重要的：

- skill 定义
- 输入输出协议
- 参考资料
- 工作流结构

这些抽出来后，再做 model adapter 就容易很多。

## 5. 当前如何切换模型

当前项目通过配置切换：

- `anthropic`
- `openai`

而 skill 层不需要知道是哪一个。

这意味着：

- skill 关心“要做什么”
- `llm_factory` 关心“用哪个模型做”

这是一个很健康的分层。

## 6. 为什么这套设计天然适合扩展到更多模型

未来如果接入更多模型，优先改的不会是：

- skill 包
- 前端 schema
- 工作台流程

而主要是：

- `llm_factory`
- 少量 Prompt adapter
- 失败兜底策略

这正说明当前设计已经具备较好的模型独立性。
