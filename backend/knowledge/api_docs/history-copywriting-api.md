# 历史接口文档示例：AI 文案生成工具

## 背景

该项目是一个面向运营人员的文案生成工具，用户选择场景、风格、字数范围，并输入参考示例后，系统调用大模型生成多条可直接使用的文案。

## 核心接口

### 1. 生成文案

- **方法**：POST
- **路径**：`/api/v1/copywritings/generate`
- **功能**：根据用户输入生成 3 条不同风格的文案结果。

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| scenario_type | string | 否 | 场景分类，例如 `promotion`、`testimonial` |
| scenario_description | string | 否 | 具体场景描述，最多 200 字 |
| tone | string | 是 | 文案风格 |
| length_range | string | 是 | 字数范围 |
| references | string[] | 否 | 参考文案，最多 3 条 |

**校验规则**

- `scenario_type` 和 `scenario_description` 至少填写一项。
- `references` 单条最多 500 字。

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "cw_001",
        "content": "今天想认真分享一个我自己也在用的小工具...",
        "tone": "warm"
      }
    ]
  }
}
```

### 2. 重新生成文案

- **方法**：POST
- **路径**：`/api/v1/copywritings:regenerate`
- **功能**：基于上一次相同输入条件重新生成一组文案。

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| request_snapshot | object | 是 | 上一次生成所用的完整请求参数 |

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "cw_002",
        "content": "换个角度说，这件事真正省下的是你的创作时间...",
        "tone": "concise"
      }
    ]
  }
}
```

## 边缘接口

### 获取文案配置

- **方法**：GET
- **路径**：`/api/v1/copywritings/options`
- **功能**：返回场景、风格、字数范围等前端选项。

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "scenarios": [
      { "label": "产品推广", "value": "promotion" }
    ],
    "tones": [
      { "label": "专业正式", "value": "professional" }
    ],
    "length_ranges": [
      { "label": "50 字以内", "value": "under_50" }
    ]
  }
}
```
