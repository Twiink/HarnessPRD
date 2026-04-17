# 目录解析与文件解析

## 1. 为什么这件事重要

一套通用 skill 能不能独立，关键不只在内容，还在于：

> 运行时怎么找到这套内容。

如果 skill 的文件查找方式很随意，那么它就很难迁移。

## 2. 当前 `prd-generator` 的查找方式

后端当前在：

[`backend/services/document_service.py`](../../backend/services/document_service.py)

里通过 `_load_skill_artifact()` 读取 skill 文件。

其核心逻辑是：

```python
artifact_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "skills",
    "prd-generator",
    *path_parts,
)
```

也就是说，当前项目采用的是：

```text
项目根目录 / skills / <skill-name> / ...
```

这种静态定位方式。

## 3. 当前被读取的文件

### 3.1 PRD 生成时

会读取：

- `references/prd-template.md`
- `references/writing-rules.md`
- `instructions.md`

### 3.2 回填摘要时

会读取：

- `references/field-schema.json`

## 4. 文件解析是怎么做的

当前采用的是最朴素、最稳定的做法：

- Markdown 文件按 UTF-8 文本读入
- JSON 文件作为字符串读入后进入 Prompt，或由前后端直接解析

这样做的优点是：

- 成本低
- 稳定
- 不绑任何第三方 skill runtime

## 5. 这种设计的局限

当前还不是一个通用 skill 注册中心，它有明显边界：

1. skill 名称是写死的  
当前直接读取 `skills/prd-generator`

2. 没有动态发现  
不会自动扫描多个 skill 包

3. 没有版本协商  
只读当前文件系统上的一份 skill

## 6. 为什么当前阶段这已经够用

因为现在目标不是做 skill 平台，而是先把一个能力包走通。

先把“一个 skill 能稳定运行”做成，再去做：

- 多 skill 注册
- skill marketplace
- skill adapter
- skill versioning

会更稳。

## 7. 下一步可以怎么演进

未来可以把当前静态读取升级成：

```text
skills/
  registry.json
  prd-generator/
  api-designer/
  prompts-generator/
```

然后运行时：

1. 扫描 `skills/`
2. 读取每个 `skill.yaml`
3. 建立技能注册表
4. 按名称、版本、能力标签选择 skill

这会让目录解析从“项目内特例”升级成“通用 skill 运行时能力”。
