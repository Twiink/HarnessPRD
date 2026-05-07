# v2 开发记录索引

这组文档记录了 `/v2` 工作台从最初的一个想法，到真正能跑起来的全过程。

它不是说明书，也不是架构文档。如果你想知道"这个系统最终是什么样的"，去看 `wiki/skills/`。这里记录的是：**我们是怎么一步步把它做出来的，踩了哪些坑，做了哪些取舍，以及为什么这么做。**

---

## 阅读顺序

| 文档 | 内容 |
|------|------|
| [00-background-and-goals.md](./00-background-and-goals.md) | 为什么要做 `/v2`，它解决了什么问题，最初怎么想的 |
| [01-first-version.md](./01-first-version.md) | 第一版 `/v2` 做了什么，跑通了什么，留下了哪些明显问题 |
| [02-skill-integration.md](./02-skill-integration.md) | 把 `prd-generator` skill 真正接进后端和前端的过程 |
| [03-backfill-and-diff.md](./03-backfill-and-diff.md) | "AI 补完的信息要写回结构化数据"——回填、diff、确认机制怎么一步步成型 |
| [04-json-and-runtime-issues.md](./04-json-and-runtime-issues.md) | 最折磨人的那些问题：JSON 解析失败、服务没重启、Prompt 边界缺失 |
| [05-workbench-expansion.md](./05-workbench-expansion.md) | `/v2` 从"单条流程"升级成"可跳步工作台"的过程 |
| [06-ux-fixes-and-iteration.md](./06-ux-fixes-and-iteration.md) | 重复消息、顺序问题、按钮命名、阶段导航——体验层的连续修正 |
| [07-summary-and-retrospective.md](./07-summary-and-retrospective.md) | 整体复盘：哪些决策是对的，哪些坑最值得记住，接下来还差什么 |
| [08-api-docs-rag-design.md](./08-api-docs-rag-design.md) | 接口文档生成前加了一层本地 RAG——设计思路、实现细节、局限与演进方向 |
| [09-vibe-coding-history-and-prompts.md](./09-vibe-coding-history-and-prompts.md) | 从 v1 到 v2 的 Vibe Coding 过程复盘：需求怎么提出、功能怎么长出来、提示词范式怎么沉淀 |

---

## 适合谁看

**非技术背景（产品、运营、感兴趣的人）**
可以先读 00、01、05、07，了解这个产品是怎么从一个想法走到今天的，以及核心的产品设计逻辑。不需要看代码，文字本身就能讲清楚。

**工程师和技术同学**
全部都值得读。03、04、08 是技术细节最密集的部分，有具体的代码、算法和踩坑记录。

**准备继续迭代 `/v2` 的人**
重点看 03、04、05、07、08，它们记录了哪些已经做得很稳，哪些还没做完，以及为什么当时做了特定取舍。

---

## 和其他文档的关系

- [`wiki/skills/`](../skills/README.md)：讲这套系统**为什么这样设计**
- `wiki/v2record/`：讲这套系统**是怎么一步一步做出来的**
