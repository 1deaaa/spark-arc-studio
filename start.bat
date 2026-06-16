@echo off
setlocal

cd /d "%~dp0"

set "SERVER_DIR=%~dp0server"
set "PYTHON_ENV=%SERVER_DIR%\.runtime\python"
set "MARKER=%PYTHON_ENV%\.deploy_complete"
set "PYTHON_EXE=%PYTHON_ENV%\python.exe"
set "CLIENT_DIR=%~dp0client"
set "CLIENT_BUILD_SCRIPT=%CLIENT_DIR%\build-frontend.ps1"

echo [launcher] Running environment deployment...

REM Prefer PowerShell 7 (pwsh), fall back to Windows built-in PowerShell 5.1
set "PS_CMD=powershell"
where pwsh >nul 2>&1
if not errorlevel 1 set "PS_CMD=pwsh"

REM 并行启动前端构建（如果存在脚本）。最小化窗口、独立日志，不阻塞后端部署。
if exist "%CLIENT_BUILD_SCRIPT%" (
    echo [launcher] Starting frontend build in parallel...
    start /min "SparkArc Frontend Build" %PS_CMD% -NoProfile -ExecutionPolicy Bypass -File "%CLIENT_BUILD_SCRIPT%"
)

%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File "%SERVER_DIR%\pyloader.win.ps1"
if errorlevel 1 (
    echo [ERROR] Environment deployment failed.
    pause
    exit /b 1
)

REM 记录当前 SparkArc 项目根目录到用户目录，方便 launcher 后续定位
"%PYTHON_EXE%" -X utf8 -c "from core.service_registry import record_service_install; record_service_install(r'%~dp0')"

if not exist "%MARKER%" (
    echo [ERROR] Deployment script finished but marker file missing. Aborting.
    pause
    exit /b 1
)

:start_server
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python executable not found: %PYTHON_EXE%
    pause
    exit /b 1
)

echo [launcher] Starting SparkArc backend...
set "WATCHFILES_IGNORE=**/*.db;**/alembic/versions/**"
set "SPARKARC_SERVER_TRAY=1"
set "SPARKARC_SERVER_RELOAD=0"
"%PYTHON_EXE%" -X utf8 "%SERVER_DIR%\app.py"

endlocal
