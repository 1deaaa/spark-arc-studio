# pyloader.ps1 - Universal Portable Python Environment Deployer
# Uses python-build-standalone (github.com/astral-sh/python-build-standalone)
# for a truly portable Python with ZERO system impact:
#   - Full stdlib including tkinter, sqlite3, ssl, etc.
#   - ZERO registry entries
#   - ZERO PATH modification
#   - ZERO file association changes
#   - Just extract and use
#
# Deployment flow (generic for any Python project):
#   Step 1: Download python-build-standalone archive
#   Step 2: Extract to .runtime/python/ (pure .NET, no tar.exe needed)
#   Step 3: Run init_env.py if exists (project-specific optional hook)
#   Step 4: pip install -r requirements.txt if exists (standard packages)
#   Then write .deploy_complete marker. Does NOT launch the app.
#
# Minimum: Windows 10 1507 (PowerShell 5.0, .NET 4.6)
# Usage: Called from project-level BAT, or: pwsh -File pyloader.ps1

$ErrorActionPreference = "Stop"

# ===== PYTHON VERSION CONFIG =====
# 目标：稳定获取任意可用的 Python 3.x.x，而不是锁死某个小版本或发布标签。
$PythonMajorMinor = "3.13"
# ============================================================

# ===== PATHS =====
$BasePath      = $PSScriptRoot
$RuntimeRoot   = Join-Path $BasePath ".runtime"
$EnvDir        = Join-Path $RuntimeRoot "python"
$MarkerFile    = Join-Path $EnvDir ".deploy_complete"
$ReqHashFile   = Join-Path $EnvDir ".requirements.sha256"
$PythonExe     = Join-Path $EnvDir "python.exe"
$InitScript    = Join-Path $BasePath "init_env.py"
$ReqFile       = Join-Path $BasePath "requirements.txt"

# 允许调用方通过环境变量覆盖镜像；正常使用无需设置，脚本会自动探测网络区域。
$PipMirror         = if ($env:PYLOADER_PIP_MIRROR) { $env:PYLOADER_PIP_MIRROR } else { $null }
$PythonMirrorBase  = if ($env:PYLOADER_PYTHON_MIRROR_BASE) { $env:PYLOADER_PYTHON_MIRROR_BASE } else { $null }
$MirrorLatestUrl   = $null
$ArchiveName       = $null
$ArchiveLocal      = $null
$ResolvedPythonVersion = $null
$ResolvedReleaseTag    = $null
$NetworkProbeScript = Join-Path (Split-Path -Parent $BasePath) "scripts\network_probe.ps1"

# ===== FUNCTIONS =====
function Exit-WithError {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

function Resolve-Mirrors {
    if (-not (Test-Path $NetworkProbeScript)) {
        Exit-WithError "Network probe script not found: $NetworkProbeScript"
    }
    . $NetworkProbeScript

    $region = Get-NetworkRegion
    if (-not $PipMirror) {
        $script:PipMirror = (Get-RecommendedMirror -Type "pypi" -Probe $true).Primary
    }
    if (-not $PythonMirrorBase) {
        $script:PythonMirrorBase = (Get-RecommendedMirror -Type "python_standalone" -Probe $true).Primary.TrimEnd("/")
    }

    if ($env:PYLOADER_PIP_MIRROR -or $env:PYLOADER_PYTHON_MIRROR_BASE) {
        Write-Host "[mirror] Using caller-provided mirror overrides where supplied." -ForegroundColor Cyan
    }
    elseif ($region.IsMainlandChina) {
        Write-Host "[mirror] Detected mainland China network (CN), using configured domestic candidates." -ForegroundColor Cyan
    }
    else {
        Write-Host "[mirror] Network region: $($region.CountryCode), using configured default candidates." -ForegroundColor Cyan
    }

    $script:MirrorLatestUrl = "$PythonMirrorBase/github-release/astral-sh/python-build-standalone/LatestRelease/"
}

function Get-CurrentPythonVersion {
    if (-not (Test-Path $PythonExe)) {
        return $null
    }

    try {
        $version = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
        return ($version | Select-Object -First 1).Trim()
    }
    catch {
        return $null
    }
}

function Get-RequirementsHash {
    if (-not (Test-Path $ReqFile)) {
        return $null
    }

    $stream = $null
    $sha256 = $null
    try {
        $stream = [System.IO.File]::OpenRead($ReqFile)
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        return [System.BitConverter]::ToString($sha256.ComputeHash($stream)).Replace("-", "")
    }
    catch {
        return $null
    }
    finally {
        if ($sha256) { $sha256.Dispose() }
        if ($stream) { $stream.Dispose() }
    }
}

function Invoke-WebRequestWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,
        [int]$MaximumAttempts = 3,
        [int]$MaximumRedirection = 5
    )

    for ($attempt = 1; $attempt -le $MaximumAttempts; $attempt++) {
        try {
            return Invoke-WebRequest -Uri $Uri -UseBasicParsing -MaximumRedirection $MaximumRedirection
        }
        catch {
            if ($attempt -eq $MaximumAttempts) {
                throw
            }
            Write-Host "[network] Request failed, retrying ($attempt/$MaximumAttempts): $Uri" -ForegroundColor Yellow
            Start-Sleep -Seconds $attempt
        }
    }
}

