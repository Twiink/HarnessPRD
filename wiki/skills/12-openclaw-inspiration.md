# OpenClaw 风格启发

## 1. 这里说的“参考 OpenClaw”是什么意思

这里的“参考 OpenClaw”，不是说当前实现已经与 OpenClaw 完全兼容，而是说设计方向上借鉴了这类系统的核心思路：

> 把能力做成通用 skill，而不是做成平台私有 Prompt。

## 2. 被借鉴的核心思想

### 2.1 能力包要独立存在

skill 不应该埋在某个页面组件或某段后端代码里，而应该能独立存放、独立描述。

### 2.2 输入输出要显式

不能靠人记忆“这个能力通常怎么用”，而要让运行时能读懂：

- 输入格式
- 输出格式
- 约束
- 工作流

### 2.3 参考资料外置

模板、schema、示例、规则都不该只写在 Prompt 里。

### 2.4 可被多个 Agent 消费

一个 skill 的价值不该取决于它是不是只能被某一个平台用。

## 3. 当前实现如何体现这种启发

### 3.1 独立 skill 目录

`skills/prd-generator/`

### 3.2 独立 skill 契约

`skill.yaml`

### 3.3 独立参考文件

`references/`

### 3.4 前端与 skill 契约对齐

`/v2` 的结构化录入不是面向页面私有状态，而是面向 `requirements_summary`。

## 4. 当前没有做、但明显可以继续朝 OpenClaw 风格演进的点

### 4.1 多 skill 注册中心

现在只有 `prd-generator`，未来可以有：

- `api-designer`
- `prompts-generator`
- `requirements-refiner`

### 4.2 skill adapter

当前还没有针对不同运行时的 adapter 文件。

### 4.3 skill marketplace / registry

现在 skill 还是项目内文件夹，还不是注册化能力仓库。

## 5. 为什么这种设计值得

因为一旦能力被独立出来，它的复用面会很大：

- 可以服务网页产品
- 可以服务命令行 Agent
- 可以服务 IDE Agent
- 可以服务多模型后端

它的价值就不再依赖某个具体页面。
