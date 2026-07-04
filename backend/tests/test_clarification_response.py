"""clarification_state 解析测试"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.clarification_response import (  # noqa: E402
    normalize_clarification_meta,
    parse_clarification_response,
    strip_clarification_state_block,
)


SAMPLE_REPLY = """好的，所有核心需求已确认。

目前定义的内容摘要如下：

- **注册 / 登录**：手机号 + 验证码

没有的话可以直接点击生成 PRD。

```clarification_state
{
  "open_questions": [],
  "ready_to_generate": true
}
```"""


def test_parse_clarification_response_strips_block_and_returns_meta():
    display, meta = parse_clarification_response(SAMPLE_REPLY)
    assert "```clarification_state" not in display
    assert "所有核心需求已确认" in display
    assert meta == {"open_questions": [], "ready_to_generate": True}


def test_normalize_clarification_meta_forces_ready_false_when_questions_exist():
    meta = normalize_clarification_meta(
        {
            "open_questions": ["昵称是否可修改？"],
            "ready_to_generate": True,
        }
    )
    assert meta["open_questions"] == ["昵称是否可修改？"]
    assert meta["ready_to_generate"] is False


def test_strip_clarification_state_block_removes_complete_fence():
    stripped = strip_clarification_state_block(SAMPLE_REPLY)
    assert "```" not in stripped
    assert stripped.endswith("生成 PRD。")


def test_strip_clarification_state_block_removes_partial_fence():
    partial = SAMPLE_REPLY.split("```clarification_state")[0] + "\n```clarification_st"
    stripped = strip_clarification_state_block(partial)
    assert "```" not in stripped
    assert stripped.endswith("生成 PRD。")


def test_parse_clarification_response_without_block_returns_original():
    text = "请先确认昵称是否可修改？"
    display, meta = parse_clarification_response(text)
    assert display == text
    assert meta is None
