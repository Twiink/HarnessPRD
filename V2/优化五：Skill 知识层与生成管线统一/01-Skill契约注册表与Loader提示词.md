# Skill 契约、注册表与 Loader 提示词

点击此处可复制本篇提示词

本篇在现有 `skills/prd-generator/` 目录上建立 Skill 基础设施：补齐 `skill.yaml` 元数据、全局注册表 `config/skills.yaml`、统一加载器 `skill_loader`。PRD 生成改经 loader 读取规范文件，**对外行为与改造前一致**。本篇不删除 RAG、不新建 `api-docs-generator`，后者见 02 篇。

## 使用场景

这份提示词用于在 harnessprd 项目 `backend/` 与 `skills/`、`config/` 建立 Skill 加载与绑定机制。

**前置条件**：`skills/prd-generator/` 已存在；`document_service._load_skill_artifact` 已在 PRD / 摘要回填路径使用。

**现状问题：** Skill 文件路径硬编码在 `document_service` 中（固定 `skills/prd-generator/`），无 artifact 与 skill 的声明式绑定；新增 skill 需复制 open 逻辑，无法通过配置扩展。

**本篇交付范围：**

```
skills/prd-generator/skill.yaml
  + config/skills.yaml（artifact → skill 绑定）
  → skill_loader（扫描、校验、读取、拼接）
  → document_service PRD 路径改调 loader
```

**本次不做：**

- 新建 `api-docs-generator`、`prompts-generator`
- 删除 `rag_service`、RAG API、前端 RAG 门控
- 改造接口文档 / 提示词生成 prompt 组装
- `run_summary.injected_skills`（RAG 下线篇一并做）
- `team.yaml`、上传 UI、Skill 热加载

### 一、功能目标

- 定义 Skill 目录契约：`skill.yaml` + `instructions.md` + `references/`
- 为 `skills/prd-generator/` 补充 `skill.yaml`
- 新增 `config/skills.yaml`：声明 artifact 与 skill 的绑定关系
- 新增 `services/skill_loader.py`：扫描、校验、读取、拼接 skill 内容
- `document_service` 中 PRD 相关逻辑改调 loader，删除 `_load_skill_artifact` 硬编码
- 启动或首次加载时校验：注册表引用的 skill 目录存在、`skill.yaml` 合法
- 现有 PRD 生成、摘要回填、JSON schema 读取 **结果不变**（回归用）

### 二、要解决的问题

当前读 skill 的方式：

```python
# document_service.py — 写死 prd-generator
os.path.join(..., "skills", "prd-generator", *path_parts)
```

存在以下问题：

- 仅 PRD 走 skill，路径绑死在代码中
- 缺少「该 skill 适用于哪些 artifact / 任务」的声明
- 新增 skill 只能复制粘贴一套文件读取逻辑

改造后，业务代码通过 loader 查询：**给定 `artifact`，需要注入哪些 skill 文件？**

### 三、代码结构

```
harnessprd/
  config/
    skills.yaml                    # 新建：artifact → skill 绑定
  skills/
    prd-generator/
      skill.yaml                   # 新建：元数据
      instructions.md              # 保留
      references/                  # 保留
  backend/
    services/
      skill_loader.py              # 新建
      document_service.py          # 改造：PRD 路径用 loader
```

**分层原则：**

| 层 | 职责 |
|----|------|
| `skills/*/skill.yaml` | 单个 skill 的自描述 |
| `config/skills.yaml` | 全局：哪种产物用哪些 skill |
| `skill_loader` | 读文件、校验、按角色拼接 |
| `document_service` | 业务 prompt 组装，调用 loader |

### 四、Skill 目录契约

每个 skill 目录结构：

```
skills/{skill_id}/
├── skill.yaml          # 必填
├── instructions.md     # 推荐
└── references/         # 可选，任意 md/json
    └── ...
```

#### `skill.yaml` 字段

```yaml
id: prd-generator
version: "1.0.0"
label: PRD 生成规范
description: 结构化需求摘要转 PRD 的模板、写作规则与字段契约
applies_to:
  - prd
  - optimize-prd
artifacts:
  - path: instructions.md
    role: instructions
  - path: references/writing-rules.md
    role: reference
  - path: references/prd-template.md
    role: template
  - path: references/field-schema.json
    role: schema
enabled: true
priority: 10
```

**字段说明：**

| 字段 | 含义 |
|------|------|
| `id` | 与目录名一致 |
| `version` | 语义化版本，供后续 pin |
| `applies_to` | 可用于哪些 artifact（与注册表交叉校验） |
| `artifacts` | 要注入的文件列表及角色 |
| `role` | `instructions` / `reference` / `template` / `schema` / `example` |
| `priority` | 多 skill 时排序，数字越小越靠前 |
| `enabled` | 默认 true；loader 跳过 false |

`role` 不强制改变拼接文案，但 loader 应按 role 分组，便于 `compose_prompt_sections()` 生成稳定格式。

