# Token 双层预算：模型窗口与策略上限

语言模型有固定的上下文窗口。把太长的输入发给模型，轻则被截断影响输出质量，重则直接报错。但不同步骤对"多长算太长"的标准是不一样的：澄清对话可以很长，写文档的单次调用应该更保守。

harnessprd 用两层约束来管这件事。**第一层是模型硬件上限**，来自模型本身的参数，谁也改不了。**第二层是策略上限**，来自应用层配置，针对不同步骤类型各自设不同的值。Token 预算取两层中更严的那一个。

## 硬件上限：模型配置文件

每个模型能接多长的输入、最多能输出多少 Token，写在 `backend/config/models.yaml` 里。这份文件是**人工维护**的：窗口大小、输出上限来自各模型官方文档，不是运行时自动探测出来的。换模型或厂商更新了规格，改这里就行，不用动业务代码。

项目里目前已配好 DeepSeek 的参数；`.env` 里的 `DEFAULT_LLM_MODEL=deepseek-v4-flash` 决定实际调用哪条记录。以后切 Claude、GPT 等，在 yaml 里补上对应条目（或改已有条目的数值），再把 `.env` 里的模型名改过去即可。

```yaml
# harnessprd/backend/config/models.yaml

# 模型物理顶（来自官方文档，人工维护；换模型时改这里，不改 .env 里的预算数字）
models:
  deepseek-v4-flash:
    provider: openai_compatible
    context_window: 1000000      # 总上下文窗口
    max_output_tokens: 384000    # 单次最多输出多少 Token
    encoding: cl100k_base        # tiktoken 估算用的编码

  deepseek-chat:
    alias_of: deepseek-v4-flash  # 别名，共用同一套物理顶

  claude-3-5-sonnet-20241022:
    provider: anthropic
    context_window: 200000
    max_output_tokens: 8192
    encoding: cl100k_base

  default:                       # 兜底：yaml 里找不到当前模型名时用这条
    context_window: 60000
    max_output_tokens: 8192
    encoding: cl100k_base
```

`.env` 只负责「用哪个模型」；`models.yaml` 负责「这个模型物理上能塞多少」。如果 `.env` 填了一个 yaml 里没有的名字，系统不会硬猜，而是退回 `default` 的窗口和输出上限——偏保守，避免按不存在的大窗口去估算预算。

算输入预算时，会把输出空间先留出来：**输入上限 = context_window − max_output_tokens**。例如 DeepSeek 这条是 100 万窗口、最大输出 38.4 万，输入侧最多约 61.6 万 Token。这样输入和输出不会在同一次调用里互相挤占。

## 策略上限：按步骤分类

不同的调用步骤对输入长度的预期不同，策略上限对此做了分类：

```python
# harnessprd/backend/services/token_estimator.py

# 澄清对话步骤：历史会话累积，允许更长的上下文
_CHAT_HISTORY_STEPS = {LlmStep.CHAT_START.value, LlmStep.CHAT_CONTINUE.value}
# 单次文档生成步骤：一次性调用，过长会挤压输出空间
_SINGLE_CALL_STEPS = {
    LlmStep.PRD_WRITER.value,
    LlmStep.PRD_REVIEW.value,
    LlmStep.PRD_REWRITE.value,
    LlmStep.API_DOCS_GENERATE.value,
    LlmStep.PROMPTS_GENERATE.value,
    LlmStep.DOCUMENT_OPTIMIZE.value,
}
# 辅助步骤：JSON 修复、摘要同步等，使用默认预算
_CONTEXT_BUDGET_STEPS = {
    LlmStep.SUMMARY_SYNC.value,
    LlmStep.JSON_REPAIR.value,
    LlmStep.JSON_REGENERATE.value,
}

def _budget_for_step(step: str) -> int:
    if step in _CHAT_HISTORY_STEPS:
        return settings.chat_history_budget       # 对话类，允许更长
    if step in _SINGLE_CALL_STEPS:
        return settings.single_call_input_budget  # 单次生成，约束更严
    if step in _CONTEXT_BUDGET_STEPS:
        return settings.context_budget_tokens     # 辅助步骤，使用默认预算
    return settings.context_budget_tokens
```

