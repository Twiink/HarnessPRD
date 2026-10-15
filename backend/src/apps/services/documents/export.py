"""交付包 ZIP 导出。"""

from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from apps.db.connection import read_snapshot
from apps.domain.documents.content_identity import content_hash, valid_baseline
from apps.services.documents.versions import get_current_version
from apps.services.sessions.state import extract_title, load_session_data_raw


DOC_TYPE_FILES = {
    "prd": "PRD.md",
    "api-docs": "API-Docs.md",
    "prompts": "Prompts.md",
}

SESSION_FIELD_BY_DOC = {
    "prd": "prdContent",
    "api-docs": "apiDocsContent",
    "prompts": "promptsContent",
}


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", name.strip())
    return cleaned or "delivery"


def _doc_snapshot(session_id: str, session_data: Dict[str, Any], doc_type: str) -> Dict[str, Any]:
    current = get_current_version(session_id, doc_type)
    field = SESSION_FIELD_BY_DOC[doc_type]
    fallback_content = (session_data.get(field) or "").strip()
    if current:
        meta = current.get("metadata") or {}
        return {
            "content": current.get("content") or fallback_content,
            "version_no": current.get("version_no"),
            "version_id": current.get("id"),
            "quality_gate": meta.get("quality_gate"),
            "review": meta.get("review"),
            "derived_from": meta.get("derived_from"),
            "created_at": current.get("created_at"),
            "content_hash": content_hash(current.get("content") or ""),
        }
    return {
        "content": fallback_content,
        "version_no": None,
        "version_id": None,
        "quality_gate": None,
        "review": None,
        "derived_from": None,
        "created_at": None,
        "content_hash": content_hash(fallback_content),
    }


def _compute_stale_warnings(
    session_data: Dict[str, Any],
    snapshots: Dict[str, Dict[str, Any]],
) -> List[str]:
    warnings: List[str] = []
    api_meta = snapshots["api-docs"]
    prompts_meta = snapshots["prompts"]

    api_derived = (api_meta.get("derived_from") or {}) if api_meta.get("content") else {}
    if api_derived.get("unverified"):
        warnings.append("接口文档来源未验证，请检查生成输入")

    def stale(derived, prefix, snapshot):
        recorded_hash = derived.get(f"{prefix}_content_hash")
        if recorded_hash:
            return recorded_hash != snapshot["content_hash"]
        recorded_no = derived.get(f"{prefix}_version_no")
        return bool(
            recorded_no and snapshot.get("version_no") and recorded_no < snapshot["version_no"]
        )

    if stale(api_derived, "prd", snapshots["prd"]):
        warnings.append("PRD 已更新，接口文档需要同步")

    prompts_derived = (
        (prompts_meta.get("derived_from") or {}) if prompts_meta.get("content") else {}
    )
    if prompts_derived.get("unverified"):
        warnings.append("提示词来源未验证，请检查生成输入")
    if stale(prompts_derived, "prd", snapshots["prd"]):
        warnings.append("PRD 已更新，提示词需要同步")
    if not prompts_derived.get("api_docs_skipped") and stale(
        prompts_derived, "api_docs", snapshots["api-docs"]
    ):
        warnings.append("接口文档已更新，提示词需要同步")
    return warnings


