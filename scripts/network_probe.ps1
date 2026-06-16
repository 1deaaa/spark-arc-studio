# network_probe.ps1 - 通用网络环境探测与镜像选择组件
#
# 设计目标：
#   1. 不依赖任何项目特有路径，可被 pyloader.ps1、start.bat 或其他 PowerShell 脚本复用。
#   2. 公益 IP 归属地 API，无 API Key、无明显频率限制。
#   3. 探测结果缓存到临时文件，避免每次调用都查 IP（缓存 5 分钟）。
#   4. 按国家/地区给出推荐镜像，并提供 URL 可达性探测函数。
#
# 用法：
#   # 直接执行并输出 JSON
#   pwsh -File scripts/network_probe.ps1
#
#   # 点源导入后调用函数
#   . "scripts/network_probe.ps1"
#   $region = Get-NetworkRegion
#   $mirror = Get-RecommendedMirror -Type "pypi"
#   if (Test-EndpointReachable $mirror) { ... }
#
# 返回对象示例：
#   {
#     "countryCode": "CN",
#     "countryName": "China",
#     "isMainlandChina": true,
#     "mirrors": {
#       "pypi":      "https://mirrors.aliyun.com/pypi/simple/",
#       "github":    "https://mirrors.ustc.edu.cn/github-release/",
#       "huggingface": "https://hf-mirror.com",
#       "ghProxy":   "https://gh-proxy.com/"
#     }
#   }

param(
    [ValidateSet("json", "pypi", "github_release", "huggingface", "gh_proxy", "python_standalone", "git_clone", "country")]
    [string]$Output = "json"
)

$ErrorActionPreference = "Stop"

# ===== 配置区 =====
$CacheTtlSeconds = 300
$ProbeTimeoutSec = 3

# 公益 IP 归属地 API（按优先级排列）
# freeipapi.com：完全免费、无需 Key、返回 countryCode/countryName，额度较宽松。
$GeoIpProviders = @(
    "https://freeipapi.com/api/json/"
    "https://ipapi.co/json/"
    "https://ipwho.is/json/"
)

# 镜像表：按区域归类，key 越小优先级越高（同一区域内）
$MirrorTable = @{
    pypi = @{
        default  = "https://pypi.org/simple/"
        mainland = @(
            "https://mirrors.aliyun.com/pypi/simple/"
            "https://pypi.tuna.tsinghua.edu.cn/simple/"
            "https://mirrors.ustc.edu.cn/pypi/web/simple/"
        )
    }
    github_release = @{
        default  = "https://github.com/"
        mainland = @(
            "https://mirrors.ustc.edu.cn/github-release/"
            "https://gh-proxy.com/"
        )
    }
    huggingface = @{
        default  = "https://huggingface.co"
        mainland = @(
            "https://hf-mirror.com"
        )
    }
    gh_proxy = @{
        default  = "https://gh-proxy.com/"
        mainland = @("https://gh-proxy.com/")
    }
    git_clone = @{
        # 默认仓库：SparkArc 主仓库；中国大陆通过 gh-proxy 代理 HTTPS clone
        default  = "https://github.com/1deaaa/sparkarc.git"
        mainland = @("https://gh-proxy.com/https://github.com/1deaaa/sparkarc.git")
    }
    python_standalone = @{
        # 专为 pyloader 准备的完整 LatestRelease 索引页 URL
        default  = ""
        mainland = @(
            "https://mirrors.ustc.edu.cn/github-release/astral-sh/python-build-standalone/LatestRelease/"
        )
    }
}

# ===== 路径与缓存 =====
function Get-NetworkProbeCacheDir {
    $base = $env:TEMP
    if (-not $base) { $base = [System.IO.Path]::GetTempPath() }
    return Join-Path $base "sparkarc_network_probe"
}

function Get-NetworkProbeCacheFile {
    return Join-Path (Get-NetworkProbeCacheDir) "region.json"
}

function Read-NetworkProbeCache {
    $cacheFile = Get-NetworkProbeCacheFile
    if (-not (Test-Path $cacheFile)) { return $null }
    try {
        $raw = Get-Content $cacheFile -Raw -ErrorAction Stop
        $cached = $raw | ConvertFrom-Json -ErrorAction Stop
        $ts = [datetime]$cached.timestamp
        if (([datetime]::UtcNow - $ts).TotalSeconds -gt $CacheTtlSeconds) { return $null }
        return $cached
    }
    catch {
        return $null
    }
}

function Write-NetworkProbeCache {
    param([Parameter(Mandatory = $true)][object]$Payload)
    $dir = Get-NetworkProbeCacheDir
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    $clone = $Payload | ConvertTo-Json -Depth 4 | ConvertFrom-Json
    $clone | Add-Member -NotePropertyName "timestamp" -NotePropertyValue ([datetime]::UtcNow.ToString("O")) -Force
    $clone | ConvertTo-Json -Depth 4 | Set-Content -Path (Get-NetworkProbeCacheFile) -Encoding UTF8
}

# ===== 网络探测 =====
function Test-EndpointReachable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [int]$TimeoutSec = $ProbeTimeoutSec,
        [string]$Method = "HEAD"
    )
    try {
        $req = Invoke-WebRequest -Uri $Url -Method $Method -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop
        return ($req.StatusCode -ge 200 -and $req.StatusCode -lt 400)
    }
    catch {
        # 某些镜像对 HEAD 不友好，回退 GET 只读响应头
        if ($Method -eq "HEAD") {
            try {
                $req = Invoke-WebRequest -Uri $Url -Method "GET" -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop
                return ($req.StatusCode -ge 200 -and $req.StatusCode -lt 400)
            }
            catch {
                return $false
            }
        }
        return $false
    }
}

