"""历史元数据的兼容读取也必须在写锁存在时保持可读。"""

import json

from apps.db.repositories import documents as document_repository
from apps.services.documents.versions import get_current_version, get_version
from apps.services.sessions.state import save_session


def test_legacy_review_read_does_not_acquire_write_lock(isolated_database):
    sid = save_session({"prdContent": "# legacy", "prdReviewResult": {"passed": True}})["id"]
    current = get_current_version(sid, "prd")
    document_repository.update_metadata(current["id"], "{}")
    isolated_database.busy_timeout_ms = 10
    lock = isolated_database.connect()
    try:
        lock.execute("BEGIN IMMEDIATE")
        result = get_version(sid, "prd", current["id"])
        assert result["metadata"]["review"] == {"passed": True}
    finally:
        lock.rollback()
        lock.close()
    document = document_repository.get_document(sid, "prd")
    raw = document_repository.get_version(document["id"], current["id"])
    assert json.loads(raw["metadata_json"]) == {}
