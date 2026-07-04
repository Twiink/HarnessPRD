# Token 预算与上下文估算提示词

点击此处可复制本篇提示词

Token 预算建立在 01 的观测包装层之上：**在调用模型前估算 prompt 的 input token 数，并与有效上限比较**。01 记录实际用量；本篇负责发送前检查与拦截。

有效 budget（可用 input 上限）= `min(业务策略 cap, 模型物理顶)`，取两层约束中更严格者。

## 使用场景

这份提示词用于在 harnessprd 项目 `backend/` 增加 **发送前 Token 估算**、**模型注册表** 和 **双层 budget 检查**。

**前置条件**：01 观测链路已完成（`get_tracked_llm`、`RunMetricsCollector`、SSE error 带 `request_id`）。

**为什么要做：** 每次调模型都是**独立的一次 API 请求**（澄清每一轮、PRD 的写/审/改各算一次），不是「全流程共享一个窗口配额」。每次送进去的 messages 由多块拼成：system prompt、结构化摘要、澄清历史、PRD 正文、Skill 规范片段、固定模板等。太长时不做检查，会直接撞模型 API 报错，用户只看到「生成失败」却不知道是聊太长了。

**改造后的调用顺序：**

```
messages（待发 prompt）
  → resolve_effective_budget(step, model)   # 算有效上限 = min(业务 cap, 模型物理顶)
  → estimate_tokens(messages, step, model)  # 估算 input token 数
  → check_budget(estimate, step)            # 与上限比较，得出 ok / warn / exceed
  → [reject 且 exceed] 返回 TOKEN_BUDGET_EXCEEDED，不调用 LLM
  → [否则] tracked_llm 调用（01 的观测逻辑）
  → run_summary / done 回传 context_usage（供前端展示上下文占用告警）
```

### 一、功能目标

- 新增 `config/models.yaml` + `services/model_registry.py`：维护各模型的**物理顶**（窗口大小、最大输出等；先配 DeepSeek + default）
- 新增/改造 `services/token_estimator.py`：tiktoken 估算 + 字符 fallback；`resolve_effective_budget(step, model)`
- **`max_tokens` 与 budget 联动**：`resolve_max_output(model)` 取自注册表，同时驱动 `get_llm()` 与 budget 物理顶；禁止写死、不用 `.env` / step 分档
- `core/config.py` 保留**业务策略 cap**（`.env` 里配）
- 在 `get_tracked_llm` **每次** `ainvoke` / `astream` **调用前**执行 budget 检查，传入当前 `model` 名
- `start-stream` / `continue-stream` 的 `done` 均带 `context_usage`（上下文占用情况）
- `run_summary` 和日志增加 `budget` 字段（可选含 `budget_source`：生效的是业务顶还是物理顶）
- `requirements.txt` 增加 `tiktoken`，更新 `.env.example`

### 二、代码结构

```
backend/
  config/
    models.yaml              # 模型物理参数（人工维护，不运行时拉 API）
  services/
    model_registry.py        # 读 yaml；resolve 模型；算 hardware_input_cap、resolve_max_output
    token_estimator.py       # estimate_tokens、resolve_effective_budget、check_budget
    llm_factory.py           # get_llm 用 resolve_max_output；调用前 check_budget
  core/
    config.py                # 业务策略 cap、warn/reject 模式
  api/
    conversation.py          # BudgetExceededError → SSE error / HTTP 422
```

依赖已存在的 `services/llm_metrics.py`（`RunMetricsCollector`、`get_tracked_llm`）。

### 三、双层 budget（核心概念）

#### 物理顶（模型注册表）

先给模型留出输出空间，剩下的才是 input 上限：

```text
hardware_input_cap = model.context_window
                     - resolve_max_output(model)
                     - SAFETY_MARGIN（可选，默认 0）
```

#### 业务顶（`.env` 策略 cap）

通常**小于**模型物理窗口。例如澄清对话 cap 设为 6 万，而 DeepSeek 窗口为 100 万——目的是在接近业务上限时提前告警，而非等到 API 报错。

| step 类型 | `.env` 键 | 说明 |
|-----------|-----------|--------------|
| 澄清 | `CHAT_HISTORY_BUDGET` | 对话历史别无限涨，接近上限时 warn |
| 单次生成 | `SINGLE_CALL_INPUT_BUDGET` | 写 PRD / 接口文档 / 提示词时，单次 prompt 别太长 |
| 辅助步骤 | `CONTEXT_BUDGET_TOKENS` | 摘要同步、JSON 修复等轻量调用 |

#### 有效 budget（每次调用实际用的上限）

```text
policy_cap = 上表按 step 取值
effective_input_budget = max(min(policy_cap, hardware_input_cap), 1)
ratio = estimated_input_tokens / effective_input_budget   # 用了上限的百分之几
```

当 `policy_cap < hardware_input_cap` 时，回传 `budget_tokens = policy_cap`，`budget_source = policy`（业务顶生效）；反之则为 `hardware`。澄清场景通常 **policy 生效**。

