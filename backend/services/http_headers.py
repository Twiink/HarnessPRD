"""HTTP 响应头辅助。"""

from urllib.parse import quote


def build_attachment_content_disposition(filename: str) -> str:
    """构建 attachment Content-Disposition，兼容非 ASCII 文件名（RFC 5987）。"""
    try:
        filename.encode("ascii")
    except UnicodeEncodeError:
        fallback = "delivery.zip"
        if "." in filename:
            ext = filename.rsplit(".", 1)[-1]
            if ext.isascii() and ext.isalnum():
                fallback = f"delivery.{ext}"
        encoded = quote(filename, safe="")
        return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'
    return f'attachment; filename="{filename}"'
