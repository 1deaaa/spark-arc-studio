@echo off
setlocal
chcp 65001 >nul

rem Replace this value with your Gitee personal access token.
set "GITEE_TOKEN=PASTE_YOUR_GITEE_TOKEN_HERE"

rem Optional GitHub token for higher API rate limits.
set "GITHUB_TOKEN="

set "GITHUB_REPOSITORY=1deaaa/spark-arc-studio"
set "GITEE_REPOSITORY=aideaaa/spark-arc-studio"

pushd "%~dp0.."
where node >nul 2>&1
if errorlevel 1 (
  echo Node.js 20 or newer is required.
  popd
  exit /b 1
)

node "%~dp0sync-github-release-to-gitee.mjs"
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" (
  echo Release sync failed.
  exit /b %EXIT_CODE%
)
echo Release sync completed.
exit /b 0

