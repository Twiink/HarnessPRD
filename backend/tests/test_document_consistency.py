"""Content identity, baseline validity and coherent delivery snapshots."""

import hashlib
import io
import json
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from apps.core.errors import DomainError
from apps.db.connection import database_context
from apps.services.documents import versions as documents
from apps.services.sessions import state as sessions
from apps.services.documents import export as delivery
from apps.services.generation.guards import assert_can_create_job


def digest(content):
    return hashlib.sha256(content.encode()).hexdigest()


def confirmed_session(content="# Original"):
    sid = sessions.save_session({"prdContent": content})["id"]
    version = documents.get_current_version(sid, "prd")
    sessions.save_session(
        {
            "prdBaselineConfirmed": True,
            "prdBaselineConfirmedAt": "2026-10-15T00:00:00Z",
            "prdBaselineVersionId": version["id"],
            "prdBaselineVersionNo": version["version_no"],
            "prdBaselineContentHash": digest(content)[:16],
        },
        sid,
    )
    return sid


@pytest.mark.parametrize("operation", ["save", "checkpoint", "restore", "generate", "optimize"])
def test_content_changes_invalidate_baseline_and_reports(isolated_database, operation):
    sid = confirmed_session()
    original = documents.get_current_version(sid, "prd")
    documents.patch_current_metadata(
        sid, "prd", {"review": {"passed": True}, "quality_gate": {"passed": True}}
    )
    if operation == "restore":
        earlier = documents.checkpoint(sid, "prd", "# Earlier")
        documents.restore_version(sid, "prd", original["id"])
        confirmed_session_data = sessions.load_session_data_raw(sid)
        current = documents.get_current_version(sid, "prd")
        sessions.save_session(
            {
                **confirmed_session_data,
                "prdBaselineConfirmed": True,
                "prdBaselineVersionId": current["id"],
                "prdBaselineVersionNo": current["version_no"],
                "prdBaselineContentHash": digest(current["content"])[:16],
            },
            sid,
        )
        documents.restore_version(sid, "prd", earlier["version_id"])
    elif operation == "save":
        sessions.save_session({"prdContent": "# Changed"}, sid)
    elif operation == "checkpoint":
        documents.checkpoint(sid, "prd", "# Changed")
    else:
        documents.sync_from_job(
            sid,
            "optimize-prd" if operation == "optimize" else "prd",
            "# Changed",
            source_job_id="changed",
        )
    data = sessions.load_session_data_raw(sid)
    assert data["prdBaselineConfirmed"] is False
    assert data["prdBaselineContentHash"] is None
    meta = documents.get_current_version(sid, "prd")["metadata"]
    assert "review" not in meta
    assert "quality_gate" not in meta


def test_new_reports_bound_to_content_and_note_preserves_them(isolated_database):
    sid = sessions.save_session({"prdContent": "# Original"})["id"]
    documents.patch_current_metadata(
        sid, "prd", {"review": {"passed": True}, "quality_gate": {"passed": True}}
    )
    current = documents.get_current_version(sid, "prd")
    assert current["metadata"]["content_hash"] == digest("# Original")
    documents.update_version_note(sid, "prd", current["id"], "checked")
    noted = documents.get_current_version(sid, "prd")
    assert noted["metadata"]["review"] == current["metadata"]["review"]
    assert noted["metadata"]["quality_gate"] == current["metadata"]["quality_gate"]


def test_new_generation_reports_and_unchanged_baseline_remain_valid(isolated_database):
    sid = confirmed_session()
    sessions.save_session({"custom": "metadata only"}, sid)
    assert sessions.load_session_data_raw(sid)["prdBaselineConfirmed"] is True
    documents.sync_from_job(
        sid,
        "prd",
        "# New",
        review={"passed": True},
        source_job_id="new",
        extra_metadata={"quality_gate": {"passed": True}},
    )
    sessions.sync_session_on_job_complete(sid, "prd", "# New", {"passed": True})
    current = documents.get_current_version(sid, "prd")
    assert current["metadata"]["content_hash"] == digest("# New")
    assert current["metadata"]["review"] == {"passed": True}
    assert current["metadata"]["quality_gate"] == {"passed": True}
    assert sessions.load_session_data_raw(sid)["prdReviewResult"] == {"passed": True}


def test_partial_save_preserves_documents_newer_than_session_mirror(isolated_database):
    sid = sessions.save_session({"prdContent": "old"})["id"]
    documents.sync_from_job(sid, "prd", "new", source_job_id="new")
    sessions.save_session({"custom": "update"}, sid)
    assert documents.get_current_version(sid, "prd")["content"] == "new"
    assert sessions.load_session_data_raw(sid)["prdContent"] == "new"


def test_old_client_review_does_not_revalidate_edited_document(isolated_database):
    sid = sessions.save_session({"prdContent": "old", "prdReviewResult": {"passed": True}})["id"]
    sessions.save_session({"prdContent": "new"}, sid)
    sessions.save_session({"prdReviewResult": {"passed": True}}, sid)
    assert "review" not in documents.get_current_version(sid, "prd")["metadata"]
    assert sessions.load_session_data_raw(sid)["prdReviewResult"] is None


