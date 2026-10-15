"""Provenance and client-controlled session state cannot invalidate delivery identity."""

import asyncio
import io
import json
import zipfile

import pytest

from apps.core.config import Settings, settings_context
from apps.db.repositories.jobs import JobRepository
from apps.domain.documents.content_identity import content_hash
from apps.runtime.job_executor import JobExecutor
from apps.services.documents import versions as documents
from apps.services.documents.export import build_delivery_zip
from apps.services.sessions import state as sessions


def archive(sid):
    data, _ = build_delivery_zip(sid)
    result = zipfile.ZipFile(io.BytesIO(data))
    return json.loads(result.read("manifest.json")), result


@pytest.mark.parametrize("artifact", ["optimize-api-docs", "optimize-prompts"])
def test_optimization_uses_submission_provenance_after_sources_change(isolated_database, artifact):
    sid = sessions.save_session({"prdContent": "# Original"})["id"]
    doc_type = artifact.removeprefix("optimize-")
    source = documents.build_source_snapshot(sid, doc_type, {"prd_content": "# Original"})
    documents.sync_from_job(
        sid,
        doc_type,
        "old generated",
        source_job_id="old",
        extra_metadata={"derived_from": source},
    )
    payload = {"current_content": "old generated", "instruction": "polish"}
    payload["_source_snapshot"] = documents.build_source_snapshot(sid, artifact, payload)
    assert payload["_source_snapshot"]["prd_content_hash"] == content_hash("# Original")
    documents.checkpoint(sid, "prd", "# Changed")
    documents.sync_from_job(
        sid,
        doc_type,
        "new unrelated document",
        source_job_id="intervening",
        extra_metadata={"derived_from": {"prd_content_hash": content_hash("# Changed")}},
    )

    class FakeDocuments:
        async def optimize_document_stream(self, kind, content, *args):
            assert kind == doc_type
            assert content == "old generated"
            yield {"type": "done", "content": "optimized original"}

    async def run():
        async def emit(event):
            pass

        config = Settings(_env_file=None, database_path=isolated_database.path)
        with settings_context(config):
            return await JobExecutor(FakeDocuments()).execute(
                {"session_id": sid, "artifact": artifact, "payload_json": json.dumps(payload)}, emit
            )

    outcome = asyncio.run(run())
    documents.sync_from_job(
        sid, artifact, outcome.content, source_job_id="optimized", extra_metadata=outcome.metadata
    )
    current = documents.get_current_version(sid, doc_type)
    assert current["metadata"]["derived_from"]["prd_content_hash"] == content_hash("# Original")
    manifest, _ = archive(sid)
    assert manifest["stale_warnings"]


@pytest.mark.parametrize("artifact", ["optimize-api-docs", "optimize-prompts"])
def test_override_optimization_marks_unknown_source_and_warns(isolated_database, artifact):
    doc_type = artifact.removeprefix("optimize-")
    sid = sessions.save_session({"prdContent": "# PRD"})["id"]
    documents.sync_from_job(sid, doc_type, "working", source_job_id="working")
    snapshot = documents.build_source_snapshot(sid, artifact, {"current_content": "external"})
    assert snapshot["unverified"] is True
    assert snapshot["input_content_hash"] == content_hash("external")
    documents.sync_from_job(
        sid,
        artifact,
        "optimized external",
        source_job_id="external",
        extra_metadata={"derived_from": snapshot},
    )
    manifest, _ = archive(sid)
    assert any("来源未验证" in warning for warning in manifest["stale_warnings"])
    assert manifest["documents"][doc_type.replace("-", "_")]["derived_from"]["unverified"] is True


def test_export_preserves_document_bytes_and_hash(isolated_database):
    sid = sessions.save_session({})["id"]
    content = "\n# Generated\n\n"
    documents.sync_from_job(sid, "prd", content, source_job_id="generated")
    manifest, result = archive(sid)
    assert result.read("PRD.md") == content.encode()
    assert manifest["documents"]["prd"]["content_hash"] == content_hash(content)


