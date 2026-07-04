# 规范注入：Skill 与任务 Prompt 模板

让模型按照团队规范生成文档，最直接的做法是把规范写进 prompt。但这个方案有一个问题：规范多了之后，prompt 会越来越长，而且规范是散落在各处的静态文件，没有统一的管理方式。今天写死在 Python 里，明天要更新规范，还得改代码。

harnessprd v2 引入了 Skill 知识层，解决的就是这件事：团队规范存放在版本化的文件目录里，通过注册表声明哪些文档用哪套规范，生成时由统一的 loader 加载并注入 prompt，生成代码不需要知道规范文件在哪。

目录结构如下。每个 Skill 是一个子目录，`skill.yaml` 是清单，声明包含哪些规范文件及各自 role。

```
skills/
├── prd-generator/           # PRD 生成规范（绑 prd、optimize-prd）
│   ├── skill.yaml           # 清单：id、版本、artifacts 及 role
│   ├── instructions.md      # role: instructions — 任务生成说明
│   └── references/
│       ├── writing-rules.md       # role: reference — 写作规则
│       ├── prd-template.md        # role: template — PRD 章节模板
│       ├── field-schema.json      # role: schema — 结构化摘要字段契约（sync 回填用）
│       └── examples/                # 本地示例，未写入 skill.yaml，不参与自动注入
│           ├── friend-circle-copywriter.input.json
│           └── friend-circle-copywriter.output.md
├── api-docs-generator/      # 接口文档生成规范（绑 api-docs、optimize-api-docs）
│   ├── skill.yaml
│   ├── instructions.md      # role: instructions
│   └── references/
│       ├── team-api-guidelines.md   # role: reference — 团队 HTTP API 设计规范
│       ├── history-copywriting-api.md  # role: example — 历史接口文档示例
│       ├── history-task-api.md         # role: example — 历史接口文档示例
│       └── writing-rules.md           # role: reference — 写作规则
└── prompts-generator/       # 提示词套件生成规范（绑 prompts、optimize-prompts）
    ├── skill.yaml
    ├── instructions.md      # role: instructions
    └── references/
        ├── prompts-template.md  # role: template — 提示词套件结构模板
        └── writing-rules.md     # role: reference — 写作规则
```

loader 只读取 `skill.yaml` 里声明的 artifacts；目录里多出来的文件（如 prd-generator 下的 `examples/`）不会自动进 prompt。

## 两类静态知识：Skill 与 prompts.py

生成 prompt 里的静态知识来自两个地方，各自负责不同的事。

**第一类是 `prompts.py` 里的常量**，主要是各 Agent 的 System Prompt。这些常量定义了模型扮演的角色——是 PRD 写手、还是审查专家、还是 JSON 修复助手。它们硬编码在代码里，每次调用都作为 SystemMessage 传入：

```python
# harnessprd/backend/services/prompts.py

# 告诉模型它是谁、怎么思考
PRD_WRITER_SYSTEM_PROMPT = """你是一位资深产品经理和技术写作者，负责撰写 PRD。
你的目标：
1. 忠实依据用户需求与澄清对话输出 PRD
2. 保持结构清晰、工程可执行、适合 AI 辅助开发
3. 不编造业务事实，信息不足时写"待确认"
...
"""

# 告诉审查 Agent 它的唯一职责是找问题，不是重写
PRD_REVIEWER_SYSTEM_PROMPT = """你是一位严谨的 PRD 审查专家。
你的唯一任务是审查给定 PRD 是否忠实覆盖需求，并指出其中的问题。
...
"""
```

**第二类是 Skill 文件**，存放在 `skills/` 目录下的规范文档，包括写作规则、输出模板、历史示例等。这些文件不内嵌在代码里，而是通过 `skill.yaml` 清单声明，由 loader 在运行时读取。

