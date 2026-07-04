# 观测链路：分 step 追踪与生成汇总

一次 PRD 生成背后，可能触发 2 到 4 次 LLM 调用：Writer 写草稿、Reviewer 审查、Rewriter 修订、以及可能出现的 JSON 修复或重生成。如果没有观测，出了问题只能靠猜——是哪一步慢了？哪一步报错了？Token 消耗集中在哪里？

harnessprd v2 的观测链路围绕两个层级设计：**单次 LLM 调用级别的 step 追踪**，以及**跨整次 Job 的 run summary**。

## Step 追踪：每次调用都有名字

每次 LLM 调用都对应一个步骤标签，这个标签贯穿日志、指标和前端展示（枚举类 `LlmStep`）：

```python
# harnessprd/backend/services/llm_metrics.py

class LlmStep(str, Enum):
    # 澄清对话：区分首轮和后续轮
    CHAT_START = "chat_start"
    CHAT_CONTINUE = "chat_continue"
    # PRD 三阶段：起草 → 审查 → 修订
    PRD_WRITER = "prd_writer"
    PRD_REVIEW = "prd_review"
    PRD_REWRITE = "prd_rewrite"
    # 接口文档与提示词生成
    API_DOCS_GENERATE = "api_docs_generate"
    API_DOCS_REVIEW = "api_docs_review"
    PROMPTS_GENERATE = "prompts_generate"
    PROMPTS_REVIEW = "prompts_review"
    DOCUMENT_OPTIMIZE = "document_optimize"
    # 辅助步骤：修复错误 JSON、同步摘要等
    JSON_REPAIR = "json_repair"
    JSON_REGENERATE = "json_regenerate"
    SUMMARY_SYNC = "summary_sync"
```

调用方用 `get_tracked_llm(LlmStep.PRD_WRITER.value, temperature=0.3)` 取 LLM 实例，而不是直接构造模型对象。返回的是带追踪功能的模型封装，它在调用前后自动记录耗时和 Token 用量：

```python
# harnessprd/backend/services/llm_factory.py

class TrackedChatModel:
    async def ainvoke(self, messages, **kwargs):
        # 发送前先做 Token 预算检查，超出时提前拦截（下一篇详述）
        self._run_budget_check(messages)
        started = time.perf_counter()
        try:
            response = await self._llm.ainvoke(messages, **kwargs)
            duration_ms = int((time.perf_counter() - started) * 1000)
            # 从响应元数据里读取实际 Token 用量
            usage = getattr(response, "usage_metadata", None)
            self._record_step(usage, duration_ms, "ok")
            return response
        except Exception as e:
            duration_ms = int((time.perf_counter() - started) * 1000)
            # 出错时也记录指标，status 标记为 "error"
            self._record_step({}, duration_ms, "error", str(e)[:200])
            raise
```

流式调用（`astream()`）的记录逻辑类似，差别在于流式响应的 Token 用量不在首个 chunk 里，而是在最后一个 chunk 的 `usage_metadata` 字段：

```python
# harnessprd/backend/services/llm_factory.py

async def astream(self, messages, **kwargs):
    self._run_budget_check(messages)
    started = time.perf_counter()
    last_chunk = None
    try:
        async for chunk in self._llm.astream(messages, **kwargs):
            # 边流边把 chunk 吐给上层，同时记录最后一个 chunk 备用
            last_chunk = chunk
            yield chunk
        duration_ms = int((time.perf_counter() - started) * 1000)
        # 流式调用的 usage 信息在最后一个 chunk 里，流完才能读到
        usage = getattr(last_chunk, "usage_metadata", None) if last_chunk else None
        self._record_step(usage, duration_ms, "ok")
    except Exception as e:
        duration_ms = int((time.perf_counter() - started) * 1000)
        # 出错时同样记录 error 状态的 step 指标
        self._record_step({}, duration_ms, "error", str(e)[:200])
        raise
```

这意味着 Writer 的内容还在往前端推的时候，这一步的指标还没写完——只有流结束才记录完毕。