@pytest.mark.parametrize("doc_type", ["api-docs", "prompts"])
def test_restore_preserves_historical_source_and_bytes_without_revalidating_reports(
    isolated_database, doc_type
):
    sid = sessions.save_session({"prdContent": "# Original"})["id"]
    source = documents.build_source_snapshot(sid, doc_type, {"prd_content": "# Original"})
    original_content = "\noriginal generated\n"
    documents.sync_from_job(
        sid,
        doc_type,
        original_content,
        source_job_id="original",
        review={"passed": True},
        extra_metadata={"derived_from": source, "quality_gate": {"passed": True}},
    )
    original = documents.get_current_version(sid, doc_type)
    documents.checkpoint(sid, "prd", "# New PRD")
    documents.sync_from_job(sid, doc_type, "replacement", source_job_id="replacement")
    documents.restore_version(sid, doc_type, original["id"])
    restored = documents.get_current_version(sid, doc_type)
    assert restored["content"] == original_content
    assert restored["metadata"]["derived_from"] == source
    assert restored["metadata"]["content_hash"] == content_hash(original_content)
    assert "review" not in restored["metadata"]
    assert "quality_gate" not in restored["metadata"]
    manifest, _ = archive(sid)
    assert manifest["stale_warnings"]


@pytest.mark.parametrize("field", ["activeJobId", "activeOptimizeJobId"])
def test_client_foreign_job_cannot_control_document_persistence(isolated_database, field):
    foreign = sessions.save_session({})["id"]
    jobs = JobRepository(isolated_database)
    artifact = "optimize-prd" if field == "activeOptimizeJobId" else "prd"
    job_id = jobs.create(foreign, artifact, {}, None, "foreign", None)
    job = jobs.claim("worker", 30, 3)
    jobs.progress(job_id, "worker", job["attempt_count"], draft_content="foreign draft")
    sid = sessions.save_session({"prdContent": "own content", field: job_id})["id"]
    data = sessions.get_session(sid)["session_data"]
    assert data.get(field) is None
    assert data["prdContent"] == "own content"
    assert documents.get_current_version(sid, "prd")["content"] == "own content"


def test_existing_foreign_or_missing_job_pointer_is_sanitized_on_read(isolated_database):
    sid = sessions.save_session({"prdContent": "own content"})["id"]
    foreign = sessions.save_session({})["id"]
    jobs = JobRepository(isolated_database)
    job_id = jobs.create(foreign, "prd", {}, None, "foreign", None)
    job = jobs.claim("worker", 30, 3)
    jobs.progress(job_id, "worker", job["attempt_count"], draft_content="foreign draft")
    raw = sessions.load_session_data_raw(sid)
    raw.update(activeJobId=job_id, activeOptimizeJobId="missing")
    with isolated_database.transaction() as conn:
        conn.execute(
            "UPDATE project_sessions SET session_data=? WHERE id=?", (json.dumps(raw), sid)
        )
    data = sessions.get_session(sid)["session_data"]
    assert data["prdContent"] == "own content"
    assert data["activeJobId"] is None
    assert data["activeOptimizeJobId"] is None


def test_export_omits_timestamp_until_baseline_identity_is_valid(isolated_database):
    sid = sessions.save_session(
        {
            "prdContent": "# PRD",
            "prdBaselineConfirmed": False,
            "prdBaselineConfirmedAt": "unverified timestamp",
        }
    )["id"]
    manifest, _ = archive(sid)
    assert "baseline_confirmed_at" not in manifest["documents"]["prd"]
    current = documents.get_current_version(sid, "prd")
    sessions.save_session(
        {
            "prdBaselineConfirmed": True,
            "prdBaselineConfirmedAt": "confirmed timestamp",
            "prdBaselineVersionId": current["id"],
            "prdBaselineVersionNo": current["version_no"],
            "prdBaselineContentHash": content_hash(current["content"])[:16],
        },
        sid,
    )
    manifest, _ = archive(sid)
    assert manifest["documents"]["prd"]["baseline_confirmed_at"] == "confirmed timestamp"
