# build-frontend.ps1 - 前端依赖安装与构建脚本
#
# 设计目标：
#   1. 与 start.bat 配合，可在后端部署的同时并行执行前端构建。
#   2. 复用 scripts/network_probe.ps1 自动判断网络区域并切换 npm registry。
#   3. 通过 marker 与 package-lock.json 哈希避免不必要的重复安装。
#   4. 不修改 pyloader，保持其为通用 Python 部署组件。
#
# 用法：
#   pwsh -File client/build-frontend.ps1
#
# 输出：
#   - 构建产物写入 client/dist/
#   - marker 文件写入 client/.frontend_build_complete

$ErrorActionPreference = "Stop"

# ===== 路径 =====
$RepoRoot       = Split-Path -Parent $PSScriptRoot
$ClientDir      = $PSScriptRoot
$NetworkProbe   = Join-Path $RepoRoot "scripts" "network_probe.ps1"
$DistDir        = Join-Path $ClientDir "dist"
$MarkerFile     = Join-Path $ClientDir ".frontend_build_complete"
$LockHashFile   = Join-Path $ClientDir ".package-lock.sha256"
$PackageLock    = Join-Path $ClientDir "package-lock.json"
$PackageJson    = Join-Path $ClientDir "package.json"

# ===== 载入网络探测组件 =====
if (Test-Path $NetworkProbe) {
    . $NetworkProbe
}
else {
    Write-Host "[WARN] 未找到网络探测组件 $NetworkProbe，将使用默认 npm registry。" -ForegroundColor Yellow
}

function Exit-WithError {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-LockFileHash {
    if (-not (Test-Path $PackageLock)) { return $null }
    try {
        return (Get-FileHash -Path $PackageLock -Algorithm SHA256).Hash
    }
    catch {
        return $null
    }
}

function Get-StoredLockHash {
    if (-not (Test-Path $LockHashFile)) { return $null }
    try {
        return (Get-Content $LockHashFile -Raw -ErrorAction Stop).Trim()
    }
    catch {
        return $null
    }
}

function Set-LockHash {
    param([string]$Hash)
    $Hash | Set-Content -Path $LockHashFile -Encoding UTF8 -NoNewline
}

function Test-NpmInstallNeeded {
    <#
    .SYNOPSIS
        判断是否需要重新执行 npm install。
        依据：node_modules 不存在、package-lock.json 不存在，或 package-lock.json 哈希变化。
    #>
    $currentHash = Get-LockFileHash
    $storedHash  = Get-StoredLockHash
    $nodeModules = Join-Path $ClientDir "node_modules"

    if (-not (Test-Path $nodeModules)) { return $true }
    if (-not $currentHash) { return $true }
    if ($currentHash -ne $storedHash) { return $true }
    return $false
}

function Test-FrontendBuildNeeded {
    <#
    .SYNOPSIS
        判断是否需要重新构建前端。
        依据：marker 不存在，或 marker 生成后源码目录、配置文件有更新。
        不依赖 Git，纯文件时间戳比较。
    #>
    if (-not (Test-Path $MarkerFile)) { return $true }
    if (Test-NpmInstallNeeded) { return $true }

    $markerTime = (Get-Item $MarkerFile).LastWriteTimeUtc
    $watchRoots = @(
        (Join-Path $ClientDir "package.json"),
        (Join-Path $ClientDir "package-lock.json"),
        (Join-Path $ClientDir "index.html"),
        (Join-Path $ClientDir "vite.config.ts"),
        (Join-Path $ClientDir "tsconfig.json"),
        (Join-Path $ClientDir "src"),
        (Join-Path $ClientDir "public")
    )

    foreach ($root in $watchRoots) {
        if (-not (Test-Path $root)) { continue }
        $item = Get-Item $root
        if ($item.PSIsContainer) {
            # 递归检查目录内文件，但跳过 node_modules、dist 和临时文件
            $newer = Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object {
                    $full = $_.FullName
                    # 跳过构建产物和依赖目录
                    if ($full -like "*\node_modules\*") { return $false }
                    if ($full -like "*\dist\*") { return $false }
                    if ($full -like "*\.tmp\*") { return $false }
                    # 跳过编辑器临时文件和系统文件
                    if ($_.Name -match '^\.(DS_Store|swp|swo|tmp|bak|cache)$') { return $false }
                    if ($_.Name -match '~$') { return $false }
                    # 跳过日志文件
                    if ($_.Extension -in '.log', '.tmp', '.bak', '.cache') { return $false }
                    return $_.LastWriteTimeUtc -gt $markerTime
                } |
                Select-Object -First 1
            if ($newer) {
                Write-Host "[frontend] 源文件变更：$($newer.FullName)" -ForegroundColor DarkGray
                return $true
            }
        }
        elseif ($item.LastWriteTimeUtc -gt $markerTime) {
            Write-Host "[frontend] 配置文件变更：$root" -ForegroundColor DarkGray
            return $true
        }
    }

    return $false
}

function Invoke-NpmInstall {
    $currentHash = Get-LockFileHash
    Write-Host "[frontend] 安装前端依赖..." -ForegroundColor Yellow
    $npmArgs = @("install")
    if (-not $currentHash) {
        # 没有 lock 文件时避免写入 package-lock
        $npmArgs += "--no-package-lock"
    }

    $p = Start-Process -FilePath "cmd" -ArgumentList (@("/c", "npm") + $npmArgs) -WorkingDirectory $ClientDir -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        Exit-WithError "npm install 失败，退出码 $($p.ExitCode)。"
    }

    Set-LockHash -Hash (Get-LockFileHash)
}

