# SparkArc 前端构建兼容入口。
# 实际逻辑统一由 Node 脚本维护，避免 Windows 与 Unix 各自维护一套依赖状态机。

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "build-frontend.mjs"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[frontend] 未检测到 Node.js。请通过 Launcher 受管部署，或先安装 Node.js 20+。" -ForegroundColor Red
    exit 1
}

& node $scriptPath
exit $LASTEXITCODE
