# v2 开发记录索引

这组文档专门记录 `/v2` 工作台从设计到落地的过程，不是最终设计说明，而是**开发过程记录、问题轨迹、修复思路和复盘总结**。

如果 `wiki/skills/` 更像“方法论和架构说明”，那么 `wiki/v2record/` 更像“项目实战日志”。

## 阅读顺序

| 文档 | 内容 |
|------|------|
| [00-background-and-goals.md](./00-background-and-goals.md) | 为什么要做 `/v2`，它和旧版页面的关系是什么 |
| [01-first-version.md](./01-first-version.md) | 第一版 `/v2`：结构化表单、澄清对话、PRD 生成 |
| [02-skill-integration.md](./02-skill-integration.md) | 把 `prd-generator` skill 真正接进后端和前端 |
| [03-backfill-and-diff.md](./03-backfill-and-diff.md) | 回填、diff、确认机制是怎么逐步成型的 |
| [04-json-and-runtime-issues.md](./04-json-and-runtime-issues.md) | JSON 回填失败、服务未重启、解析异常等问题实录 |
| [05-workbench-expansion.md](./05-workbench-expansion.md) | `/v2` 从单一路径升级成可跳步工作台的过程 |
| [06-ux-fixes-and-iteration.md](./06-ux-fixes-and-iteration.md) | 重复消息、流程顺序、按钮命名、阶段导航等体验修正 |
| [07-summary-and-retrospective.md](./07-summary-and-retrospective.md) | 整体总结：哪些决策是对的，哪些还需要继续演进 |

## 适合谁看

- 想快速理解 `/v2` 是怎么从 0 到 1 做出来的人
- 想知道这套系统真实踩了哪些坑的人
- 准备继续迭代 `/v2` 工作台的人
- 想了解“技能化 PRD 生成”落地过程的人

## 和其他文档的关系

- [`wiki/skills/`](../skills/README.md)：讲这套系统为什么这样设计
- `wiki/v2record/`：讲这套系统是怎么一步一步做出来的