function Invoke-GeoIpLookup {
    foreach ($provider in $GeoIpProviders) {
        try {
            $resp = Invoke-WebRequest -Uri $provider -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            $data = ($resp.Content | ConvertFrom-Json -ErrorAction Stop)

            # 不同 API 的字段名略有差异，做兼容
            $countryCode = if ($data.countryCode) { $data.countryCode } elseif ($data.country_code) { $data.country_code } elseif ($data.country) { $data.country } else { "" }
            $countryName = if ($data.countryName) { $data.countryName } elseif ($data.country_name) { $data.country_name } elseif ($data.country) { $data.country } else { "" }

            $countryCode = ($countryCode -as [string]).Trim().ToUpper()
            if ($countryCode -and $countryCode.Length -ge 2) {
                return [pscustomobject]@{
                    Provider    = $provider
                    CountryCode = $countryCode
                    CountryName = ($countryName -as [string]).Trim()
                }
            }
        }
        catch {
            continue
        }
    }
    return $null
}

function Get-NetworkRegion {
    <#
    .SYNOPSIS
        获取当前网络出口的 IP 归属国家代码。
    .OUTPUTS
        pscustomobject，包含 CountryCode、CountryName、IsMainlandChina。
    #>
    $cached = Read-NetworkProbeCache
    if ($cached -and $cached.countryCode) {
        return [pscustomobject]@{
            CountryCode       = $cached.countryCode
            CountryName       = $cached.countryName
            IsMainlandChina   = [bool]$cached.isMainlandChina
            Source            = "cache"
        }
    }

    $geo = Invoke-GeoIpLookup
    if (-not $geo) {
        return [pscustomobject]@{
            CountryCode       = "UNKNOWN"
            CountryName       = "Unknown"
            IsMainlandChina   = $false
            Source            = "fallback"
        }
    }

    $isCn = ($geo.CountryCode -eq "CN")
    $result = [pscustomobject]@{
        CountryCode       = $geo.CountryCode
        CountryName       = $geo.CountryName
        IsMainlandChina   = $isCn
        Source            = $geo.Provider
    }

    # 写缓存（只写稳定字段）
    Write-NetworkProbeCache -Payload ([pscustomobject]@{
        countryCode     = $result.CountryCode
        countryName     = $result.CountryName
        isMainlandChina = $result.IsMainlandChina
    })

    return $result
}

function Get-RecommendedMirror {
    <#
    .SYNOPSIS
        根据网络归属地返回某类下载资源的推荐镜像 URL。
    .PARAMETER Type
        资源类型：pypi / github_release / huggingface / gh_proxy
    .PARAMETER Probe
        是否探测可达性并按可达性排序（默认 true）。
    #>
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("pypi", "github_release", "huggingface", "gh_proxy", "python_standalone", "git_clone")]
        [string]$Type,
        [bool]$Probe = $true
    )

    $region = Get-NetworkRegion
    $cfg = $MirrorTable[$Type]
    $rawCandidates = if ($region.IsMainlandChina) { $cfg.mainland + $cfg.default } else { @($cfg.default) + $cfg.mainland }
    $candidates = @($rawCandidates | Where-Object { $_ -is [string] -and $_.Trim().Length -gt 0 })

    if (-not $Probe) {
        return [pscustomobject]@{
            Type        = $Type
            Primary     = $candidates | Select-Object -First 1
            Candidates  = $candidates
            CountryCode = $region.CountryCode
        }
    }

    $reachable = @()
    $unreachable = @()
    foreach ($url in $candidates) {
        if (Test-EndpointReachable -Url $url -TimeoutSec $ProbeTimeoutSec) {
            $reachable += $url
        }
        else {
            $unreachable += $url
        }
    }

    $ordered = $reachable + $unreachable
    if ($ordered.Count -eq 0) { $ordered = $candidates }

    return [pscustomobject]@{
        Type        = $Type
        Primary     = $ordered | Select-Object -First 1
        Candidates  = $ordered
        Reachable   = $reachable
        CountryCode = $region.CountryCode
    }
}

function Invoke-NetworkProbe {
    <#
    .SYNOPSIS
        一次性探测网络环境并返回完整结果对象。
    #>
    $region = Get-NetworkRegion
    $mirrors = @{}
    foreach ($type in $MirrorTable.Keys) {
        $mirrors[$type] = (Get-RecommendedMirror -Type $type -Probe $true).Primary
    }

    return [pscustomobject]@{
        CountryCode       = $region.CountryCode
        CountryName       = $region.CountryName
        IsMainlandChina   = $region.IsMainlandChina
        Source            = $region.Source
        Mirrors           = $mirrors
        ProbeTimestamp    = [datetime]::UtcNow.ToString("O")
    }
}

# ===== 直接执行时输出 =====
if ($MyInvocation.InvocationName -ne '.') {
    switch ($Output) {
        "pypi"            { (Get-RecommendedMirror -Type "pypi").Primary }
        "github_release"  { (Get-RecommendedMirror -Type "github_release").Primary }
        "huggingface"     { (Get-RecommendedMirror -Type "huggingface").Primary }
        "gh_proxy"        { (Get-RecommendedMirror -Type "gh_proxy").Primary }
        "python_standalone" {
            $url = (Get-RecommendedMirror -Type "python_standalone").Primary
            if (-not $url) {
                Write-Error "当前网络环境下没有可用的 python-build-standalone 镜像索引页。" -ErrorAction Stop
            }
            $url
        }
        "git_clone"       { (Get-RecommendedMirror -Type "git_clone").Primary }
        "country"         { (Get-NetworkRegion).CountryCode }
        default           { Invoke-NetworkProbe | ConvertTo-Json -Depth 4 }
    }
}
