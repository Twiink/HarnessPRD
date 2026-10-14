"""Document/version persistence. Version policies and metadata stay in the service."""

from apps.db.connection import get_connection


def get_document(session_id: str, doc_type: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE session_id=? AND doc_type=?",
            (session_id, doc_type),
        ).fetchone()
        return dict(row) if row else None


def insert_document(row: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO documents
            (id,session_id,doc_type,current_version_id,created_at,updated_at)
            VALUES (:id,:session_id,:doc_type,:current_version_id,:created_at,:updated_at)""",
            row,
        )


def get_version(document_id: str, version_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM document_versions WHERE document_id=? AND id=?",
            (document_id, version_id),
        ).fetchone()
        return dict(row) if row else None


def list_versions(document_id: str) -> list[dict]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM document_versions WHERE document_id=? ORDER BY version_no DESC",
                (document_id,),
            ).fetchall()
        ]


def version_by_number(document_id: str, number: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM document_versions WHERE document_id=? AND version_no=?",
            (document_id, number),
        ).fetchone()
        return dict(row) if row else None


def version_by_job(document_id: str, job_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM document_versions WHERE document_id=? AND source_job_id=?",
            (document_id, job_id),
        ).fetchone()
        return dict(row) if row else None


def has_generated_version(document_id: str) -> bool:
    with get_connection() as conn:
        return (
            conn.execute(
                "SELECT 1 FROM document_versions WHERE document_id=? AND source_kind='generate' LIMIT 1",
                (document_id,),
            ).fetchone()
            is not None
        )


def next_version_number(document_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(version_no) FROM document_versions WHERE document_id=?",
            (document_id,),
        ).fetchone()
        return int(row[0] or 0) + 1


def insert_version(row: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO document_versions
            (id,document_id,version_no,content,source_kind,source_job_id,parent_version_id,
             metadata_json,created_at)
            VALUES (:id,:document_id,:version_no,:content,:source_kind,:source_job_id,
                    :parent_version_id,:metadata_json,:created_at)""",
            row,
        )


def update_version(
    version_id: str, content: str, source_kind: str, source_job_id: str | None, metadata_json: str
) -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE document_versions SET content=?,source_kind=?,
            source_job_id=COALESCE(?,source_job_id),metadata_json=? WHERE id=?""",
            (content, source_kind, source_job_id, metadata_json, version_id),
        )


def update_metadata(version_id: str, metadata_json: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE document_versions SET metadata_json=? WHERE id=?", (metadata_json, version_id)
        )


def set_current(document_id: str, version_id: str, now: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE documents SET current_version_id=?,updated_at=? WHERE id=?",
            (version_id, now, document_id),
        )
