"""任务状态、输入及执行结果契约。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Artifact(str, Enum):
    PRD = "prd"
    API_DOCS = "api-docs"
    PROMPTS = "prompts"
    OPTIMIZE_PRD = "optimize-prd"
    OPTIMIZE_API_DOCS = "optimize-api-docs"
    OPTIMIZE_PROMPTS = "optimize-prompts"


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


ACTIVE_STATUSES = ("pending", "queued", "running", "interrupted")
TERMINAL_STATUSES = ("succeeded", "failed", "cancelled")


@dataclass
class JobOutcome:
    content: str
    review: dict[str, Any] | None = None
    result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class LeaseLostError(Exception):
    """执行者已失去任务所有权，必须停止写入。"""
