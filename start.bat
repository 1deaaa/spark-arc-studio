@echo off
setlocal

cd /d "%~dp0"

set "SERVER_DIR=%~dp0server"
set "PYTHON_ENV=%SERVER_DIR%\python_env"
set "MARKER=%PYTHON_ENV%\.deploy_complete"
set "PYTHON_EXE=%PYTHON_ENV%\python.exe"

echo [launcher] Running environment deployment...

REM Prefer PowerShell 7 (pwsh), fall back to Windows built-in PowerShell 5.1
set "PS_CMD=powershell"
where pwsh >nul 2>&1
if not errorlevel 1 set "PS_CMD=pwsh"

%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File "%SERVER_DIR%\pyloader.ps1"
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
