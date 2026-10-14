# 历史接口文档示例：轻量任务管理工具

## 背景

该项目面向小团队任务协作，核心功能包括任务创建、任务分配、状态流转、截止时间提醒和列表查询。

## 核心接口

### 1. 创建任务

- **方法**：POST
- **路径**：`/api/v1/tasks`
- **功能**：创建一条任务，并可指定负责人和截止时间。

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| title | string | 是 | 任务标题，最多 80 字 |
| description | string | 否 | 任务描述 |
| assignee_id | string | 否 | 负责人用户 ID |
| due_at | string | 否 | 截止时间，ISO 8601 |
| priority | string | 否 | 优先级：low、medium、high |

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "task_001",
    "title": "完成首页改版",
    "status": "todo",
    "assignee_id": "user_001",
    "due_at": "2026-04-22T18:00:00+08:00"
  }
}
```

### 2. 更新任务状态

- **方法**：PATCH
- **路径**：`/api/v1/tasks/{task_id}/status`
- **功能**：更新任务状态。

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| status | string | 是 | `todo`、`doing`、`done` |

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "task_001",
    "status": "doing"
  }
}
```

### 3. 查询任务列表

- **方法**：GET
- **路径**：`/api/v1/tasks`
- **功能**：按状态、负责人、关键词分页查询任务列表。

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| status | string | 否 | 任务状态 |
| assignee_id | string | 否 | 负责人用户 ID |
| keyword | string | 否 | 搜索关键词 |
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页数量，默认 20 |

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "task_001",
        "title": "完成首页改版",
        "status": "doing"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

## 边缘接口

### 获取任务筛选选项

- **方法**：GET
- **路径**：`/api/v1/tasks/options`
- **功能**：返回任务状态、优先级等枚举配置。