对话类步骤的预算更松，因为澄清对话需要积累上下文；单次文档生成的预算更严，因为过长的输入会挤压输出空间，影响生成质量；JSON 修复和摘要同步是轻量辅助调用，用默认预算。

全部 13 个 `LlmStep` 值的分类如下：

| step | 分类 | 适用预算 |
|------|------|---------|
| `chat_start` / `chat_continue` | 对话历史步骤 | `chat_history_budget` |
| `prd_writer` / `prd_review` / `prd_rewrite` | 单次生成步骤 | `single_call_input_budget` |
| `api_docs_generate` / `prompts_generate` / `document_optimize` | 单次生成步骤 | `single_call_input_budget` |
| `summary_sync` / `json_repair` / `json_regenerate` | 辅助步骤 | `context_budget_tokens` |
| `api_docs_review` / `prompts_review` | 未显式分类，走默认 | `context_budget_tokens` |

## 谁在什么时候检查

预算检查不需要调用方显式触发——它内嵌在 `TrackedChatModel` 的调用路径里。无论是 `ainvoke()` 还是 `astream()`，进入实际调用之前都会先执行 `_run_budget_check()`：

```python
# harnessprd/backend/services/llm_factory.py

async def ainvoke(self, messages, **kwargs):
    # 每次 LLM 调用前，自动运行预算检查
    self._run_budget_check(messages)
    # 检查通过后，才真正发起调用
    started = time.perf_counter()
    response = await self._llm.ainvoke(messages, **kwargs)
    # ...
```

`get_tracked_llm(LlmStep.PRD_WRITER.value, temperature=0.3)` 构造时已绑定了 step 名，`_run_budget_check()` 直接用这个名字从策略表查出对应上限，不需要调用方传入任何额外参数。

## 取有效预算

两层约束取更严的那一个：

```python
# harnessprd/backend/services/token_estimator.py

def resolve_effective_budget(step: str, model: str) -> EffectiveBudget:
    policy_cap = _budget_for_step(step)
    hw_cap = hardware_input_cap(model) if model else policy_cap
    if policy_cap <= hw_cap:
        effective = max(policy_cap, 1)
        source = "policy"      # 策略上限更严
    else:
        effective = max(hw_cap, 1)
        source = "hardware"    # 硬件上限更严
    return EffectiveBudget(
        effective_input_budget=effective,
        policy_cap=policy_cap,
        hardware_cap=hw_cap,
        budget_source=source,
        max_output_tokens=resolve_max_output(model),
    )
```

`budget_source` 字段记录这次是哪一层在约束，方便排查。