两类知识的分工很清晰：`prompts.py` 定义角色和推理方式，告诉模型"你是谁、应该怎么思考"，通常不需要频繁改动；Skill 文件定义规范和格式约束，告诉模型"输出要符合哪些团队规范"，可以独立更新，改完就生效，不需要动代码。

## Skill 是什么

一个 Skill 就是 `skills/` 目录下的一个子目录，里面有一个 `skill.yaml` 清单文件，以及若干规范文件。`skill.yaml` 声明这个 Skill 的 id、版本、包含哪些文件、每个文件扮演什么角色：

```yaml
# harnessprd/skills/prd-generator/skill.yaml

id: prd-generator
version: "1.0.0"
label: PRD 生成规范
description: 结构化需求摘要转 PRD 的模板、写作规则与字段契约
applies_to:
  - prd
  - optimize-prd
artifacts:
  - path: instructions.md
    role: instructions      # 生成说明，告诉模型怎么做这个任务
  - path: references/writing-rules.md
    role: reference         # 写作规范
  - path: references/prd-template.md
    role: template          # 输出模板
  - path: references/field-schema.json
    role: schema            # 字段定义，给模型参考
enabled: true
priority: 10
```

role 字段决定文件内容在 prompt 里的语义：`instructions` 是任务说明，`reference` 是规范约束，`template` 是输出结构，`example` 是历史示例。不同 role 的内容会被组织成不同的 prompt 段落。

接口文档生成规范的 Skill 结构类似，但多了两个历史示例文件：

```yaml
# harnessprd/skills/api-docs-generator/skill.yaml

artifacts:
  - path: instructions.md
    role: instructions
  - path: references/team-api-guidelines.md
    role: reference         # 团队接口设计规范
  - path: references/history-copywriting-api.md
    role: example           # 历史接口文档示例 1
  - path: references/history-task-api.md
    role: example           # 历史接口文档示例 2
  - path: references/writing-rules.md
    role: reference
```

example 文件是可选的，缺失时只记录 warning，不报错，不阻断生成。

## 注册表：声明绑定关系

Skill 和文档类型的绑定关系在 `config/skills.yaml` 里统一声明：

```yaml
# harnessprd/config/skills.yaml

bindings:
  prd:
    skills:
      - prd-generator
  optimize-prd:
    skills:
      - prd-generator
  api-docs:
    skills:
      - api-docs-generator
  optimize-api-docs:
    skills:
      - api-docs-generator
  prompts:
    skills:
      - prompts-generator
  optimize-prompts:
    skills:
      - prompts-generator
```

一个 artifact 类型可以绑定多个 Skill，loader 会按 `priority` 字段排序后依次加载，并把内容合并。目前每种文档类型各绑了一个 Skill，但架构上支持扩展。

## Loader：统一加载管道

Loader 的职责是：给定一个 artifact 类型，从注册表查出绑定的 Skill，依次读取每个 Skill 里声明的文件，把内容组织成按 role 分组的字典。

```python
# harnessprd/backend/services/skill_loader.py

def load_skill_bundle(artifact: str) -> SkillBundle:
    # 从注册表查出绑定的 skill id 列表，已按 priority 排序
    skill_ids = resolve_skill_ids(artifact)  # 从注册表查绑定
    bundle = SkillBundle(artifact=artifact, skills=skill_ids)

    for skill_id in skill_ids:
        # 读取 skill.yaml 清单，lru_cache 保证同一进程只读一次
        manifest = load_skill_manifest(skill_id)  # 读 skill.yaml
        for item in manifest.get("artifacts") or []:
            # 逐个读取 artifacts 声明的文件，内容为空时仍插入占位记录
            content = read_artifact_file(skill_id, item["path"])
            bundle.artifacts.append(
                SkillArtifact(
                    skill_id=skill_id,
                    path=item["path"],
                    role=item.get("role", "reference"),
                    content=content,
                )
            )
    return bundle


def compose_prompt_sections(bundle: SkillBundle) -> dict[str, str]:
    # 按 role 顺序分组，同 role 的多个文件内容用空行拼接
    role_order = ["instructions", "template", "reference", "schema", "example"]
    grouped: dict[str, list[str]] = {role: [] for role in role_order}

    for artifact in bundle.artifacts:
        if not artifact.content:
            continue
        grouped[artifact.role].append(artifact.content)

    sections: dict[str, str] = {}
    for role in role_order:
        parts = grouped.get(role) or []
        if parts:
            # 返回 {"instructions": "...", "reference": "...", "template": "..."} 供调用方按需组装
            sections[role] = "\n\n".join(parts)
    return sections
```

