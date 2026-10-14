#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

if ! command -v uv >/dev/null 2>&1; then
  printf '未找到 uv，请先安装 uv（https://docs.astral.sh/uv/）\n' >&2
  exit 1
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  printf '未找到 Node.js/npm，请先安装 Node.js 18+。\n' >&2
  exit 1
fi

if [ ! -f "$BACKEND_DIR/.env" ]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  printf '已创建 backend/.env，请填写 API Key 后重新启动。\n'
  exit 0
fi

printf '同步后端依赖...\n'
uv sync --project "$BACKEND_DIR"

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  printf '安装前端依赖...\n'
  npm --prefix "$FRONTEND_DIR" install
fi

"$SCRIPT_DIR/scripts/dev-backend.sh" &
BACKEND_PID=$!
"$SCRIPT_DIR/scripts/dev-frontend.sh" &
FRONTEND_PID=$!

cleanup() {
  printf '\n正在停止前后端服务...\n'
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

printf '\n前端：http://localhost:5174\nAPI 文档：http://localhost:8001/docs\n按 Ctrl+C 停止服务。\n'
wait "$BACKEND_PID" "$FRONTEND_PID"
