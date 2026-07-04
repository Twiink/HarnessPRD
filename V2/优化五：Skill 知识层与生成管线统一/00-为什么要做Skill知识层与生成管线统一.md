# 00 - 为什么要做 Skill 知识层与生成管线统一

v2 已经能走完：澄清 → PRD → 接口文档 → 提示词套件。PRD 生成时，会把 `skills/prd-generator/` 里的模板和写作规则 **静默拼进发给模型的 prompt**，用户无感。

但「团队规范怎么进模型」这件事，三条产物目前仍是 **三种做法**：

- **PRD**：读 `skills/prd-generator/`，经 loader 拼进模型 prompt，用户无感
- **接口文档**：读 `backend/knowledge/api_docs/`，走关键词检索，还要弹出 **RAG 确认页** 让用户点「开始生成」
- **提示词套件**：生成规范写在 `prompts.py` 的 `PROMPTS_GENERATION_PROMPT` 里，**没有**对应的 `skills/prompts-generator/` 目录

## 当前问题：双轨知识注入

### PRD 已经在用 Skill，但很「手工」

仓库里已有：

```
skills/prd-generator/
├── instructions.md
└── references/
    ├── prd-template.md
    ├── writing-rules.md
    └── field-schema.json
```

后端通过 `document_service._load_skill_artifact()` 读取，但路径 **写死在 Python 里**，只认 `prd-generator` 这一个目录。加新规范、换绑定关系，都要改代码。

### 接口文档走 RAG，成本高、收益低

生成接口文档前，系统会：

1. 用 PRD + 澄清对话拼 query
2. 对 3 个静态 md 做关键词打分
3. 前端展示「找到 N 段资料」，等用户确认
4. 再把检索结果塞进 prompt

这些资料本质是 **固定的团队规范和历史示例**，每次让用户审批，摩擦大；检索能力也弱，称不上真正的 RAG 产品能力。

### 三条产物，三种规范来源

| 产物 | 团队规范放哪 | 用户是否感知 |
|------|-------------|--------------|
| PRD | `skills/prd-generator/` | 否 |
| 接口文档 | `knowledge/api_docs/` + RAG | 是（确认页） |
| 提示词套件 | `prompts.py` 硬编码 | 否，但也不可配置 |

说明：PRD 已经在把 skill **注入模型 prompt**；缺的是 **提示词套件这一步** 自己的 skill 目录，以及三条线统一的加载方式。

![三条产物当前的知识注入方式对比](https://pic.niumianoffer.com/images/fs/opt5-00-knowledge-injection-current.png)

## 目标：统一到 Skill 静默注入

Skill 知识层要做的，不是另起一套知识库，而是：

**在现有 `skills/` 目录上，加契约、加注册表、加统一 loader，让 PRD、接口文档、提示词套件三条生成线都走同一条 skill 注入管线。**

用户侧：

- 点「生成接口文档」→ **直接开始 Job**，不再出现 RAG 确认页
- 团队规范在后台自动注入，和 PRD 一样无感

工程侧：

- 新增 skill = 加目录 + 改 yaml，尽量不改 `document_service` 主流程
- `run_summary` 记录 `injected_skills`，知道这次用了哪些规范文件

用生活类比：

> 现在像做菜：主料菜谱（PRD）有标准配方本；配菜规范（接口文档）却要顾客先翻冰箱挑食材、签字确认再做。  
> 改完后，配方本统一放在厨房 `skills/` 柜子里，按菜名自动拿对应本子，顾客只等上菜。

## 和现有 `skills/` 的关系

**不替换、不搬家**，是在上面加一层「怎么发现、怎么加载」：

```
skills/prd-generator/          ← 已有，补 skill.yaml
skills/api-docs-generator/     ← 新建，迁入 knowledge 里的 md
skills/prompts-generator/      ← 新建，从 prompts.py 迁入提示词套件生成规范

config/skills.yaml             ← 声明 prd / api-docs / prompts 各绑哪些 skill
skill_loader                   ← 唯一读 skill 的入口
```

`prd-generator` 里的 `instructions.md`、`references/` **内容保留**，只是从「代码硬编码 open 文件」改成「loader 按注册表读取」。

![统一 Skill Loader 静默注入架构](https://pic.niumianoffer.com/images/fs/opt5-00-skill-loader-unified.png)

## 大概怎么做

分两篇实施（见同目录 `01`、`02` 改造说明）：

**基础设施**

- 定义 `skill.yaml` 契约
- `config/skills.yaml` 注册表
- `skill_loader` 统一加载
- PRD 相关路径先迁到 loader（行为应与改前一致）

**RAG 下线与管线接入**

- 新建 `api-docs-generator`、`prompts-generator`
- 生成 / 优化走 loader 拼 prompt
- 删除 `rag_service`、RAG API、前端确认页
- `run_summary.injected_skills` 可观测

```
用户点「生成接口文档」
  → 前端直接 POST /jobs（api-docs）
  → job_runner → document_service
  → skill_loader 加载 api-docs-generator 的 references
  → 静默拼进 prompt → 流式生成
  → run_summary 记录 injected_skills
```

## 本阶段明确不做

- 团队 `team.yaml` 覆盖、多租户配置
- Web 上传本团队规范、Skill 管理后台
- Skill 版本 pin、市场 / 插件安装
- 真向量 RAG、知识库入库（与优化七语义检索分开）
- 改造澄清对话、文档版本 diff、导出 ZIP
- 改造 v1 `App.tsx`

## 做了之后有什么优势

**对用户**

- 生成接口文档少一步确认，主路径更顺
- 三份产物的团队规范注入方式一致，都是静默、可配置

**对工程**

- 知识注入单点维护，删 RAG 双轨代码
- 与 Cursor / Agent 类产品的 Skill 模式对齐，后续扩展有挂点
- `injected_skills` 便于排查「为什么这版接口文档风格变了」

**对产品边界**

- 不引入新中间件，仍是本地 `skills/` 目录 + yaml 配置
- 生成 Job、版本管理、观测链路保持不变，只换 prompt 组装方式

## 后续平台化怎么长出来（本期不做）

本期搭好 loader + 注册表后，后续可在同一管线上叠加：

| 阶段 | 能力 |
|------|------|
| A | `team.yaml` 按团队覆盖某个 reference 文件 |
| B | 管理页上传规范、启用 / 禁用 skill |
| C | Skill 版本 pin，写入 `document_versions.metadata` |
| D | 大规范库内嵌检索（可接优化七） |

每一层都向后兼容：没有 team 配置时，用 `skills/` 默认文件即可。

Skill 知识层解决的是「团队知识怎么稳定、可维护地进模型」。和观测、Job、版本合在一起，v2 才从能生成，变成 **规范可配置、注入可追踪** 的专业流水线。
