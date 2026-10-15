"""quality_gate 单元测试"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from apps.domain.documents.quality import run_quality_gate  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
SAMPLE_PRD = (
    REPO_ROOT / "skills/prd-generator/references/examples/friend-circle-copywriter.output.md"
).read_text(encoding="utf-8")


def test_prd_sample_passes():
    result = run_quality_gate("prd", SAMPLE_PRD)
    assert result["doc_type"] == "prd"
    assert result["score"] >= 80
    assert result["passed"] is True


def test_prd_missing_scope_fails():
    broken = SAMPLE_PRD.replace("## 6. 项目范围", "## 6. 备注")
    result = run_quality_gate("prd", broken)
    assert result["passed"] is False
    assert any(c["id"] == "prd.section.scope" and not c["passed"] for c in result["checks"])


def test_empty_content():
    result = run_quality_gate("prd", "")
    assert result["passed"] is False
    assert result["checks"][0]["id"] == "empty_content"


def test_api_docs_minimal():
    content = """
## 核心接口
### POST /api/tasks
{"code": 0, "data": {}}
## 边缘接口
### GET /api/health
"""
    result = run_quality_gate("api-docs", content)
    assert result["doc_type"] == "api-docs"
    assert any(c["id"] == "api.section.core" and c["passed"] for c in result["checks"])


def test_api_docs_missing_core():
    content = '{"code": 0, "data": {}} /api/x'
    result = run_quality_gate("api-docs", content)
    assert any(c["id"] == "api.section.core" and not c["passed"] for c in result["checks"])


def test_api_docs_skill_template_format():
    """skill 示例格式：### 标题 + **方法** / **路径** 分行"""
    content = """
## 核心接口

### 1. 创建申请

- **方法**：POST
- **路径**：`/api/applications`
- **功能**：发起人选择模板并填写表单。

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
| template_id | string | 是 | 模板 ID |

**响应示例**

```json
{"code": 0, "message": "ok", "data": {"id": "app_001"}}
```

## 边缘接口

### 健康检查

- **方法**：GET
- **路径**：`/api/health`
"""
    result = run_quality_gate("api-docs", content)
    endpoint_check = next(c for c in result["checks"] if c["id"] == "api.endpoint.count")
    assert endpoint_check["passed"] is True
    assert result["score"] == 100


def test_prompts_sections():
    content = """
## 1. 项目总览提示词
## 2. 功能开发提示词
### 功能A
## 3. 接口实现提示词
## 4. 前端开发提示词
## 5. 代码审查提示词
"""
    result = run_quality_gate(
        "prompts",
        content,
        {"prd_content": "| 功能名称 |\n| a |", "api_docs_content": "x"},
    )
    assert result["doc_type"] == "prompts"
    assert any(c["id"] == "prompts.section.context" and c["passed"] for c in result["checks"])
