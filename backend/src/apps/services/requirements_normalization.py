"""将需求来源中的功能集合整合为完整项目的功能清单。"""

from __future__ import annotations

import re
from typing import Any


def normalize_feature_fields(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(data)
    rows: list[dict[str, Any]] = []
    for key in ("features", "mvp_features", "v2_features"):
        source = result.pop(key, None)
        if isinstance(source, str):
            source = source.splitlines()
        if not isinstance(source, list):
            continue
        for item in source:
            if isinstance(item, str):
                text = re.sub(r"^\s*(?:[-*•]\s*|\d+[.)、]\s*)", "", item).strip()
                parts = [part.strip() for part in re.split(r"[|｜]", text)]
                row = {
                    "name": parts[0],
                    "description": parts[1] if len(parts) > 1 else parts[0],
                    "user_value": parts[2] if len(parts) > 2 else "",
                }
            elif isinstance(item, dict):
                row = dict(item)
                row.update(
                    {
                        key: str(item.get(key) or "").strip()
                        for key in ("name", "description", "user_value")
                    }
                )
            else:
                continue
            if not any(row.values()):
                continue
            existing = next(
                (entry for entry in rows if row["name"] and entry["name"] == row["name"]),
                None,
            )
            if existing is None:
                rows.append(row)
                continue
            extra_fields = set(row) - {"name", "description", "user_value"}
            if any(field in existing and existing[field] != row[field] for field in extra_fields):
                rows.append(row)
                continue
            existing.update({field: row[field] for field in extra_fields})
            for field in ("description", "user_value"):
                value = row[field]
                if not value or value == "待确认" or value == existing[field]:
                    continue
                if existing[field] in ("", "待确认", existing["name"]):
                    existing[field] = value
                elif value != row["name"] and value not in existing[field].split("；"):
                    existing[field] += f"；{value}"
    result["features"] = rows
    return result


def normalize_session_requirements(session_data: dict[str, Any]) -> dict[str, Any]:
    result = dict(session_data)
    for key in ("formData", "requirementsSummary", "pendingSummary"):
        value = result.get(key)
        if isinstance(value, dict):
            result[key] = normalize_feature_fields(value)
    return result