每次调用成功或失败都会产生一条单步指标记录，包含步骤名称、模型名称、输入/输出 Token 数、耗时和状态：

```python
# harnessprd/backend/services/llm_metrics.py

@dataclass
class StepMetrics:
    step: str          # "prd_writer"
    model: str         # "claude-3-5-sonnet-20241022"
    input_tokens: int
    output_tokens: int
    duration_ms: int
    status: str        # "ok" | "error"
    error: str = ""
```

这条记录立刻以 JSON 写入日志（`event: llm_step`），可以被日志系统实时采集，也可以在终端直接看到每一步的耗时和 Token。

![LLM Step 追踪链路](https://pic.niumianoffer.com/images/fs/04-01-llm-step-tracing.png)

## Run 级别汇总：跨步骤聚合

单次步骤的记录解决了"某一步出了什么问题"，但还需要回答"这整次生成花了多少"。汇总指标对象 `RunMetrics` 负责在 Job 的生命周期里聚合所有步骤：

```python
# harnessprd/backend/services/llm_metrics.py

@dataclass
class RunMetrics:
    run_type: str               # "generate_prd_from_summary_stream"
    request_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    llm_call_count: int = 0
    steps: List[StepMetrics] = field(default_factory=list)
    # Rewriter 是否实际被触发（Reviewer 发现问题时为 True）
    revision_applied: Optional[bool] = None
    # 最高 Token 使用率那次检查的摘要，写入 run_summary
    budget: Optional[Dict[str, Any]] = None
    injected_skills: Optional[List[Dict[str, Any]]] = None

    def add_step(self, step: StepMetrics) -> None:
        self.steps.append(step)
        self.llm_call_count += 1
        self.total_input_tokens += step.input_tokens
        self.total_output_tokens += step.output_tokens
```

指标采集器通过异步上下文把当前 run 挂在后台，每步调用结束后会自动找到当前 run 并追加记录，不需要把采集器对象显式传来传去。Job 开始时创建采集器，Job 结束时调 `finish()` 汇总，整个 run 的指标就收集完了：

```python
# harnessprd/backend/services/llm_factory.py

def _record_step(self, usage, duration_ms, status, error=""):
    # 把 usage、耗时、状态组装成一条步骤指标 StepMetrics
    record = build_step_metrics(self._step, self._model_name, usage, duration_ms, status, error)
    # 通过 ContextVar 找到当前 run，追加步骤记录
    run = RunMetricsCollector.current()
    if run is not None:
        run.add_step(record)
    # 同时写结构化日志，带上 request_id 方便串联同一次生成的所有调用
    log_llm_step({**record.to_dict(), "request_id": get_request_id()})
```

## run_summary 事件

Job 最后，汇总结果通过 SSE 推给前端，作为 `run_summary` 事件：

```python
# harnessprd/backend/services/job_runner.py

async def _finish_run_summary(job_id, run, revision_applied, artifact=None):
    # 尝试加载注入的规范包元数据，失败只记日志，不影响 run_summary 推送
    if artifact:
        try:
            bundle = load_skill_bundle(artifact)
            meta = bundle_to_injected_meta(bundle)
            if meta:
                run.set_injected_skills(meta)
        except Exception as exc:
            logger.warning("加载 injected_skills 失败 (%s): %s", artifact, exc)
    # 汇总所有步骤，计算总 Token 数、总耗时、LLM 调用次数
    summary = run.finish(revision_applied=revision_applied)
    event = {"type": "run_summary", **summary.to_dict()}
    # 推给前端，前端可展示本次调用的模型统计
    await publish(job_id, event)
    # 同时写服务端 JSON 日志，供问题排查使用
    log_run_summary(summary)
    # 把 run_summary 持久化写入当前版本的 metadata_json
    await _finalize_document_for_job(job_id, run_summary=summary.to_dict())
```

一条典型的 `run_summary` 事件长这样：

```json
{
  "type": "run_summary",
  "request_id": "req_abc123",
  "run_type": "generate_prd_from_summary_stream",
  "total_input_tokens": 12400,
  "total_output_tokens": 3200,
  "total_duration_ms": 18500,
  "llm_call_count": 3,
  "revision_applied": true,
  "steps": [
    {"step": "prd_writer",   "input_tokens": 8000,  "output_tokens": 2800, "duration_ms": 12000},
    {"step": "prd_review",   "input_tokens": 3200,  "output_tokens": 300,  "duration_ms": 4000},
    {"step": "prd_rewrite",  "input_tokens": 1200,  "output_tokens": 100,  "duration_ms": 2500}
  ],
  "budget": {"ratio": 0.62, "level": "ok", "budget_tokens": 14000},
  "injected_skills": [{"skill_id": "prd-generator", "version": "1.0.0", "artifacts": [...]}]
}
```

前端收到这条事件后，可以展示"本次共调用 3 次模型、总耗时 18.5 秒、应用了修订"等信息，也可以看到哪一步耗时最长。

`_finalize_document_for_job()` 同时把 run_summary 写进当前版本的 `metadata_json`，这样在版本历史页翻到某个历史版本时，不只能看到文档内容，还能看到那次生成花了多少 Token、Rewriter 有没有被触发。生成记录不是临时的流数据，它是版本元数据的一部分，可以随时回溯。

![Run Summary 的聚合、推送与持久化](https://pic.niumianoffer.com/images/fs/04-01-run-summary.png)

## 失败不丢观测

Job 执行失败时，观测链路不会断。`_finish_run_summary()` 被放在 `finally` 块里，无论 Job 成功还是报错，都会执行：

```python
# harnessprd/backend/services/job_runner.py

try:
    async for event in document_service.generate_prd_from_summary_stream(...):
        # 处理正常事件，累积草稿内容
        ...
except Exception as exc:
    # 记录错误，把草稿和失败状态写进版本元数据
    _sync_document_before_session(session_id, "prd", draft, failed=True, job_id=job_id)
    await publish(job_id, {"type": "error", "message": str(exc)})
finally:
    # 无论成功还是失败，始终汇总并推送 run_summary
    await _finish_run_summary(job_id, run, revision_applied, artifact="prd")
```

失败时，`RunMetrics` 已经积累了失败前所有步骤的指标。`_finish_run_summary()` 把这些数据推给前端并写进日志，版本元数据里也会带上 `"job_status": "failed"` 标记。

"Writer 写了 8000 Token 但 Reviewer 还没来得及跑就报错了"这类情况是可观测的：RunMetrics 里有一条 `prd_writer` 的 step 记录，但没有 `prd_review`，失败位置一目了然。

## 前端展示汇总，日志留明细

前端收到的 `run_summary` 是聚合后的汇总：总 Token 数、总耗时、调用了几次模型、有没有触发修订。用户在界面上看到的是这份汇总，不是每一步的明细。

逐步明细留在服务端日志里。每次 LLM 调用完成，`_record_step()` 立即调 `log_llm_step()` 写一条结构化日志，记录 step 名称、模型名、Token 数、耗时和状态；Job 结束时 `log_run_summary()` 再写一条聚合日志。两层日志串联在同一个 `request_id` 下。

```json
// 每次 LLM 调用后写入的 llm_step 日志
{
  "event": "llm_step",
  "request_id": "req_abc123",
  "step": "prd_writer",
  "model": "claude-sonnet-4-6",
  "input_tokens": 8000,
  "output_tokens": 2800,
  "duration_ms": 12000,
  "status": "ok"
}
```

排查某次生成为什么慢或为什么 Token 多时，先看 run_summary 定位哪次 Job 有问题，再用 `request_id` 在日志系统里查出这次 Job 的逐步明细。前端展示的是对话友好的摘要，日志留下的是排查友好的原始记录。

## 这条链路解决了什么

没有观测时，生成慢了不知道慢在哪里，Token 消耗多了不知道哪个步骤吃了大头，JSON 修复被触发了也不知道。有了分 step 追踪之后，这些问题都有了明确的数据支撑。

是否触发修订的字段 `revision_applied`、Token 使用率字段 `budget`、注入规范包字段 `injected_skills`，三者叠在一起，把一次生成过程说清楚了。