#### 常见误解（验收与调参时对照）

- 模型标 1M **不是** PRD 全流程共享 1M 配额；澄清第 6 轮约 1 万 token，对 1M 物理顶几乎不会 warn。
- 不能「按轮预分配 token」；澄清轮数不确定，只应在**每次 continue 发送前**现算当前 messages 总长。
- ratio 的分母是 **input 有效上限**，**不再**从业务顶减 output；output 只在算物理顶时从窗口扣除。

### 四、模型注册表

#### `config/models.yaml`（示例，数据来自官方文档，人工维护）

```yaml
models:
  deepseek-v4-flash:
    provider: openai_compatible
    context_window: 1000000
    max_output_tokens: 384000
    encoding: cl100k_base

  deepseek-chat:              # 别名，共用同一套参数
    alias_of: deepseek-v4-flash

  default:                    # 未知模型名时的保守兜底
    context_window: 32768
    max_output_tokens: 4096
    encoding: cl100k_base
```

#### `model_registry.py` 职责

- 启动时加载 yaml
- `resolve(model_name)` → `ModelCaps`（支持 `alias_of` 别名）
- 未知模型 → 走 `default` + `logger.warning`
- **不**通过 `/v1/models` 自动拉 context_window（多数 API 不提供可靠字段）

#### `resolve_max_output(model)` — 输出上限仅来自注册表（必做）

`llm_factory` **禁止**写死 `max_tokens`。输出上限**只**查注册表，**不**设 `.env` 项、**不**按 step 分档：

```text
max_output = model.max_output_tokens   # 如 DeepSeek 384000
```

budget 算物理顶时**必须用同一个** `max_output`：

```text
hardware_input_cap = model.context_window - max_output - SAFETY_MARGIN
```

| 字段 | 含义 |
|------|------|
| `resolve_max_output(model)` | 传给 `ChatOpenAI(max_tokens=...)` 的值 |
| `TokenEstimate.max_output_tokens` | 日志对照，与 API 一致 |
| `.env` | **无**输出相关配置；换模型/调输出顶 → 改 `models.yaml` |

**为何输出顶不放 `.env`：** 本篇主线是 **input 业务 cap**（澄清 6 万等）。业务 cap 远小于模型窗口时，output 预留大小对 ratio 几乎无影响。输出顶放注册表可避免 PRD 被过小的全局 cap（如 4096）截断，也减少配置面。

`get_tracked_llm(step)` → `get_llm(model)`，`TrackedChatModel` 构造时保存 `_max_output`，budget 检查与 API 调用共用。

### 五、数据结构

#### TokenEstimate（估算结果）

```python
@dataclass
class TokenEstimate:
    estimated_input_tokens: int   # 估算的 input 长度
    budget_tokens: int            # 有效 input 上限 effective_input_budget
    max_output_tokens: int        # 本次允许的最大输出
    ratio: float                  # 估算 input / 上限
    estimator: str                # tiktoken | char_heuristic（用的哪种估算法）
```

#### BudgetCheckResult（检查结果）

```python
@dataclass
class BudgetCheckResult:
    allowed: bool                 # 是否允许继续调模型
    mode: str                     # warn | reject（当前模式）
    level: str                    # ok | warn | exceed
    estimated_input_tokens: int
    budget_tokens: int            # 有效上限
    ratio: float
    message: str                  # 给用户/日志的说明
    step: str
    model: str
    policy_cap: int               # 可选，业务顶
    hardware_cap: int             # 可选，物理顶
    budget_source: str            # policy | hardware（哪层更严）
```

#### context_usage（SSE done 回传 — 前端用来展示 amber 提示）

前端**必用**字段保持如下，不要改语义：

```json
{
  "estimated_input_tokens": 42000,
  "budget_tokens": 60000,
  "ratio": 0.70,
  "level": "warn"
}
```

**可选扩展**（仅日志/调参，前端不展示）：

```json
{
  "budget_source": "policy",
  "model": "deepseek-v4-flash",
  "policy_cap": 60000,
  "hardware_cap": 995904
}
```

### 六、Token 估算策略

- **优先 tiktoken** 数 Token；encoding 优先取注册表 `model.encoding`，fallback `TOKEN_ENCODING`
- OpenAI 兼容（含 DeepSeek）：默认 `cl100k_base`
- **Fallback：** `len(text) * 0.6`（char_heuristic，偏保守，估不准时宁可算大一点）

### 七、level 划分与 warn / reject 模式

| ratio（占用比例） | level | warn 模式 | reject 模式 |
|-------------------|-------|-----------|-------------|
| < 0.6 | ok | 正常调用 | 正常调用 |
| 0.6 ~ 0.95 | warn | 调用 + 日志 warn | 调用 + 日志 warn |
| > 0.95 | exceed | 调用 + 日志 warn | **拒绝调用** |

阈值默认 0.6 / 0.95，后续可改为 `.env` 可配置。默认 `TOKEN_BUDGET_MODE=warn`（只告警不拦）。

### 八、各 step 用哪条业务 cap