def _build_readme(
    product_name: str,
    snapshots: Dict[str, Dict[str, Any]],
    manifest: Dict[str, Any],
) -> str:
    lines = [
        f"# {product_name} — 交付包",
        "",
        "由 harnessprd 导出。建议按以下顺序阅读：",
        "",
        "1. PRD.md — 产品需求",
        "2. API-Docs.md — 接口说明（如有）",
        "3. Prompts.md — AI 开发提示词（如有）",
        "",
        "## 文档清单",
        "",
    ]
    labels = {"prd": "PRD", "api-docs": "接口文档", "prompts": "提示词"}
    for doc_type, label in labels.items():
        snap = snapshots[doc_type]
        if not (snap.get("content") or "").strip():
            lines.append(f"- {label}：未包含")
            continue
        lines.append(f"- {label}：已包含")

    lines.extend(["", "## 质量摘要", ""])
    for doc_type, label in labels.items():
        snap = snapshots[doc_type]
        if not (snap.get("content") or "").strip():
            continue
        gate = snap.get("quality_gate") or {}
        review = snap.get("review") or {}
        gate_text = ("通过" if gate.get("passed") else "未通过") if gate else "未评估"
        score = gate.get("score")
        score_text = f"（{score} 分）" if score is not None else ""
        lines.append(f"- {label} quality_gate：{gate_text}{score_text}")
        if review.get("summary"):
            lines.append(f"  - Review：{review['summary']}")

    stale = manifest.get("stale_warnings") or []
    if stale:
        lines.extend(["", "## 过期提示", ""])
        for item in stale:
            lines.append(f"- {item}")

    lines.append("")
    return "\n".join(lines)


def build_delivery_zip(session_id: str) -> Tuple[bytes, str]:
    with read_snapshot():
        session_data = load_session_data_raw(session_id)
        product_name = extract_title(session_data, session_id)
        snapshots = {
            doc_type: _doc_snapshot(session_id, session_data, doc_type)
            for doc_type in DOC_TYPE_FILES
        }
    has_any = any((snap.get("content") or "").strip() for snap in snapshots.values())
    if not has_any:
        raise ValueError("没有可导出的文档内容")

    exported_at = datetime.now(timezone.utc).isoformat()
    stale_warnings = _compute_stale_warnings(session_data, snapshots)

    documents_manifest: Dict[str, Any] = {}
    for doc_type, snap in snapshots.items():
        if not (snap.get("content") or "").strip():
            continue
        entry: Dict[str, Any] = {
            "record_id": snap.get("version_id"),
            "saved_at": snap.get("created_at"),
            "content_hash": snap["content_hash"],
        }
        if (
            doc_type == "prd"
            and session_data.get("prdBaselineConfirmedAt")
            and valid_baseline(
                session_data,
                {
                    "id": snap.get("version_id"),
                    "version_no": snap.get("version_no"),
                    "content": snap.get("content"),
                },
            )
        ):
            entry["baseline_confirmed_at"] = session_data.get("prdBaselineConfirmedAt")
        if snap.get("quality_gate"):
            entry["quality_gate"] = snap["quality_gate"]
        if snap.get("review"):
            entry["review"] = {
                "passed": snap["review"].get("passed"),
                "summary": snap["review"].get("summary"),
            }
        if snap.get("derived_from"):
            derived = snap["derived_from"]
            entry["derived_from"] = {
                "prd_record_id": derived.get("prd_version_id"),
                "api_docs_record_id": derived.get("api_docs_version_id"),
                "api_docs_skipped": derived.get("api_docs_skipped", False),
                "prd_content_hash": derived.get("prd_content_hash"),
                "api_docs_content_hash": derived.get("api_docs_content_hash"),
            }
            if derived.get("unverified"):
                entry["derived_from"]["unverified"] = True
            if derived.get("input_content_hash"):
                entry["derived_from"]["input_content_hash"] = derived["input_content_hash"]
        documents_manifest[doc_type.replace("-", "_")] = entry

    manifest = {
        "product_name": product_name,
        "session_id": session_id,
        "exported_at": exported_at,
        "entry_mode": session_data.get("entryMode") or "structured",
        "documents": documents_manifest,
        "stale_warnings": stale_warnings,
    }

    readme = _build_readme(product_name, snapshots, manifest)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", readme)
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for doc_type, filename in DOC_TYPE_FILES.items():
            content = snapshots[doc_type].get("content") or ""
            if content.strip():
                zf.writestr(filename, content)

    filename = f"{_safe_filename(product_name)}-delivery.zip"
    return buffer.getvalue(), filename