function Resolve-PythonArchive {
    Write-Host "[scan] Querying latest standalone Python release..." -ForegroundColor Yellow

    $escaped = [regex]::Escape($PythonMajorMinor)

    if ($PythonMirrorBase -eq "https://github.com") {
        try {
            $latestUrl = "https://github.com/astral-sh/python-build-standalone/releases/latest"
            $latestResponse = Invoke-WebRequestWithRetry -Uri $latestUrl -MaximumRedirection 10
            $finalUri = $null
            if ($latestResponse.BaseResponse.ResponseUri) {
                $finalUri = [string]$latestResponse.BaseResponse.ResponseUri.AbsoluteUri
            }
            elseif ($latestResponse.BaseResponse.RequestMessage.RequestUri) {
                $finalUri = [string]$latestResponse.BaseResponse.RequestMessage.RequestUri.AbsoluteUri
            }

            $tagMatch = [regex]::Match($finalUri, "/releases/tag/([^/?#]+)")
            if (-not $tagMatch.Success) {
                throw "GitHub latest release redirect did not include a release tag"
            }

            $releaseTag = $tagMatch.Groups[1].Value
            $assetsUrl = "https://github.com/astral-sh/python-build-standalone/releases/expanded_assets/$releaseTag"
            $assetsResponse = Invoke-WebRequestWithRetry -Uri $assetsUrl
        }
        catch {
            Exit-WithError "Failed to query the official Python standalone release: $($_.Exception.Message)"
        }

        $assetPattern = "^/astral-sh/python-build-standalone/releases/download/([^/]+)/cpython-($escaped\.\d+)\+(\d+)-x86_64-pc-windows-msvc-install_only\.tar\.gz$"
        $candidates = @()
        foreach ($link in $assetsResponse.Links) {
            $href = [string]$link.href
            if ($href -match $assetPattern) {
                $candidates += [pscustomobject]@{
                    Href       = $href
                    Version    = $matches[2]
                    ReleaseTag = $matches[1]
                    BuildTag   = $matches[3]
                }
            }
        }

        if (-not $candidates) {
            Exit-WithError "The latest official release does not provide a matching Python $PythonMajorMinor.x standalone package."
        }

        $best = $candidates |
            Sort-Object -Property @{
                Expression = {
                    $parts = $_.Version.Split('.') | ForEach-Object { [int]$_ }
                    ($parts[0] * 1000000) + ($parts[1] * 1000) + $parts[2]
                }
            }, @{
                Expression = { [int64]$_.BuildTag }
            } -Descending |
            Select-Object -First 1

        $script:ResolvedPythonVersion = $best.Version
        $script:ResolvedReleaseTag = $best.ReleaseTag
        $script:ArchiveName = [System.IO.Path]::GetFileName($best.Href)
        $script:ArchiveLocal = Join-Path $RuntimeRoot $ArchiveName

        return [pscustomobject]@{
            Version     = $ResolvedPythonVersion
            ReleaseTag  = $ResolvedReleaseTag
            ArchiveName = $ArchiveName
            MirrorUrl   = "https://github.com$($best.Href)"
        }
    }

    try {
        $resp = Invoke-WebRequestWithRetry -Uri $MirrorLatestUrl
    }
    catch {
        Exit-WithError "Failed to query mirror index: $($_.Exception.Message)"
    }

    $pattern = "^/github-release/astral-sh/python-build-standalone/LatestRelease/cpython-($escaped\.\d+)%2B(\d+)-x86_64-pc-windows-msvc-install_only\.tar\.gz$"
    $candidates = @()

    foreach ($link in $resp.Links) {
        $href = [string]$link.href
        if ($href -match $pattern) {
            $candidates += [pscustomobject]@{
                Href       = $href
                Version    = $matches[1]
                ReleaseTag = $matches[2]
            }
        }
    }

    if (-not $candidates) {
        Exit-WithError "Mirror does not currently provide a matching Python $PythonMajorMinor.x standalone package."
    }

    $best = $candidates |
        Sort-Object -Property @{
            Expression = {
                $parts = $_.Version.Split('.') | ForEach-Object { [int]$_ }
                ($parts[0] * 1000000) + ($parts[1] * 1000) + $parts[2]
            }
        }, @{
            Expression = { [int64]$_.ReleaseTag }
        } -Descending |
        Select-Object -First 1

    $script:ResolvedPythonVersion = $best.Version
    $script:ResolvedReleaseTag = $best.ReleaseTag
    $script:ArchiveName = "cpython-$ResolvedPythonVersion+$ResolvedReleaseTag-x86_64-pc-windows-msvc-install_only.tar.gz"
    $script:ArchiveLocal = Join-Path $RuntimeRoot $ArchiveName

    # PythonMirrorBase 已根据网络区域自动选择：国内用 USTC 镜像，海外用 GitHub 官方
    $mirrorUrl = "$PythonMirrorBase$($best.Href)"

    return [pscustomobject]@{
        Version     = $ResolvedPythonVersion
        ReleaseTag  = $ResolvedReleaseTag
        ArchiveName = $ArchiveName
        MirrorUrl   = $mirrorUrl
    }
}