@pytest.mark.parametrize(
    "tamper",
    [
        {"prdBaselineVersionId": "other"},
        {"prdBaselineContentHash": "bad-hash"},
        {"prdBaselineVersionNo": 99},
    ],
)
def test_server_rejects_stale_baseline_identity(isolated_database, tamper):
    sid = confirmed_session()
    sessions.save_session(tamper, sid)
    data = sessions.load_session_data_raw(sid)
    assert not data["prdBaselineConfirmed"]
    with pytest.raises(DomainError) as error:
        assert_can_create_job(data, "api-docs")
    assert error.value.code == "BASELINE_REQUIRED"


def test_confirmed_baseline_uses_actual_current_document(isolated_database):
    sid = confirmed_session()
    data = sessions.load_session_data_raw(sid)
    assert_can_create_job(data, "api-docs")
    data["prdContent"] = "# Forged mirror"
    with pytest.raises(DomainError):
        assert_can_create_job(data, "api-docs")
    other = sessions.save_session({"prdContent": "# Other"})["id"]
    with pytest.raises(DomainError):
        assert_can_create_job(sessions.load_session_data_raw(sid), "api-docs", session_id=other)


@pytest.mark.parametrize("content", ["", "  ", None])
def test_explicit_clear_rejected_and_omitted_document_preserved(isolated_database, content):
    sid = sessions.save_session({"prdContent": "# Original"})["id"]
    with pytest.raises(DomainError) as error:
        sessions.save_session({"prdContent": content}, sid)
    assert error.value.status_code == 422
    sessions.save_session({"custom": "keep"}, sid)
    assert sessions.get_session(sid)["session_data"]["prdContent"] == "# Original"
    assert sessions.save_session({"prdContent": content})["id"]


def test_source_snapshot_records_actual_inputs_and_hashes(isolated_database):
    sid = sessions.save_session({"prdContent": "# Original", "apiDocsContent": "API"})["id"]
    original = documents.get_current_version(sid, "prd")
    source = documents.build_source_snapshot(
        sid, "prompts", {"prd_content": "# Original", "api_docs_content": "API"}
    )
    assert source["prd_version_id"] == original["id"]
    assert source["prd_content_hash"] == digest("# Original")
    override = documents.build_source_snapshot(sid, "api-docs", {"prd_content": "# Override"})
    assert override["prd_content_hash"] == digest("# Override")
    assert override.get("prd_version_id") is None
    assert override.get("prd_version_no") is None


def test_export_detects_content_changes_without_version_increment(isolated_database):
    sid = sessions.save_session({"prdContent": "# Original"})["id"]
    source = documents.build_source_snapshot(sid, "api-docs", {"prd_content": "# Original"})
    documents.sync_from_job(
        sid, "api-docs", "API", source_job_id="api", extra_metadata={"derived_from": source}
    )
    sessions.save_session({"prdContent": "# Modified"}, sid)
    data, _ = delivery.build_delivery_zip(sid)
    manifest = json.loads(zipfile.ZipFile(io.BytesIO(data)).read("manifest.json"))
    assert "PRD 已更新，接口文档需要同步" in manifest["stale_warnings"]


def test_queries_do_not_acquire_write_lock(isolated_database):
    sid = sessions.save_session({"prdContent": "# Original"})["id"]
    current = documents.get_current_version(sid, "prd")
    isolated_database.busy_timeout_ms = 10
    conn = isolated_database.connect()
    conn.execute("BEGIN IMMEDIATE")
    try:
        assert sessions.list_sessions()
        assert sessions.get_session(sid)
        assert documents.get_current_version(sid, "prd")
        assert documents.get_documents_by_session(sid)
        assert documents.list_versions(sid, "prd")
        assert documents.get_version(sid, "prd", current["id"])
        assert delivery.build_delivery_zip(sid)
    finally:
        conn.rollback()
        conn.close()


def test_export_reads_coherent_snapshot_and_compresses_outside_transaction(
    isolated_database, monkeypatch
):
    sid = sessions.save_session({"prdContent": "old PRD", "apiDocsContent": "old API"})["id"]
    original = delivery._doc_snapshot
    original_zip = delivery.zipfile.ZipFile

    def open_zip(*args, **kwargs):
        with isolated_database.read() as conn:
            assert not conn.in_transaction
        return original_zip(*args, **kwargs)

    def snapshot(session_id, data, doc_type):
        result = original(session_id, data, doc_type)
        if doc_type == "prd":

            def update():
                with database_context(isolated_database):
                    sessions.save_session(
                        {"prdContent": "new PRD", "apiDocsContent": "new API"}, sid
                    )

            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(update).result(timeout=5)
        return result

    monkeypatch.setattr(delivery, "_doc_snapshot", snapshot)
    monkeypatch.setattr(delivery.zipfile, "ZipFile", open_zip)
    data, _ = delivery.build_delivery_zip(sid)
    archive = zipfile.ZipFile(io.BytesIO(data))
    assert archive.read("PRD.md") == b"old PRD"
    assert archive.read("API-Docs.md") == b"old API"
