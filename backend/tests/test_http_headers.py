"""HTTP 响应头辅助测试"""

import sys
from pathlib import Path

from fastapi.responses import Response

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from apps.services.http_headers import build_attachment_content_disposition  # noqa: E402


def test_ascii_filename_uses_simple_disposition():
    header = build_attachment_content_disposition("product-delivery.zip")
    assert header == 'attachment; filename="product-delivery.zip"'


def test_unicode_filename_uses_rfc5987_and_ascii_fallback():
    header = build_attachment_content_disposition("内部审批流-delivery.zip")
    assert 'filename="delivery.zip"' in header
    assert "filename*=UTF-8''" in header
    assert "%E5%86%85%E9%83%A8" in header


def test_unicode_filename_header_is_latin1_safe():
    header = build_attachment_content_disposition("内部审批流-delivery.zip")
    Response(
        content=b"zip",
        media_type="application/zip",
        headers={"Content-Disposition": header},
    )