function Download-ResolvedArchive {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$ResolvedInfo
    )

    Write-Host "[1/4] Downloading Python $($ResolvedInfo.Version) standalone (~40MB)..." -ForegroundColor Yellow
    Write-Host "      Source: $($ResolvedInfo.MirrorUrl)" -ForegroundColor DarkGray

    try {
        $mirrorHost = ([uri]$ResolvedInfo.MirrorUrl).Host
        $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

        # USTC 大文件镜像会先返回 JavaScript 校验页，Cookie 值必须来自本次请求的实际出口 IP。
        if ($mirrorHost -eq "mirrors.ustc.edu.cn") {
            $verification = Invoke-WebRequest -Uri $ResolvedInfo.MirrorUrl -WebSession $session -UseBasicParsing
            $cookieMatch = [regex]::Match(
                [string]$verification.Content,
                'document\.cookie\s*=\s*"addr=([^;"]+)'
            )
            if (-not $cookieMatch.Success) {
                throw "USTC mirror verification page did not provide an address cookie"
            }
            $verificationAddress = $cookieMatch.Groups[1].Value
            [System.Net.IPAddress]$parsedAddress = $null
            if (-not [System.Net.IPAddress]::TryParse($verificationAddress, [ref]$parsedAddress)) {
                throw "USTC mirror returned an invalid verification address"
            }
            $session.Cookies.Add((New-Object System.Net.Cookie("addr", $verificationAddress, "/", $mirrorHost)))
        }

        Invoke-WebRequest -Uri $ResolvedInfo.MirrorUrl -WebSession $session -OutFile $ArchiveLocal -UseBasicParsing
        if ((Get-Item $ArchiveLocal).Length -lt 1MB) {
            throw "Downloaded file too small, likely an error page"
        }
        Write-Host "      Download complete." -ForegroundColor Green
    }
    catch {
        $failureReason = $_.Exception.Message
        if (Test-Path $ArchiveLocal) { Remove-Item $ArchiveLocal -Force }
        Exit-WithError ("Mirror download failed. Check your network.`n" +
            "Reason: $failureReason`n" +
            "You can also download manually and place it here:`n" +
            "  File: $ArchiveName`n" +
            "  URL:  $($ResolvedInfo.MirrorUrl)")
    }
}