function Invoke-FrontendBuild {
    Write-Host "[frontend] 构建前端..." -ForegroundColor Yellow
    $p = Start-Process -FilePath "cmd" -ArgumentList @("/c", "npm", "run", "build") -WorkingDirectory $ClientDir -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        Exit-WithError "npm run build 失败，退出码 $($p.ExitCode)。"
    }
}

function Write-BuildMarker {
    $content = "Built: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Node $(node -v) | npm $(npm -v)"
    $content | Set-Content -Path $MarkerFile -Encoding UTF8
}

function Set-NpmRegistryByRegion {
    <#
    .SYNOPSIS
        根据网络归属地临时设置 npm registry，构建结束后不保留。
        仅修改当前进程环境变量；不写入 ~/.npmrc。
    #>
    try {
        $region = Get-NetworkRegion
        if ($region.IsMainlandChina) {
            $mirror = Get-RecommendedMirror -Type "pypi" -Probe $true
            # npm registry 优先使用淘宝镜像，回退到其他国内镜像
            $npmRegistry = if ($mirror.Primary -like "*aliyun*") { "https://registry.npmmirror.com" } else { "https://registry.npmmirror.com" }
            $env:NPM_CONFIG_REGISTRY = $npmRegistry
            Write-Host "[frontend] 检测到中国大陆网络，临时使用 npm registry: $npmRegistry" -ForegroundColor Cyan
        }
        else {
            Write-Host "[frontend] 检测到非中国大陆网络，使用默认 npm registry。" -ForegroundColor DarkGray
        }
    }
    catch {
        Write-Host "[frontend] 网络探测失败，使用默认 npm registry。" -ForegroundColor Yellow
    }
}

# ===== 日志 =====
$LogFile = Join-Path $ClientDir ".frontend_build.log"
Start-Transcript -Path $LogFile -Force | Out-Null

# ===== 主流程 =====
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SparkArc 前端构建脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (-not (Test-CommandAvailable "node")) {
    Exit-WithError "未检测到 Node.js。请先安装 Node.js（建议 LTS 版本）：https://nodejs.org/"
}
if (-not (Test-CommandAvailable "npm")) {
    Exit-WithError "未检测到 npm。请检查 Node.js 安装是否完整。"
}

Write-Host "[frontend] Node.js $(node -v) / npm $(npm -v)" -ForegroundColor DarkGray

if (-not (Test-Path $PackageJson)) {
    Exit-WithError "未找到 $PackageJson，请确认在正确的项目目录下执行。"
}

Set-NpmRegistryByRegion

$needsInstall = Test-NpmInstallNeeded
$needsBuild   = Test-FrontendBuildNeeded

if (-not $needsInstall -and -not $needsBuild) {
    Write-Host ""
    Write-Host "[frontend] 源码与依赖均未变更，无需重新构建。" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "[frontend] 构建产物已就绪：$DistDir" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Stop-Transcript | Out-Null
    exit 0
}

if ($needsInstall) {
    Invoke-NpmInstall
}
if ($needsBuild) {
    Invoke-FrontendBuild
}
Write-BuildMarker

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "[frontend] 构建完成：$DistDir" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

Stop-Transcript | Out-Null
