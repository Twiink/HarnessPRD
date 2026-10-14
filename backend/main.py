"""兼容现有 uvicorn main:app 命令；正式入口为 apps.main。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from apps.main import app, create_app  # noqa: E402

if __name__ == "__main__":
    import uvicorn
    from apps.core.config import get_settings

    config = get_settings()
    uvicorn.run(app, host=config.host, port=config.port)
