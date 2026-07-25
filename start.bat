@echo off
setlocal

cd /d "%~dp0"

set "SERVER_DIR=%~dp0server"
set "PYTHON_ENV=%SERVER_DIR%\.runtime\python"
set "MARKER=%PYTHON_ENV%\.deploy_complete"
set "PYTHON_EXE=%PYTHON_ENV%\python.exe"
set "CLIENT_DIR=%~dp0client"
set "CLIENT_BUILD_SCRIPT=%CLIENT_DIR%\build-frontend.mjs"

echo [launcher] Running environment deployment...

REM Prefer PowerShell 7 (pwsh), fall back to Windows built-in PowerShell 5.1
set "PS_CMD=powershell"
where pwsh >nul 2>&1
if not errorlevel 1 set "PS_CMD=pwsh"

%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File "%SERVER_DIR%\pyloader.win.ps1"
if errorlevel 1 (
    echo [ERROR] Environment deployment failed.
    pause
    exit /b 1
)

if not exist "%MARKER%" (
    echo [ERROR] Deployment script finished but marker file missing. Aborting.
    pause
    exit /b 1
)

REM 通过环境变量传递路径，避免用户目录包含单引号时破坏 Python 代码字符串。
set "SPARKARC_SERVICE_PROJECT_ROOT=%~dp0"
"%PYTHON_EXE%" -X utf8 -c "import os, sys; root = os.environ['SPARKARC_SERVICE_PROJECT_ROOT']; sys.path.insert(0, os.path.join(root, 'server')); from core.service_registry import record_service_install; record_service_install(root)"
if errorlevel 1 (
    echo [ERROR] Failed to register the local SparkArc service.
    pause
    exit /b 1
)

if not exist "%CLIENT_BUILD_SCRIPT%" (
    echo [ERROR] Frontend build script not found: %CLIENT_BUILD_SCRIPT%
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js was not found. Use Launcher managed deployment or install Node.js 20+.
    pause
    exit /b 1
)

echo [launcher] Building frontend...
node "%CLIENT_BUILD_SCRIPT%"
if errorlevel 1 (
    echo [ERROR] Frontend build failed.
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
if not defined SPARKARC_SERVER_TRAY set "SPARKARC_SERVER_TRAY=1"
if not defined SPARKARC_SERVER_RELOAD set "SPARKARC_SERVER_RELOAD=0"
"%PYTHON_EXE%" -X utf8 "%SERVER_DIR%\app.py"

endlocal
