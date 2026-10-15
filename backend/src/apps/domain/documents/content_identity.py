"""Pure content identity rules shared by document and delivery use cases."""

import hashlib
from typing import Any


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def matches_content_hash(value: Any, content: str) -> bool:
    """Accept the existing browser's 16-character SHA-256 confirmation field."""
    digest = content_hash(content)
    return isinstance(value, str) and value in (digest, digest[:16])


def bind_metadata(content: str, metadata: dict[str, Any]) -> dict[str, Any]:
    bound = dict(metadata)
    digest = content_hash(content)
    if bound.get("content_hash") not in (None, digest):
        bound.pop("review", None)
        bound.pop("quality_gate", None)
    bound["content_hash"] = digest
    return bound


def valid_baseline(data: dict[str, Any], current: dict[str, Any] | None) -> bool:
    return bool(
        current
        and bool(current.get("id"))
        and data.get("prdBaselineConfirmed") is True
        and data.get("prdBaselineVersionId") == current["id"]
        and data.get("prdBaselineVersionNo") == current["version_no"]
        and data.get("prdContent") == current["content"]
        and matches_content_hash(data.get("prdBaselineContentHash"), current["content"])
    )