#### 为 `prd-generator` 编写 `skill.yaml`

根据现有引用关系填写：

- `instructions.md` → instructions
- `references/writing-rules.md` → reference
- `references/prd-template.md` → template
- `references/field-schema.json` → schema
- `references/examples/*` → example（可选注入，默认 **不** 自动注入 examples，除非注册表显式需要）

### 五、`config/skills.yaml`

```yaml
bindings:
  prd:
    skills:
      - prd-generator
  optimize-prd:
    skills:
      - prd-generator
  api-docs:
    skills: []          # 本篇留空，RAG 下线篇填入 api-docs-generator
  optimize-api-docs:
    skills: []
  prompts:
    skills: []
  optimize-prompts:
    skills: []
```

规则：

- `bindings` 的 key 与 Job `artifact`、优化类型一致
- 值为 skill id 列表，按 `skill.yaml` 的 `priority` 二次排序
- 空列表合法：loader 返回空 bundle，调用方按无 skill 处理

### 六、`skill_loader.py` API

建议公开接口：

```python
@dataclass
class SkillArtifact:
    skill_id: str
    path: str
    role: str
    content: str

@dataclass
class SkillBundle:
    artifact: str
    skills: list[str]
    artifacts: list[SkillArtifact]

def get_skills_root() -> Path: ...

def load_skill_manifest(skill_id: str) -> dict: ...

def resolve_skill_ids(artifact: str) -> list[str]: ...

def load_skill_bundle(artifact: str) -> SkillBundle: ...

def read_artifact_file(skill_id: str, relative_path: str) -> str: ...

def compose_prompt_sections(bundle: SkillBundle) -> dict[str, str]:
    """
    返回按角色分组的文本，例如：
    {
      "instructions": "...",
      "template": "...",
      "reference": "...",
      "schema": "...",
    }
    缺失角色省略；文件读失败记 warning，不抛致命错（与现有 `_load_skill_artifact` 行为一致）。
    """
```

**路径解析：**

- skills 根目录：`{repo_root}/skills/`
- config：`{repo_root}/config/skills.yaml`
- 用 `pathlib`，不依赖 cwd

**校验（建议 `load_skill_bundle` 时执行）：**

- skill 目录存在
- `skill.yaml` 可解析，`id` 与目录名一致
- `artifacts[].path` 文件存在（example 类可选 warn）
- `enabled: false` 的 skill 跳过

**缓存：**

- 可对 manifest 和文件内容做进程内 `lru_cache`（开发期改文件需重启，本期可接受）

### 七、改造 `document_service.py`（仅 PRD 相关）

替换所有 `_load_skill_artifact(...)` 调用为 loader：

| 现调用点 | 改法 |
|----------|------|
| `_build_prd_from_summary_prompt` | `bundle = load_skill_bundle("prd")` → `compose_prompt_sections` |
| `_build_summary_sync_prompt` | 读 `schema` 角色或 `read_artifact_file("prd-generator", "references/field-schema.json")` |

**拼接顺序保持与现逻辑等价：**

1. 固定任务说明（中文条目 1～6）
2. 结构化摘要 JSON
3. writing_rules（reference）
4. instructions
5. prd-template（template）

删除 `_load_skill_artifact` 函数；`_load_prd_template()` 保留作 **fallback**（`skills` 模板缺失时读 `core/prd_template.md`）。

**本篇不改动：**

- `generate_api_docs_stream`（仍用 RAG）
- `generate_prompts_stream`
- `retrieve_api_docs_rag_hits`

### 八、错误与日志

- skill 文件缺失：logger.warning，该段为空，生成继续（与现有实现一致）
- `skills.yaml` 引用不存在的 skill_id：启动时或首次 `load_skill_bundle` 抛清晰异常（配置错误应尽早暴露）
- 不在本篇写 `injected_skills` 到 run_summary

### 九、验收标准（本篇）

1. `skills/prd-generator/skill.yaml` 存在且字段完整
2. `config/skills.yaml` 存在，`prd` / `optimize-prd` 绑定 `prd-generator`
3. `skill_loader.load_skill_bundle("prd")` 返回非空 artifacts，含 template 与 schema
4. 结构化主路径生成 PRD：**章节结构、表格、写作风格与改造前可比**（人工抽测 1 次）
5. 澄清后摘要回填 JSON：**schema 约束仍生效**
6. `pytest` 或最小脚本：loader 能加载 prd-generator；引用不存在 skill 时配置校验失败
7. **接口文档生成仍走 RAG**（确认本篇未误删）

```bash
# 后端启动无报错
cd backend && uvicorn main:app --reload
```

### 十、实现顺序建议

1. 写 `skill.yaml` + `config/skills.yaml`
2. 实现 `skill_loader` + 单元测试
3. 改 `document_service` PRD 路径
4. 跑一轮 PRD 生成回归
5. 再进入 RAG 下线篇
