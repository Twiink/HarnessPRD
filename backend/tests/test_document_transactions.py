"""Session/document invariants under failures, replay and concurrent writers."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from apps.db.connection import database_context, get_connection, transaction
from apps.services.documents import versions as documents
from apps.services.sessions import state as sessions
from apps.core.errors import DomainError
from apps.domain.documents.content_identity import content_hash


@pytest.fixture
def session_id(isolated_database):
    return sessions.save_session({"prdContent": "# Original"})["id"]


def test_checkpoint_restore_preserve_history_and_mirror(session_id):
    original = documents.get_current_version(session_id, "prd")
    documents.patch_current_metadata(session_id, "prd", {"review": {"score": 80}})
    saved = documents.checkpoint(session_id, "prd", "# Revised", "before review")
    current = documents.get_current_version(session_id, "prd")
    assert current["parent_version_id"] == original["id"]
    assert current["metadata"] == {
        "change_note": "before review",
        "content_hash": content_hash("# Revised"),
    }
    assert sessions.load_session_data_raw(session_id)["prdContent"] == "# Revised"
    restored = documents.restore_version(session_id, "prd", original["id"])
    assert restored["version_no"] == 3
    current = documents.get_current_version(session_id, "prd")
    assert current["parent_version_id"] == saved["version_id"]
    assert current["metadata"]["restored_from_version_id"] == original["id"]
    assert "review" not in current["metadata"]
    assert sessions.load_session_data_raw(session_id)["prdContent"] == "# Original"
    assert documents.get_version(session_id, "prd", saved["version_id"])["content"] == "# Revised"


def test_note_trim_clear_preserve_other_metadata_and_scope(session_id, isolated_database):
    current = documents.get_current_version(session_id, "prd")
    documents.patch_current_metadata(session_id, "prd", {"review": {"score": 80}})
    noted = documents.update_version_note(session_id, "prd", current["id"], "  checked  ")
    assert noted["metadata"] == {
        "change_note": "checked",
        "review": {"score": 80},
        "content_hash": content_hash("# Original"),
    }
    cleared = documents.update_version_note(session_id, "prd", current["id"], "   ")
    assert cleared["metadata"] == {
        "review": {"score": 80},
        "content_hash": content_hash("# Original"),
    }
    other = sessions.save_session({"prdContent": "# Other"})["id"]
    with pytest.raises(documents.VersionNotFoundError):
        documents.update_version_note(other, "prd", current["id"], "unauthorized")
    assert (
        documents.get_version(session_id, "prd", current["id"])["metadata"] == cleared["metadata"]
    )


@pytest.mark.parametrize("operation", ["checkpoint", "restore"])
def test_version_and_mirror_rollback_together(session_id, monkeypatch, operation):
    original = documents.get_current_version(session_id, "prd")
    if operation == "restore":
        documents.checkpoint(session_id, "prd", "# Revised")
    before = documents.list_versions(session_id, "prd")
    mirror = sessions.load_session_data_raw(session_id)

    def fail(*args, **kwargs):
        raise RuntimeError("mirror write failed")

    monkeypatch.setattr(sessions, "sync_session_mirror_for_doc_type", fail)
    with pytest.raises(RuntimeError, match="mirror write failed"):
        if operation == "checkpoint":
            documents.checkpoint(session_id, "prd", "# Must rollback")
        else:
            documents.restore_version(session_id, "prd", original["id"])
    assert documents.list_versions(session_id, "prd") == before
    assert sessions.load_session_data_raw(session_id) == mirror


def test_outer_transaction_rolls_back_note_and_content(session_id):
    original = documents.get_current_version(session_id, "prd")
    with pytest.raises(RuntimeError, match="abort"):
        with transaction():
            documents.update_version_note(session_id, "prd", original["id"], "rollback")
            documents.update_current_content(
                session_id, "prd", "# Abort", documents.VersionSourceKind.AUTO_SAVE
            )
            raise RuntimeError("abort")
    assert documents.get_current_version(session_id, "prd") == original


@pytest.mark.parametrize("existing", [False, True])
def test_save_session_and_documents_rollback_together(isolated_database, monkeypatch, existing):
    session_id = sessions.save_session({"prdContent": "# Original"})["id"] if existing else None
    before = sessions.list_sessions()

    def fail(*args, **kwargs):
        raise RuntimeError("document write failed")

    monkeypatch.setattr(sessions, "sync_session_content_to_documents", fail)
    with pytest.raises(RuntimeError, match="document write failed"):
        sessions.save_session({"prdContent": "# Abort"}, session_id)
    assert sessions.list_sessions() == before
    if existing:
        assert sessions.load_session_data_raw(session_id)["prdContent"] == "# Original"
        assert documents.get_current_version(session_id, "prd")["content"] == "# Original"


def test_get_session_backfill_rolls_back_with_refresh_failure(isolated_database, monkeypatch):
    session_id = sessions.save_session({})["id"]
    with get_connection() as conn:
        conn.execute(
            "UPDATE project_sessions SET session_data=? WHERE id=?",
            ('{"prdContent":"legacy"}', session_id),
        )

    def fail(*args, **kwargs):
        raise RuntimeError("refresh failed")

    monkeypatch.setattr(sessions, "refresh_session_content_from_documents", fail)
    with pytest.raises(RuntimeError, match="refresh failed"):
        sessions.get_session(session_id)
    assert documents.get_document(session_id, "prd") is None


def test_job_replay_does_not_append_or_restore_stale_current(session_id):
    documents.sync_from_job(session_id, "prd", "job one", source_job_id="one")
    first = documents.get_current_version(session_id, "prd")
    documents.sync_from_job(session_id, "prd", "job two", source_job_id="two")
    latest = documents.get_current_version(session_id, "prd")
    count = len(documents.list_versions(session_id, "prd")["versions"])
    documents.sync_from_job(session_id, "prd", "stale replay", source_job_id="one")
    assert documents.get_current_version(session_id, "prd") == latest
    assert documents.get_version(session_id, "prd", first["id"])["content"] == "job one"
    assert len(documents.list_versions(session_id, "prd")["versions"]) == count


def test_failed_draft_never_overwrites_success(session_id):
    documents.sync_from_job(session_id, "prd", "success", source_job_id="success")
    success = documents.get_current_version(session_id, "prd")
    documents.sync_from_job(
        session_id, "optimize-prd", "broken draft", failed=True, source_job_id="failure"
    )
    assert documents.get_current_version(session_id, "prd") == success
    documents.sync_from_job(
        session_id, "prd", "failed replay", failed=True, source_job_id="success"
    )
    assert documents.get_current_version(session_id, "prd") == success


@pytest.mark.parametrize("artifact", ["prd", "optimize-prd"])
def test_failed_session_sync_preserves_success_and_clears_active_job(session_id, artifact):
    documents.sync_from_job(session_id, "prd", "success", source_job_id="success")
    original = documents.get_current_version(session_id, "prd")
    update = (
        sessions.sync_session_on_optimize_failed
        if artifact.startswith("optimize-")
        else sessions.sync_session_on_job_failed
    )
    update(session_id, artifact, "broken draft")
    assert sessions.load_session_data_raw(session_id)["prdContent"] == "success"
    assert sessions.load_session_data_raw(session_id)["activeJobId"] is None
    assert documents.get_current_version(session_id, "prd") == original


def test_failed_initial_draft_can_be_promoted_once(isolated_database):
    session_id = sessions.save_session({})["id"]
    documents.sync_from_job(session_id, "prd", "draft", failed=True, source_job_id="retry")
    documents.sync_from_job(session_id, "prd", "final", source_job_id="retry")
    current = documents.get_current_version(session_id, "prd")
    assert current["content"] == "final"
    assert current["metadata"].get("job_status") != "failed"
    documents.sync_from_job(session_id, "prd", "duplicate", source_job_id="retry")
    assert documents.get_current_version(session_id, "prd") == current
    assert len(documents.list_versions(session_id, "prd")["versions"]) == 1


def test_optimization_retains_job_identity_for_later_replay(session_id):
    documents.sync_from_job(session_id, "prd", "generated", source_job_id="generate")
    documents.sync_from_job(session_id, "optimize-prd", "optimized", source_job_id="optimize")
    latest = documents.get_current_version(session_id, "prd")
    documents.sync_from_job(session_id, "prd", "stale generation", source_job_id="generate")
    assert documents.get_current_version(session_id, "prd") == latest
    documents.sync_from_job(session_id, "prd", "new generation", source_job_id="new")
    latest = documents.get_current_version(session_id, "prd")
    documents.sync_from_job(
        session_id, "optimize-prd", "stale optimization", source_job_id="optimize"
    )
    assert documents.get_current_version(session_id, "prd") == latest


def test_concurrent_checkpoints_have_distinct_monotonic_versions(session_id, isolated_database):
    def write(index):
        with database_context(isolated_database):
            return documents.checkpoint(session_id, "prd", f"# Draft {index}")["version_no"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        numbers = list(pool.map(write, range(8)))
    assert sorted(numbers) == list(range(2, 10))
    current = documents.get_current_version(session_id, "prd")
    assert current["version_no"] == 9
    assert sessions.load_session_data_raw(session_id)["prdContent"] == current["content"]


def test_concurrent_same_job_completion_writes_once(session_id, isolated_database):
    def complete(index):
        with database_context(isolated_database):
            documents.sync_from_job(session_id, "prd", "completed", source_job_id="same-job")

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(complete, range(8)))
    current = documents.get_current_version(session_id, "prd")
    assert current["content"] == "completed"
    assert current["source_job_id"] == "same-job"
    assert len(documents.list_versions(session_id, "prd")["versions"]) == 1


@pytest.mark.parametrize("failed", [True, False])
def test_session_finalization_preserves_newer_other_document(session_id, failed):
    data = sessions.load_session_data_raw(session_id)
    data["apiDocsContent"] = "old api"
    sessions.save_session(data, session_id)
    documents.sync_from_job(session_id, "api-docs", "new api", source_job_id="api")
    latest_api = documents.get_current_version(session_id, "api-docs")
    update = (
        sessions.sync_session_on_job_failed if failed else sessions.sync_session_on_job_complete
    )
    update(session_id, "prd", "new prd")
    assert documents.get_current_version(session_id, "api-docs") == latest_api
    assert sessions.load_session_data_raw(session_id)["apiDocsContent"] == "new api"


def test_missing_resources_raise_transport_independent_errors(isolated_database):
    with pytest.raises(KeyError) as error:
        sessions.get_session("missing")
    assert isinstance(error.value, DomainError)
    assert error.value.code == "SESSION_NOT_FOUND"
    assert error.value.status_code == 404
    with pytest.raises(documents.SessionNotFoundError):
        documents.checkpoint("missing", "prd", "# Draft")


def test_empty_checkpoint_does_not_leave_document_slot(isolated_database):
    session_id = sessions.save_session({})["id"]
    with pytest.raises(documents.CheckpointError):
        documents.checkpoint(session_id, "prd", "   ")
    assert documents.get_document(session_id, "prd") is None


@pytest.mark.parametrize("status", ["pending", "queued", "running", "interrupted"])
def test_session_view_preserves_active_generation(session_id, status):
    _insert_job(session_id, status)
    sessions.sync_session_active_job(session_id, "job", "prd")
    assert sessions.get_session(session_id)["session_data"]["viewState"] == "generating-prd"


@pytest.mark.parametrize("status", ["pending", "queued", "running", "interrupted"])
def test_delete_rejects_active_job_without_partial_deletes(session_id, status):
    _insert_job(session_id, status)
    before = documents.list_versions(session_id, "prd")
    with pytest.raises(DomainError) as error:
        sessions.delete_session(session_id)
    assert error.value.code == "JOB_CONFLICT"
    assert error.value.status_code == 409
    assert sessions.load_session_data_raw(session_id)["prdContent"] == "# Original"
    assert documents.list_versions(session_id, "prd") == before
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM generation_jobs").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM job_events").fetchone()[0] == 1


def _insert_job(session_id, status):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO generation_jobs
            (id,session_id,artifact,status,phase,payload_json,created_at,updated_at,conflict_key)
            VALUES ('job',?,'prd',?,'test','{}','now','now','prd')""",
            (session_id, status),
        )
        conn.execute("INSERT INTO job_events VALUES ('job',1,'test','{}','now')")


def test_delete_removes_only_session_owned_rows(session_id, isolated_database):
    other = sessions.save_session({"prdContent": "# Other"})["id"]
    _insert_job(session_id, "succeeded")
    sessions.delete_session(session_id)
    with get_connection() as conn:
        for table in ("job_events", "generation_jobs"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
    assert sessions.get_session(other)["session_data"]["prdContent"] == "# Other"
    with pytest.raises(KeyError):
        sessions.get_session(session_id)


def test_delete_rollback_restores_all_related_rows(session_id):
    _insert_job(session_id, "failed")
    with pytest.raises(RuntimeError, match="abort"):
        with transaction():
            sessions.delete_session(session_id)
            raise RuntimeError("abort")
    assert sessions.get_session(session_id)["session_data"]["prdContent"] == "# Original"
    with get_connection() as conn:
        for table in ("job_events", "generation_jobs", "documents", "document_versions"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 1