# ===== PURE .NET TAR EXTRACTOR (no tar.exe dependency) =====
# Compiled once per process via Add-Type; works on any Windows with .NET 4.5+ (Win8+).
if (-not ([System.Management.Automation.PSTypeName]'SparkArc.TarExtractor').Type) {
    Add-Type -TypeDefinition @"
using System;
using System.IO;
using System.Text;

namespace SparkArc {
    public class TarExtractor {
        public static int Extract(string tarPath, string destDir) {
            int count = 0;
            using (var fs = File.OpenRead(tarPath)) {
                byte[] header = new byte[512];
                while (true) {
                    int read = ReadFull(fs, header, 512);
                    if (read < 512) break;

                    bool allZero = true;
                    for (int i = 0; i < 512; i++) { if (header[i] != 0) { allZero = false; break; } }
                    if (allZero) break;

                    StringBuilder sb = new StringBuilder(256);
                    for (int i = 0; i < 100 && header[i] != 0; i++) sb.Append((char)header[i]);
                    string name = sb.ToString();

                    long fileSize = 0;
                    if (header[124] == 0x80) {
                        for (int i = 125; i < 136; i++) fileSize = (fileSize << 8) | header[i];
                    } else {
                        sb.Clear();
                        for (int i = 124; i < 136 && header[i] != 0 && header[i] != 32; i++) sb.Append((char)header[i]);
                        string sizeStr = sb.ToString().Trim();
                        if (sizeStr.Length > 0) {
                            try { fileSize = Convert.ToInt64(sizeStr, 8); } catch { }
                        }
                    }

                    char typeFlag = (char)header[156];

                    if (header[257] == 0x75 && header[258] == 0x73 && header[259] == 0x74 &&
                        header[260] == 0x61 && header[261] == 0x72) {
                        sb.Clear();
                        for (int i = 345; i < 500 && header[i] != 0; i++) sb.Append((char)header[i]);
                        string prefix = sb.ToString().Trim();
                        if (prefix.Length > 0) name = prefix + "/" + name;
                    }

                    if (typeFlag == '5' || typeFlag == 'x' || typeFlag == 'g' || typeFlag == 'L' || typeFlag == '2') {
                        fs.Seek(((fileSize + 511) / 512) * 512, SeekOrigin.Current);
                        continue;
                    }

                    if (name.Length == 0 || name == "." || name == "./") {
                        fs.Seek(((fileSize + 511) / 512) * 512, SeekOrigin.Current);
                        continue;
                    }

                    name = name.Replace('\\', '/');
                    while (name.StartsWith("/")) name = name.Substring(1);
                    while (name.StartsWith("./")) name = name.Substring(2);
                    if (name.Length == 0) {
                        fs.Seek(((fileSize + 511) / 512) * 512, SeekOrigin.Current);
                        continue;
                    }

                    string destPath = Path.Combine(destDir, name.Replace('/', Path.DirectorySeparatorChar));
                    string parentDir = Path.GetDirectoryName(destPath);
                    if (!string.IsNullOrEmpty(parentDir) && !Directory.Exists(parentDir))
                        Directory.CreateDirectory(parentDir);

                    if (fileSize > 0) {
                        using (var outFs = File.Create(destPath)) {
                            long remaining = fileSize;
                            byte[] buf = new byte[65536];
                            while (remaining > 0) {
                                int toRead = (int)Math.Min(buf.Length, remaining);
                                int n = fs.Read(buf, 0, toRead);
                                if (n == 0) break;
                                outFs.Write(buf, 0, n);
                                remaining -= n;
                            }
                        }
                        count++;
                    }

                    long padding = ((fileSize + 511) / 512 * 512) - fileSize;
                    if (padding > 0) fs.Seek(padding, SeekOrigin.Current);
                }
            }
            return count;
        }

        private static int ReadFull(Stream s, byte[] buf, int count) {
            int offset = 0;
            while (offset < count) {
                int n = s.Read(buf, offset, count - offset);
                if (n == 0) break;
                offset += n;
            }
            return offset;
        }
    }
}
"@
}

