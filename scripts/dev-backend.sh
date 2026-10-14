#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

if [[ ! -f "$BACKEND_DIR/.env" && -f "$BACKEND_DIR/.env.example" ]]; then
  printf '未找到 backend/.env，请先复制 backend/.env.example 并填写配置。\n' >&2
  exit 1
fi

exec uv run --project "$BACKEND_DIR" uvicorn --app-dir "$BACKEND_DIR/src" apps.main:app --reload --host "${HARNESSPRD_BACKEND_HOST:-127.0.0.1}" --port "${HARNESSPRD_BACKEND_PORT:-8001}"