| step | 业务 cap 来源 |
|------|---------------|
| chat_start / chat_continue | `CHAT_HISTORY_BUDGET` |
| prd_writer / prd_review / prd_rewrite | `SINGLE_CALL_INPUT_BUDGET` |
| api_docs_generate / prompts_generate / document_optimize | `SINGLE_CALL_INPUT_BUDGET` |
| summary_sync / json_repair / json_regenerate | `CONTEXT_BUDGET_TOKENS` |

再与 `resolve(model)` 的 physical cap 取 min。上表为固定规则，不要混用。

### 九、拒绝与 warn 时的 API 行为

**SSE + reject 模式 + exceed：** 在调用 LLM **之前** yield error + `[DONE]`，**不会**产生 `llm_step`（因为根本没调模型）。

**warn 模式：** 正常调用 LLM，额外打 `token_budget_warn` 日志；前端可通过 `context_usage.level` 展示 amber 条。

**JSON 接口（sync-summary）：** 超预算时 HTTP 422，body 带说明。

### 十、context_usage 回传

以下澄清流式路由的 `done` **均需**带 `context_usage`（ok / warn / exceed 都返回）：

- `start-stream`（澄清首轮）
- `continue-stream`（澄清继续）

供前端展示「已讨论较多内容」类提示；**不要**把 ratio 百分比直接暴露给普通用户。前端在 `level` 为 `warn` 或 `exceed` 时展示 ClarificationWarnBanner。

### 十一、接入位置

#### budget 检查（`TrackedChatModel` 内，调模型前）

```python
model = self._model_name
max_output = resolve_max_output(model)
estimate = estimate_tokens(messages, step=self._step, model=model)
check = check_budget(estimate, step=self._step)
...
```

#### LLM 创建（`get_llm` / `get_tracked_llm`）

```python
def get_llm(temperature: float = 0.7):
    model = settings.default_llm_model
    max_output = resolve_max_output(model)
    return ChatOpenAI(..., model=model, max_tokens=max_output, ...)
```

禁止在 `get_llm` 内写死 `4096`；禁止从 `.env` 读输出 cap。

```python
if not check.allowed:
    raise BudgetExceededError(check)
RunMetricsCollector.current().set_budget(check)
# 原有 tracked 调用逻辑...
```

`check_budget` / `resolve_effective_budget` 放在 `token_estimator.py`；`resolve_max_output` 在 `model_registry.py`。

### 十二、配置项

**模型注册表：** `config/models.yaml`（见第四节）

**`.env` 业务策略（`.env.example`）：**

```env
# 业务策略 cap（产品调参；与模型窗口取 min 后生效）
CONTEXT_BUDGET_TOKENS=120000      # 摘要同步、JSON 修复等辅助步骤
CHAT_HISTORY_BUDGET=60000         # 澄清对话历史
SINGLE_CALL_INPUT_BUDGET=100000   # PRD / 接口文档 / 提示词单次生成
TOKEN_BUDGET_MODE=warn            # warn=只告警；reject=超预算拒绝调用
TOKEN_ESTIMATOR=tiktoken
DEFAULT_LLM_MODEL=deepseek-v4-flash
```

| 配置 | 含义 |
|------|------|
| `CHAT_HISTORY_BUDGET` | 澄清 **input 业务顶** |
| `SINGLE_CALL_INPUT_BUDGET` | 单次文档生成 **input 业务顶** |
| `CONTEXT_BUDGET_TOKENS` | 辅助步骤 **input 业务顶** |
| `TOKEN_BUDGET_MODE` | `warn` / `reject` |

**输出上限不在 `.env`**：见 `config/models.yaml` 的 `max_output_tokens`。

`requirements.txt` 增加 `tiktoken>=0.7.0`、`pyyaml`（若尚未引入）。

### 十三、验收标准

- `models.yaml` 含 `deepseek-v4-flash` 与 `default`；`deepseek-chat` 别名可解析
- **`get_llm` 不再写死 max_tokens**；`max_tokens` 与 budget 日志中的 `max_output_tokens` 均来自 `resolve_max_output(model)`
- 修改 `models.yaml` 中某模型的 `max_output_tokens` 后，API 输出顶与物理 input 顶同步变化
- 未知模型走 `default` 并打 warn 日志
- 澄清：`CHAT_HISTORY_BUDGET=60000`、DeepSeek 1M 时，`budget_tokens` 应为 **60000**（policy 生效），不是 1M
- 长澄清后 `done.context_usage.level` 可为 warn；**不是**「第六轮 1 万 token 就 warn」（除非 cap 设极小）
- `start-stream` 与 `continue-stream` 的 `done` 均含 `context_usage`
- `TOKEN_BUDGET_MODE=reject` + 超长 messages → `TOKEN_BUDGET_EXCEEDED`，无 `llm_step`
- `context_usage.level` 与 ratio 划分一致
- `run_summary.budget` 含有效 budget 信息；可选 `budget_source`
- PRD 等多步流程**每一步**调用前均做 budget 检查
- 正常短对话行为与改前一致
