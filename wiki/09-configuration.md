# 配置说明

## 环境变量

所有配置通过 `backend/.env` 文件设置。首次运行如果 `.env` 不存在，`start.sh` 会自动从 `.env.example` 复制。

### 完整配置项

```env
# ── LLM 配置 ────────────────────────────────────────────
# Anthropic API Key（必填，若使用 Anthropic）
ANTHROPIC_API_KEY=sk-ant-api03-...

# 自定义 API 端点（可选，用于代理或私有化部署）
# ANTHROPIC_BASE_URL=https://your-proxy.example.com

# OpenAI API Key（可选，若使用 OpenAI）
# OPENAI_API_KEY=sk-...

# 默认 LLM Provider：anthropic 或 openai（默认：anthropic）
DEFAULT_LLM_PROVIDER=anthropic

# 默认模型（默认：claude-3-5-sonnet-20241022）
DEFAULT_LLM_MODEL=claude-3-5-sonnet-20241022

# ── 服务器配置 ──────────────────────────────────────────
# 监听地址（默认：0.0.0.0）
# HOST=0.0.0.0

# 监听端口（默认：8000）
# PORT=8000

# ── CORS 配置 ───────────────────────────────────────────
# 允许的跨域来源（逗号分隔，默认：localhost:5173 和 localhost:3000）
# CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### 必填 vs 可选

| 变量 | 必填 | 说明 |
|------|------|------|
| `ANTHROPIC_API_KEY` | 是（使用 Anthropic 时） | 在 [console.anthropic.com](https://console.anthropic.com) 获取 |
| `OPENAI_API_KEY` | 是（使用 OpenAI 时） | 在 [platform.openai.com](https://platform.openai.com) 获取 |
| `DEFAULT_LLM_PROVIDER` | 否 | 默认 `anthropic` |
| `DEFAULT_LLM_MODEL` | 否 | 默认 `claude-3-5-sonnet-20241022` |
| `ANTHROPIC_BASE_URL` | 否 | 仅代理或私有化部署需要 |
| `HOST`/`PORT` | 否 | 生产环境可能需要调整 |
| `CORS_ORIGINS` | 否 | 生产环境需要设置为真实域名 |

## 支持的模型

### Anthropic
| 模型 ID | 推荐用途 |
|---------|---------|
| `claude-opus-4-6` | 最强，适合复杂推理，成本较高 |
| `claude-sonnet-4-6` | 性能均衡，推荐默认 |
| `claude-3-5-sonnet-20241022` | 经典版本，稳定成熟 |
| `claude-haiku-4-5-20251001` | 最快最便宜，适合简单任务 |

### OpenAI
| 模型 ID | 推荐用途 |
|---------|---------|
| `gpt-4o` | 最强 OpenAI 模型 |
| `gpt-4o-mini` | 性价比高 |
| `gpt-4-turbo` | 上一代 GPT-4 |

## 运行时配置更新

不重启服务，通过 API 切换模型或 Provider：

```bash
# 切换到 OpenAI GPT-4o
curl -X POST http://localhost:8000/api/config/update \
  -H "Content-Type: application/json" \
  -d '{"default_llm_provider": "openai", "default_llm_model": "gpt-4o"}'

# 切换回 Anthropic Claude
curl -X POST http://localhost:8000/api/config/update \
  -H "Content-Type: application/json" \
  -d '{"default_llm_provider": "anthropic", "default_llm_model": "claude-3-5-sonnet-20241022"}'

# 更新 API Key
curl -X POST http://localhost:8000/api/config/update \
  -H "Content-Type: application/json" \
  -d '{"anthropic_api_key": "sk-ant-api03-..."}'
```

> **注意：** 运行时更新仅影响内存中的配置，服务重启后恢复 `.env` 中的值。如需永久生效，修改 `.env` 文件。

## 自定义表单问题

编辑 `backend/core/questions_config.json`，可以：
- 修改问题文案
- 添加/删除问题
- 修改问题类型（text/textarea/select/radio）
- 调整哪些是必填（`required: true`）
- 调整哪些是高级问题（`advanced: true`）

**字段类型说明：**
- `text`：单行文本输入
- `textarea`：多行文本
- `select`：下拉选择（需提供 `options` 数组）
- `radio`：按钮组选择（需提供 `options` 数组）

**示例：添加一个新问题**
```json
{
  "id": "budget",
  "label": "预算范围",
  "question": "你的项目预算大概是多少？",
  "description": "帮助 AI 了解技术选型的约束",
  "type": "select",
  "options": ["10 万以内", "10-50 万", "50 万以上", "暂不确定"],
  "required": false,
  "advanced": true
}
```

## 自定义 PRD 模板

编辑 `backend/core/prd_template.md`，可以定制 PRD 文档格式。

- 文件存在且非空：AI 生成 PRD 时参考此格式（内容以对话为准）
- 文件不存在或为空：使用 Prompt 中内置的默认格式

适合场景：
- 公司有固定的 PRD 格式规范
- 需要添加特定章节（如用户故事、验收标准等）
- 需要特定的表格结构

## CORS 配置

开发环境默认允许 `localhost:5173`（Vite 默认端口）。

**生产环境需要修改：**
```env
CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

如果前端和后端在同一域名（通过 Nginx 代理），可以设置为：
```env
CORS_ORIGINS=https://your-domain.com
```

## 代理 / 私有化部署

如果你的 Anthropic API 通过代理访问（常见于国内网络）：

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=https://your-anthropic-proxy.com
```

`langchain-anthropic` 会将所有请求发到 `ANTHROPIC_BASE_URL`，代理需要兼容 Anthropic API 格式。

> **重要：** 使用代理时，如果代理不支持某些新字段（如 `context_management`），需要确保 `langchain-anthropic` 版本 `<0.3.0`（requirements.txt 已锁定此版本）。