`compose_prompt_sections()` 返回的是一个 `{"instructions": "...", "reference": "...", "template": "..."}` 这样的字典，调用方拿到它，可以决定把哪些 section 拼进 prompt、以什么格式组织。

manifest 和注册表的加载都使用了 `lru_cache`，同一进程内同一 Skill 只从磁盘读一次，后续调用直接走缓存。

![Skill 知识层从注册表加载到 Prompt 注入](https://pic.niumianoffer.com/images/fs/03-02-skill-loader-injection.png)

## 注入到 Prompt：三种产物的不同拼法

三种产物的 prompt 拼法不完全一样，差异来自它们对上下文的不同需求。

**PRD 生成**的角色定义是一段内联的 SystemMessage，Skill 规范通过 `_build_prd_from_summary_prompt()` 并入同一条 HumanMessage，澄清对话如果有则单独作为一条 HumanMessage 先传入：

```python
# harnessprd/backend/services/document_service.py

# PRD 起草：内联 SystemMessage + Skill 规范内嵌在 prompt 构建函数里
lc_messages = [
    SystemMessage(
        content=(
            "你是一位资深产品经理和技术写作者。"
            "请把结构化需求摘要整理成简洁、结构化、工程可执行的 PRD。"
            "如果存在补充对话，请优先采用对话中已澄清的内容。"
        )
    )
]
if clarification_context:
    lc_messages.append(HumanMessage(content=f"澄清对话：\n\n{clarification_context}"))
lc_messages.append(HumanMessage(content=_build_prd_from_summary_prompt(requirements_summary)))
```

**接口文档生成**没有独立的 SystemMessage 定义角色，消息列表直接用对话历史初始化，Skill 规范作为独立段落追加在 PRD 内容之后。这里的角色感靠对话历史本身传递，不需要额外声明：

```python
# harnessprd/backend/services/document_service.py

# 接口文档：无 role SystemMessage，以对话历史为基础
lc_messages = _build_lc_messages(conversation_messages)
sections = compose_prompt_sections(load_skill_bundle("api-docs"))
skill_section = _build_skill_section(sections, title="团队接口规范与参考示例")
conversation_text = _format_conversation_context(conversation_messages)
conversation_section = (
    f"\n\n澄清对话摘要：\n\n{conversation_text}\n\n" if conversation_text else ""
)
# PRD + 澄清摘要 + Skill 规范 + 生成指令合并为最后一条 HumanMessage
lc_messages.append(HumanMessage(
    content=(
        f"以下是已确认的产品需求文档（PRD）：\n\n{prd_content}"
        f"{conversation_section}"
        f"{skill_section}"
        f"{API_DOCS_GENERATION_PROMPT}"
    )
))
```

**提示词套件生成**则把所有东西压进两条消息：SystemMessage 写角色，一条 HumanMessage 装下 PRD、接口文档、Skill 规范和生成指令。上下文量最大，但因为没有流式草稿需要维护，一次性传入就够了：

```python
# harnessprd/backend/services/document_service.py

# 提示词套件：role 内联，Skill 规范和上下文合并为单条 HumanMessage
sections = compose_prompt_sections(load_skill_bundle("prompts"))
skill_section = _build_skill_section(sections, title="提示词套件生成规范")
lc_messages = [
    # 角色定义写在代码里，不走 Skill 文件
    SystemMessage(content="你是一位 AI 辅助开发专家，专门为 Claude Code 等 AI 编程工具设计高质量的系统提示词。"),
    # PRD、接口文档、Skill 规范全部合并为一条消息
    HumanMessage(content=f"{context}\n\n{skill_section}"),
]
```

`_build_skill_section()` 在三种产物里都承担同样的组装工作——把各 role 的内容整理成带标题的段落：

```python
# harnessprd/backend/services/document_service.py

def _build_skill_section(sections: Dict[str, str], title: str) -> str:
    parts = []
    # 为每个 role 定义人类可读的中文标题
    role_labels = {
        "instructions": "生成说明",
        "reference": "规范与写作要点",
        "template": "输出模板",
        "example": "参考示例",
    }
    for role in ("instructions", "reference", "template", "example"):
        content = sections.get(role)
        if content:
            # 每个 role 的内容作为独立段落，带三级标题
            parts.append(f"### {role_labels.get(role, role)}\n\n{content}")
    if not parts:
        return ""
    # 整体包裹在二级标题下，便于模型识别这是规范区域
    return f"\n\n## {title}\n\n" + "\n\n".join(parts) + "\n\n"
```

Skill 内容以段落的形式嵌入 prompt，但 prompt 里明确要求"规范内化为设计结果，不堆砌原文"，避免模型直接把规范文本复制进输出。

![三种产物的 Prompt 拼装差异](https://pic.niumianoffer.com/images/fs/03-02-prompt-assembly-diff.png)

## 注入过程可观测

每次 Job 完成后，loader 还会生成一份 `injected_skills` 元数据，记录这次生成用了哪些 Skill 和哪些文件：

```python
# harnessprd/backend/services/skill_loader.py

def bundle_to_injected_meta(bundle: SkillBundle) -> list[dict[str, Any]]:
    # 按 skill_id 分组，每个 skill 对应一个条目
    by_skill: dict[str, dict[str, Any]] = {}
    for artifact in bundle.artifacts:
        # 跳过内容为空的文件（如缺失的 example），不纳入元数据
        if not artifact.content:
            continue
        entry = by_skill.setdefault(
            artifact.skill_id,
            {"skill_id": artifact.skill_id, "version": "", "artifacts": []},
        )
        # 记录实际加载了哪些文件路径
        entry["artifacts"].append(artifact.path)
    # 读取各 Skill 的版本号并写入，便于追溯当时用的是哪一版规范
    for skill_id, entry in by_skill.items():
        manifest = load_skill_manifest(skill_id)
        entry["version"] = manifest.get("version", "")
    return list(by_skill.values())
```

这份元数据写入 `run_summary.injected_skills`，格式大致如下：

```json
[
  {
    "skill_id": "api-docs-generator",
    "version": "1.0.0",
    "artifacts": [
      "instructions.md",
      "references/team-api-guidelines.md",
      "references/writing-rules.md"
    ]
  }
]
```

如果某次接口文档风格突然变了，排查时可以先查 `injected_skills`，确认用的是哪个版本的 Skill，再决定是规范文件需要调整还是生成 prompt 需要调整。这让规范注入从一个黑盒操作变成了可追踪的过程。

## 这套设计解决了什么

v1 时期，PRD 生成规范是代码里硬编码的路径，接口文档规范走的是 RAG 确认流程，提示词套件规范写在生成代码里，三种做法互不统一。v2 把**规范类知识**统一为 Skill + 注册表 + Loader 这一条路，同时把**角色定义类知识**继续维护在 `prompts.py` 里，各司其职。

好处是直接的：新增一种文档规范，在 `skills/` 下加目录、改 `config/skills.yaml` 就够了，不需要动生成代码；更新规范只改文件内容，顺手更新版本号；出了问题查 `run_summary.injected_skills`，就能知道那次生成用的是哪一版规范，而不是凭记忆猜。

用户侧感知不到这些。他们点击生成，规范在后台静默注入，文档出来就带着团队风格。