![Token 双层预算的有效上限计算](https://pic.niumianoffer.com/images/fs/04-02-token-budget-layers.png)

## Token 估算

知道预算是多少，还得知道这次请求预计消耗多少。这里的估算服务于**预算预警**——判断要不要 warn 或 reject——不是和 API 账单逐字对账。

估算支持两种方式，按环境自动选择：

**本地有 tiktoken 时。** tiktoken 是 OpenAI 发布的本地分词库，在服务端把 messages 数成 Token，不需要额外调模型 API。项目从 `models.yaml` 读取当前模型的 `encoding`（目前各模型都配 `cl100k_base`），对每条消息的 role 和 content 分别编码，再按 Chat 消息格式加上固定的协议开销（每条消息 +4、整段 +2）。对 GPT 系模型，这种计数相对贴近官方规则；对 DeepSeek、Claude 等，分词方式并不相同，这里用的是**同一套 encoding 做近似**，够判断「是否接近预算上限」，但不保证和厂商实际计费完全一致。

**无 tiktoken 或加载失败时。** 退回字符启发式：总字符数 × 0.6。系数 0.6 是适配中文场景的经验值——单个汉字通常对应约 1.5~2 个 Token，乘 0.6 算出来的数往往略低于真实消耗，估算偏保守，能避免因高估而误触发拦截。

`.env` 里 `TOKEN_ESTIMATOR=tiktoken` 控制优先走哪条路；设为其他值则直接用字符估算。

```python
# harnessprd/backend/services/token_estimator.py

def estimate_tokens(messages, step="", model="") -> TokenEstimate:
    caps = resolve(model) if model else resolve("default")
    encoding = _get_encoding(caps.encoding)
    if encoding is not None:
        estimated = _estimate_with_tiktoken(messages, encoding)
        estimator = "tiktoken"
    else:
        estimated = _estimate_with_char_heuristic(messages)
        estimator = "char_heuristic"
    # ...
```

## 三级响应

估算出比率（`ratio = estimated / budget`）之后，判断落在三个区间里的哪个：

```python
# harnessprd/backend/services/token_estimator.py

if estimate.ratio < 0.6:
    level = "ok"
elif estimate.ratio <= 0.95:
    level = "warn"
else:
    level = "exceed"

# reject 模式下超出预算会抛异常，warn 模式下只记日志继续执行
allowed = not (level == "exceed" and mode == "reject")
```

| 比率 | 级别 | 默认行为 |
|------|------|---------|
| < 60% | ok | 正常调用 |
| 60%–95% | warn | 记录警告，继续调用 |
| > 95% | exceed | 取决于 `token_budget_mode` |

预算超出模式（`token_budget_mode`）可配置为 `warn` 或 `reject`。`warn` 模式下超出也继续，只记录日志；`reject` 模式下超出会抛预算超出异常（`BudgetExceededError`），Job 失败。生产环境的保守策略是 `reject`，避免把过长的输入打给模型导致截断；开发阶段设为 `warn` 减少干扰。

## 预算结果的流通

预算检查结果有两个流向。

一是写入汇总指标里的预算字段（`RunMetrics.budget`），最终出现在 `run_summary` 事件里，让外部能看到这次调用的 Token 使用率：

```python
# harnessprd/backend/services/llm_metrics.py

def set_budget(self, check: Any) -> None:
    # check 可能是 BudgetCheckResult（有 to_budget_summary）或其他类型（有 to_context_usage）
    usage = (
        check.to_budget_summary()
        if hasattr(check, "to_budget_summary")
        else check.to_context_usage()
    )
    # 保留比率最高的那次检查结果，run_summary 里展示最严的一次
    if self.budget is None or usage["ratio"] >= self.budget.get("ratio", 0):
        self.budget = usage
```

二是存入异步上下文，对话结束时附在 `done` 事件的上下文使用率字段（`context_usage`）里，前端据此展示"当前上下文已使用 xx%"的提示：

```python
# harnessprd/backend/services/conversation_service.py

budget_check = get_last_budget_check()
if budget_check is not None:
    done_event["context_usage"] = budget_check.to_context_usage()
    # {"estimated_input_tokens": 6800, "budget_tokens": 12000, "ratio": 0.57, "level": "ok"}
```

这给用户一个明确的信号：澄清对话越来越长时，他们能看到上下文使用比率在上升，知道什么时候该结束澄清、开始生成。

两条去路服务的是两种场景，分工清晰：

| 场景 | 数据流向 | 前端展示 |
|------|---------|---------|
| 澄清对话（`chat_start`/`chat_continue`） | `context_usage` → `done` 事件 | 对话界面的上下文使用比率提示 |
| 文档生成（各 generate/review 步骤） | `budget` → `run_summary` 事件 | Job 结束后的 Token 消耗统计 |

对话类的 `context_usage` 是实时反馈，面向用户决策（"对话够了吗？该进入生成了吗？"）；生成类的 `budget` 是事后报告，面向成本感知（"这次生成花了多少输入 Token？哪一步是大头？"）。

![Token 预算检查与结果流向](https://pic.niumianoffer.com/images/fs/04-02-token-budget-flow.png)