# ---- 网络探测与镜像选择 ----
Resolve-Mirrors

# ---- Skip python deployment if already fully deployed ----
$CurrentVersion = Get-CurrentPythonVersion
$CurrentReqHash = Get-RequirementsHash
$StoredReqHash = $null

if (Test-Path $ReqHashFile) {
    try {
        $StoredReqHash = (Get-Content $ReqHashFile -ErrorAction Stop | Select-Object -First 1).Trim()
    }
    catch {
        $StoredReqHash = $null
    }
}

if (
    (Test-Path $MarkerFile) -and
    $CurrentVersion -and
    $CurrentVersion.StartsWith("$PythonMajorMinor.") -and
    (($null -eq $CurrentReqHash) -or ($CurrentReqHash -eq $StoredReqHash))
) {
    Write-Host "[pyloader] Already deployed with Python $CurrentVersion. Skipping python deployment." -ForegroundColor Green
    exit 0
}

if (Test-Path $MarkerFile) {
    if ($CurrentVersion -and $CurrentVersion.StartsWith("$PythonMajorMinor.") -and ($CurrentReqHash -ne $StoredReqHash)) {
        Write-Host "[pyloader] requirements.txt changed. Refreshing environment packages." -ForegroundColor Yellow
    }
    else {
        Write-Host "[pyloader] Deployment marker exists, but Python version is not $PythonMajorMinor.x. Rebuilding environment." -ForegroundColor Yellow
    }
}

$Resolved = Resolve-PythonArchive

Write-Host "========================================"
Write-Host "  Portable Python Deployer (standalone)"
Write-Host "  Python $($Resolved.Version) | Zero registry impact"
Write-Host "========================================"

# ---- Step 1-2: Ensure python-build-standalone archive and environment ----
$NeedsRebuild = (-not (Test-Path $PythonExe)) -or (-not $CurrentVersion) -or (-not $CurrentVersion.StartsWith("$PythonMajorMinor."))

