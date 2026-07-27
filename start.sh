:
#!/usr/bin/env bash
# start.sh - SparkArc 一键启动脚本（Linux / macOS 桌面端）
#
# 功能：
#   1. 调用 server/pyloader.unix.sh 部署 Python 环境
#   2. 启动 SparkArc 后端服务
#
# 注意：网络探测与镜像选择已下沉到 pyloader.unix.sh，本脚本不再处理。

set -e

cd "$(dirname "$0")"

SERVER_DIR="$(pwd)/server"
PYTHON_ENV="$SERVER_DIR/.runtime/python"
MARKER_FILE="$PYTHON_ENV/.deploy_complete"
PYTHON_EXE="$PYTHON_ENV/bin/python3"
CLIENT_DIR="$(pwd)/client"
CLIENT_BUILD_SCRIPT="$CLIENT_DIR/build-frontend.mjs"

echo "[launcher] Running environment deployment..."

# ===== 部署后端环境 =====
bash "$SERVER_DIR/pyloader.unix.sh"
if [ $? -ne 0 ]; then
    echo "[ERROR] Environment deployment failed."
    exit 1
fi

if [ ! -f "$MARKER_FILE" ]; then
    echo "[ERROR] Deployment script finished but marker file missing. Aborting."
    exit 1
fi

if [ ! -x "$PYTHON_EXE" ]; then
    echo "[ERROR] Python executable not found: $PYTHON_EXE"
    exit 1
fi

if [ ! -f "$CLIENT_BUILD_SCRIPT" ]; then
    echo "[ERROR] Frontend build script not found: $CLIENT_BUILD_SCRIPT"
    exit 1
fi

if ! command -v node >/dev/null 2>&1; then
    echo "[ERROR] Node.js was not found. Use Launcher managed deployment or install Node.js 20+."
    exit 1
fi

echo "[launcher] Building frontend..."
node "$CLIENT_BUILD_SCRIPT"

# ===== 启动后端 =====
echo "[launcher] Starting SparkArc backend..."
export WATCHFILES_IGNORE="**/*.db;**/alembic/versions/**"
export SPARKARC_SERVER_TRAY=1
export SPARKARC_SERVER_RELOAD=0
exec "$PYTHON_EXE" -X utf8 "$SERVER_DIR/app.py"
