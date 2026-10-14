#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  printf '未找到前端依赖，请先运行：npm --prefix frontend install\n' >&2
  exit 1
fi

cd "$FRONTEND_DIR"
exec npm run dev -- --host 0.0.0.0