if ($NeedsRebuild) {
    if (Test-Path $PythonExe) {
        Write-Host "[1-2/4] Existing .runtime/python is not Python $PythonMajorMinor.x. Rebuilding..." -ForegroundColor Yellow
        if (Test-Path $EnvDir) { Remove-Item $EnvDir -Recurse -Force }
        if (Test-Path $MarkerFile) { Remove-Item $MarkerFile -Force }
    }

    if (-not (Test-Path $RuntimeRoot)) { New-Item -ItemType Directory -Path $RuntimeRoot | Out-Null }

    if (-not (Test-Path $ArchiveLocal)) {
        Download-ResolvedArchive -ResolvedInfo $Resolved
    }
    else {
        Write-Host "[1/4] Found local archive: $ArchiveName" -ForegroundColor Green
    }

    Write-Host "[2/4] Extracting Python to .runtime/python/ ..." -ForegroundColor Yellow

    $TempExtractDir = Join-Path $BasePath "_python_extract_temp"
    if (Test-Path $TempExtractDir) { Remove-Item $TempExtractDir -Recurse -Force }
    New-Item -ItemType Directory -Path $TempExtractDir | Out-Null

    try {
        $tarTempFile = Join-Path $BasePath "_temp_python.tar"

        Write-Host "      Decompressing gzip..."
        $inStream  = $null
        $gzip      = $null
        $outStream = $null
        try {
            $inStream  = [System.IO.File]::OpenRead($ArchiveLocal)
            $gzip      = New-Object System.IO.Compression.GzipStream($inStream, [System.IO.Compression.CompressionMode]::Decompress)
            $outStream = [System.IO.File]::Create($tarTempFile)
            $gzip.CopyTo($outStream)
        }
        finally {
            if ($outStream) { try { $outStream.Dispose() } catch {} }
            if ($gzip)      { try { $gzip.Dispose() } catch {} }
            if ($inStream)  { try { $inStream.Dispose() } catch {} }
        }

        Write-Host "      Extracting tar..."
        $fileCount = [SparkArc.TarExtractor]::Extract($tarTempFile, $TempExtractDir)
        Write-Host "      Extracted $fileCount files."

        if (Test-Path $tarTempFile) { Remove-Item $tarTempFile -Force }
    }
    catch {
        if (Test-Path $tarTempFile)    { Remove-Item $tarTempFile -Force }
        if (Test-Path $TempExtractDir) { Remove-Item $TempExtractDir -Recurse -Force }
        Exit-WithError "Failed to extract archive: $($_.Exception.Message)"
    }

    $ExtractedPythonDir = Join-Path $TempExtractDir "python"
    if (-not (Test-Path (Join-Path $ExtractedPythonDir "python.exe"))) {
        if (Test-Path (Join-Path $TempExtractDir "python.exe")) {
            $ExtractedPythonDir = $TempExtractDir
        }
        else {
            if (Test-Path $TempExtractDir) { Remove-Item $TempExtractDir -Recurse -Force }
            Exit-WithError "Unexpected archive structure: python.exe not found after extraction."
        }
    }

    if (-not (Test-Path $RuntimeRoot)) { New-Item -ItemType Directory -Path $RuntimeRoot | Out-Null }
    if (Test-Path $EnvDir) { Remove-Item $EnvDir -Recurse -Force }
    Move-Item -Path $ExtractedPythonDir -Destination $EnvDir

    if (Test-Path $TempExtractDir) { Remove-Item $TempExtractDir -Recurse -Force }
    if (Test-Path $ArchiveLocal)   { Remove-Item $ArchiveLocal -Force }

    Write-Host "      Python extracted to .runtime/python/" -ForegroundColor Green
}
else {
    Write-Host "[1-2/4] Python $CurrentVersion already present in .runtime/python/" -ForegroundColor Green
}

# ***************---- Step 3: Run project-specific init script (if exists) ----****************
# This handles platform-dependent packages or project extras.
if (Test-Path $InitScript) {
    Write-Host "[3/4] Running init_env.py (project-specific setup)..." -ForegroundColor Yellow
    $p = Start-Process -FilePath $PythonExe -ArgumentList "-X utf8 `"$InitScript`"" -WorkingDirectory $BasePath -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        Exit-WithError "init_env.py failed with exit code $($p.ExitCode)."
    }
}
else {
    Write-Host "[3/4] No init_env.py found, skipping." -ForegroundColor DarkGray
}

# ---- Step 4: Install standard requirements.txt (if exists) ----
# This is the universal pip install step, works for ANY Python project.
if (Test-Path $ReqFile) {
    Write-Host "[4/4] Installing requirements.txt ..." -ForegroundColor Yellow
    $p = Start-Process -FilePath $PythonExe -ArgumentList "-X utf8 -m pip install --isolated --no-user -i $PipMirror -r `"$ReqFile`"" -WorkingDirectory $BasePath -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        Exit-WithError "pip install -r requirements.txt failed with exit code $($p.ExitCode)."
    }
}
else {
    Write-Host "[4/4] No requirements.txt found, skipping." -ForegroundColor DarkGray
}

# ---- Mark deployment as complete ----
$markerContent = "Deployed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Python $ResolvedPythonVersion (standalone, zero-registry) | Release $ResolvedReleaseTag"
$markerContent | Set-Content -Path $MarkerFile -Encoding UTF8

$FinalReqHash = Get-RequirementsHash
if ($FinalReqHash) {
    $FinalReqHash | Set-Content -Path $ReqHashFile -Encoding UTF8
}
elseif (Test-Path $ReqHashFile) {
    Remove-Item $ReqHashFile -Force
}

Write-Host ""
Write-Host "========================================"
Write-Host "[pyloader] Deployment complete!" -ForegroundColor Green
Write-Host "========================================"
exit 0
