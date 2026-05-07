#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# 国内 pip 镜像（清华）
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple/"
# 国内 npm 镜像（淘宝）
NPM_MIRROR="https://registry.npmmirror.com"

echo "🚀 启动 HarnessPRD..."
echo ""

# 检查 Python
if ! command -v python3 &>/dev/null; then
  echo "❌ 未找到 Python3，请先安装 Python 3.8+"
  exit 1
fi

# 检查 Node.js
if ! command -v node &>/dev/null; then
  echo "❌ 未找到 Node.js，请先安装 Node.js 18+"
  exit 1
fi

# 检查 .env 文件
if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "⚠️  未找到 backend/.env，从 .env.example 创建..."
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo "📝 请编辑 backend/.env 填入你的 API Key，然后重新运行此脚本"
  echo "   文件路径: $BACKEND_DIR/.env"
  open "$BACKEND_DIR/.env" 2>/dev/null || true
  exit 0
fi

# 创建或复用 venv，安装后端依赖
VENV_DIR="$BACKEND_DIR/.venv"
echo "📦 安装后端依赖（使用清华镜像）..."
cd "$BACKEND_DIR"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip -q -i "$PIP_MIRROR"
"$VENV_DIR/bin/pip" install -r requirements.txt -q -i "$PIP_MIRROR"

# 启动后端
echo "✅ 启动后端 (http://localhost:8000)..."
cd "$BACKEND_DIR"
"$VENV_DIR/bin/python" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 安装前端依赖（使用国内镜像）
echo "📦 安装前端依赖（使用淘宝镜像）..."
cd "$FRONTEND_DIR"
npm install --silent --registry "$NPM_MIRROR"

# 启动前端
echo "✅ 启动前端 (http://localhost:5173)..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "═══════════════════════════════════════"
echo "  🌐 访问地址：http://localhost:5173"
echo "  📡 API 文档：http://localhost:8000/docs"
echo "═══════════════════════════════════════"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获退出信号
cleanup() {
  echo ""
  echo "🛑 正在停止服务..."
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

wait
