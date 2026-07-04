# 00 - 为什么要做观测与 Token 预算

v2 已经跑通一条完整链路：结构化表单 → 澄清对话 → PRD（Writer / Review / Rewrite）→ 接口文档 → 提示词。Session 能持久化，Review Agent 能拦住明显漏项，SSE 也能把生成过程推给前端。

但真正用起来，还是会反复碰到同一种无力感：**流程明明在跑，你却说不清它为什么慢、为什么贵、为什么某次突然失败。**

用户点「生成 PRD」，Review 阶段正文停住不动，像卡死了；接口文档要等半分钟——是模型慢，还是 prompt 太大？澄清聊久一点，一点生成就报错——是上下文满了，还是别的原因？账单变高了——是哪一步在烧 token？

这些问题，靠猜解决不了。

## 多 Agent 流水线，默认是「盲飞」

v2 不是「问一次、答一次」的简单聊天。一次 PRD 生成，后端可能连续调用 3～4 次模型：Writer 起草、Review 审查、必要时 Rewrite 修订；后面还有接口文档、提示词、摘要回填、文档优化。

当前 LLM 调用分散在多个 service 里，出了错 mostly 只有 `logger.exception`，没有：

- 这次请求的唯一 ID，没法把日志串起来
- 每一步 input / output token 用了多少
- 每一步花了多少毫秒
- 整次生成总共调了几次、哪一步最重

**观测**要补的就是这层 visibility。

![从盲飞到可观测的多 Agent 流水线](https://pic.niumianoffer.com/images/fs/opt1-00-observability-pipeline.png)

## Token 预算是另一层问题

每次调用模型，上下文里塞着 system prompt、结构化摘要、澄清对话、PRD 正文、RAG 片段、固定模板…… 对话越长、文档越大，input 越高。

约束来自几层，容易混为一谈：

| 层级 | 谁规定 | 超了会怎样 |
|------|--------|------------|
| 模型窗口 | 厂商（查注册表） | API 报错，用户看到「生成失败」 |
| 单次输出 | 代码里 `max_tokens` | 回复被截断，PRD 缺章节 |
| 业务策略 cap | **`.env` 我们自己定** | 发送前 warn / 拒绝，给出明确说明 |

前两层的失败，用户往往不知道是「聊太长了」。**Token 预算**要做的，是在**每次**调用模型之前估算 prompt 有多大，接近上限时提前 warn 或拦截，而不是 silent 失败。

### 两层限速（物理顶 + 业务顶）

- **物理顶（模型注册表）**：DeepSeek v4-flash 约 1M token/次调用——再长会撞 API。
- **业务顶（`.env`）**：澄清 cap 6 万、PRD 单次 cap 10 万等——**故意比模型窗口小**，让用户早点收束，而不是聊到接近 1M 才出事。

每次 API 调用独立检查，取 **min(业务 cap, 模型可用输入空间)** 作为有效 budget，再算占用比例。澄清第 6 轮若只有约 1 万 token，对 1M 物理顶几乎无感；对 6 万业务顶也通常仍 ok——**要靠业务 cap 才会在合适时机 amber 提示**。

![Token 双层预算与调用前检查](https://pic.niumianoffer.com/images/fs/opt1-00-token-budget-check.png)

## 大概怎么做

观测和预算共用一条 **LLM 调用包装层**，挂在现有 `get_llm()` 外面：

```
前端 AppV2
  → API（SSE / JSON）
  → Request 中间件（request_id）
  → LLM 包装层
       ├─ 调用前：查模型注册表 + 业务 cap → 估算 token → 检查 budget
       ├─ 调用中：记录 step、耗时
       └─ 调用后：累计 tokens，写日志
  → 实际模型 API
  → SSE run_summary 回传前端
```

**观测（事后）**

- 每个 HTTP 请求一个 `request_id`
- 每次 LLM 调用打标签：`prd_writer`、`prd_review`、`chat_continue` 等
- 记录 input/output tokens、duration_ms
- SSE 流程结束时发 `run_summary`，日志打单行 JSON

**Token 预算（事前）**

- 模型注册表提供物理顶（先 DeepSeek + default fallback）
- `.env` 提供各 step 的业务 cap
- 发送前用 tiktoken（或字符 heuristic）估算 messages 大小
- warn 模式：超阈值仍调用，但打日志、回传 `context_usage`
- reject 模式：超阈值直接返回明确错误，不消耗 LLM

**前端展示**

- 生成中：阶段 Stepper + 已用时（不要假进度条）
- 完成后：折叠「耗时 · 约 X tokens · 复制 request_id」
- 澄清过长：自然语言提示「可以准备生成 PRD 了」，不展示 token 百分比

## 做了之后有什么优势

**对你（开发/运维）**

- 用户报「生成失败」，用 `request_id` 能在日志里定位到具体 step
- 能回答：一次 PRD 哪步 input 最大、哪步最慢、一共调了几次模型
- 调业务 cap 有数据依据，不是拍脑袋
- 换模型时物理顶查表自动更新，业务 cap 仍可单独调
- 成本异常时能追到是哪类流程在烧 token

**对用户**

- 生成 PRD 时知道「在审查还是起草」，Review 阶段不会误以为卡死
- 对话太长时有明确提示，而不是突然失败
- 超预算时有中文说明和下一步建议，而不是 cryptic API 错误

**对 v2 工程**

- LLM 调用有统一入口，后续加缓存、限流、换模型都有挂点
- 观测字段与 SSE 协议对齐，前端可以渐进接入，不破坏现有流程

观测解决「发生了什么」；预算解决「还能不能继续」。两者一起，把 v2 从盲飞变成可度量、可管控的多 Agent 流水线。
