# 团队接口设计规范（示例）

## 适用范围

本文档用于约束业务系统的 HTTP API 设计。生成接口文档时，应优先遵循这里的命名、响应结构、错误码和安全要求。

## 路径命名

- 基础路径统一使用 `/api/v1`。
- 资源使用复数名词，例如 `/api/v1/tasks`、`/api/v1/copywritings`。
- 动作用子资源表达，避免在路径中使用动词。例如重新生成文案使用 `POST /api/v1/copywritings:regenerate`，不要使用 `/regenerateCopywriting`。
- 查询类接口使用 `GET`，创建使用 `POST`，全量更新使用 `PUT`，局部更新使用 `PATCH`，删除使用 `DELETE`。
- 批量接口使用 `/batch` 子路径，例如 `POST /api/v1/copywritings/batch`.

## 请求规范

- 请求体统一使用 JSON。
- 字段命名使用 `snake_case`。
- 分页参数统一为 `page`、`page_size`。
- 排序参数统一为 `sort_by`、`sort_order`，`sort_order` 只允许 `asc` 或 `desc`。
- 时间字段统一使用 ISO 8601 字符串，例如 `2026-04-22T10:30:00+08:00`。
- 客户端生成的幂等键使用 `Idempotency-Key` 请求头。

## 响应规范

所有成功响应使用统一包裹结构：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

列表响应的 `data` 使用以下结构：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

## 错误响应

错误响应也使用统一结构：

```json
{
  "code": "VALIDATION_ERROR",
  "message": "参数校验失败",
  "details": [
    {
      "field": "scenario",
      "reason": "场景分类和场景描述至少填写一项"
    }
  ]
}
```

常用错误码：

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| VALIDATION_ERROR | 400 | 参数校验失败 |
| UNAUTHORIZED | 401 | 未认证或认证失效 |
| FORBIDDEN | 403 | 无权限 |
| NOT_FOUND | 404 | 资源不存在 |
| RATE_LIMITED | 429 | 请求过于频繁 |
| INTERNAL_ERROR | 500 | 服务端异常 |

## 安全要求

- API Key、模型 Key、第三方密钥只能存储在服务端环境变量中。
- 前端不得直接调用大模型供应商接口。
- 生成类接口必须做频率限制。
- 用户输入需要做长度限制和基础内容校验。
- 如果接口涉及用户数据，需要在接口文档中明确鉴权方式。

## 接口文档输出要求

- 每个接口必须包含接口名称、Method + Path、功能说明、请求参数表、响应示例、错误码。
- 核心接口和边缘接口必须分组。
- 如果某个功能不需要后端接口，应在文档中明确说明原因。
