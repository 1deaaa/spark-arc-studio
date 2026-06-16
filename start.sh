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
CLIENT_BUILD_SCRIPT="$CLIENT_DIR/build-frontend.ps1"

echo "[launcher] Running environment deployment..."

# ===== 并行启动前端构建（如果脚本存在）=====
if [ -f "$CLIENT_BUILD_SCRIPT" ] && command -v pwsh >/dev/null 2>&1; then
    echo "[launcher] Starting frontend build in parallel..."
    # 前端构建脚本自己写日志到 client/.frontend_build.log
    nohup pwsh -NoProfile -ExecutionPolicy Bypass -File "$CLIENT_BUILD_SCRIPT" >/dev/null 2>&1 &
elif [ -f "$CLIENT_BUILD_SCRIPT" ]; then
    echo "[launcher] PowerShell not found, skipping parallel frontend build."
fi

# ===== 部署后端环境 =====
bash "$SERVER_DIR/pyloader.unix.sh"
if [ $? -ne 0 ]; then
    echo "[ERROR] Environment deployment failed."
    exit 1
fi

# 记录当前 SparkArc 项目根目录到用户目录，方便 launcher 后续定位
"$PYTHON_EXE" -X utf8 -c "from core.service_registry import record_service_install; record_service_install('$(pwd)')"

if [ ! -f "$MARKER_FILE" ]; then
    echo "[ERROR] Deployment script finished but marker file missing. Aborting."
    exit 1
fi

if [ ! -x "$PYTHON_EXE" ]; then
    echo "[ERROR] Python executable not found: $PYTHON_EXE"
    exit 1
fi

# ===== 启动后端 =====
echo "[launcher] Starting SparkArc backend..."
export WATCHFILES_IGNORE="**/*.db;**/alembic/versions/**"
export SPARKARC_SERVER_TRAY=1
export SPARKARC_SERVER_RELOAD=0
exec "$PYTHON_EXE" -X utf8 "$SERVER_DIR/app.py"
