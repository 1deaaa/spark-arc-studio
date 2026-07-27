# network_probe.ps1 - 通用网络环境探测与镜像选择组件
#
# 设计目标：
#   1. 镜像候选与仓库身份统一读取根目录 sparkarc.json，可被 pyloader.ps1、start.bat 或其他 PowerShell 脚本复用。
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
Add-Type -AssemblyName System.Net.Http -ErrorAction Stop

$CacheSchemaVersion = 2
$CacheTtlSeconds = 300
$ProbeTimeoutSec = 3

# 公益 IP 归属地 API（按优先级排列）
# freeipapi.com：完全免费、无需 Key、返回 countryCode/countryName，额度较宽松。
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SparkArcConfigPath = Join-Path $ProjectRoot "sparkarc.json"

function Get-SparkArcConfig {
    if (-not (Test-Path $SparkArcConfigPath)) {
        throw "未找到跨语言项目常量文件: $SparkArcConfigPath"
    }
    try {
        $config = Get-Content -Path $SparkArcConfigPath -Raw | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "无法解析 ${SparkArcConfigPath}: $($_.Exception.Message)"
    }
    if ($config.schemaVersion -ne 1 -or $config.repository.provider -ne "github" -or -not $config.repository.slug -or @($config.repository.mainlandCloneUrls).Count -lt 1 -or @($config.network.geoIpProviders).Count -lt 2) {
        throw "sparkarc.json 缺少有效的仓库身份或大陆克隆源。"
    }
    return $config
}

$SparkArcConfig = Get-SparkArcConfig
$GeoIpProviders = @($SparkArcConfig.network.geoIpProviders | ForEach-Object { [string]$_ })

# 镜像表：按区域归类，key 越小优先级越高（同一区域内）
$MirrorTable = @{}
foreach ($property in $SparkArcConfig.network.resources.PSObject.Properties) {
    $route = $property.Value
    $MirrorTable[$property.Name] = @{
        default = @($route.default | ForEach-Object { [string]$_ })
        mainland = @($route.mainland | ForEach-Object { [string]$_ })
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
        if ($cached.schemaVersion -ne $CacheSchemaVersion) { return $null }
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
    $clone | Add-Member -NotePropertyName "schemaVersion" -NotePropertyValue $CacheSchemaVersion -Force
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
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)
    $client.DefaultRequestHeaders.UserAgent.ParseAdd("SparkArc-NetworkProbe/1.0")
    try {
        $httpMethod = if ($Method -eq "HEAD") {
            [System.Net.Http.HttpMethod]::Head
        }
        else {
            [System.Net.Http.HttpMethod]::Get
        }
        $request = [System.Net.Http.HttpRequestMessage]::new($httpMethod, $Url)
        try {
            $response = $client.SendAsync(
                $request,
                [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead
            ).GetAwaiter().GetResult()
            try {
                $statusCode = [int]$response.StatusCode
                if ($statusCode -ge 200 -and $statusCode -lt 400) { return $true }
                $shouldRetryWithGet = $Method -eq "HEAD" -and $statusCode -in @(403, 405, 501)
            }
            finally {
                $response.Dispose()
            }
        }
        finally {
            $request.Dispose()
        }

        # 仅在服务端明确拒绝 HEAD 时回退 GET，仍只读取响应头。
        if ($shouldRetryWithGet) {
            $response = $client.GetAsync(
                $Url,
                [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead
            ).GetAwaiter().GetResult()
            try {
                $statusCode = [int]$response.StatusCode
                return ($statusCode -ge 200 -and $statusCode -lt 400)
            }
            finally {
                $response.Dispose()
            }
        }
        return $false
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

function Invoke-DirectJsonRequest {
    <#
    .SYNOPSIS
        绕过 HTTP(S)_PROXY 请求 JSON，避免本地代理出口污染属地判断。
    #>
    param([Parameter(Mandatory = $true)][string]$Url)

    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.UseProxy = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(5)
    try {
        $response = $client.GetAsync($Url).GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) { return $null }
        $content = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        return $content | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        return $null
    }
    finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

function Invoke-GeoIpLookup {
    <#
    .SYNOPSIS
        用至少两个无代理 GeoIP 源的一致结果确认出口国家。
    #>
    $votes = @()
    foreach ($provider in $GeoIpProviders) {
        $data = Invoke-DirectJsonRequest -Url $provider
        if (-not $data) { continue }

        # 不同 API 的字段名略有差异，做兼容。
        $countryCode = if ($data.countryCode) { $data.countryCode } elseif ($data.country_code) { $data.country_code } elseif ($data.country) { $data.country } else { "" }
        $countryName = if ($data.countryName) { $data.countryName } elseif ($data.country_name) { $data.country_name } elseif ($data.country) { $data.country } else { "" }
        $countryCode = ($countryCode -as [string]).Trim().ToUpper()
        if ($countryCode.Length -ne 2) { continue }
        $votes += [pscustomobject]@{
            Provider    = $provider
            CountryCode = $countryCode
            CountryName = ($countryName -as [string]).Trim()
        }
    }

    if ($votes.Count -eq 0) { return $null }
    $groups = @($votes | Group-Object -Property CountryCode | Sort-Object -Property Count -Descending)
    $winner = $groups | Select-Object -First 1
    $isTied = $groups.Count -gt 1 -and $groups[1].Count -eq $winner.Count
    if ($winner.Count -lt 2 -or $isTied) { return $null }

    $firstVote = $winner.Group | Select-Object -First 1
    return [pscustomobject]@{
        Provider    = @($winner.Group | ForEach-Object { $_.Provider }) -join ", "
        CountryCode = $winner.Name
        CountryName = $firstVote.CountryName
        Confidence  = "direct_consensus"
    }
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
            Confidence        = if ($cached.confidence) { $cached.confidence } else { "unknown" }
        }
    }

    $geo = Invoke-GeoIpLookup
    if (-not $geo) {
        return [pscustomobject]@{
            CountryCode       = "UNKNOWN"
            CountryName       = "Unknown"
            IsMainlandChina   = $null
            Source            = "fallback"
            Confidence        = "unknown"
        }
    }

    $isCn = ($geo.CountryCode -eq "CN")
    $result = [pscustomobject]@{
        CountryCode       = $geo.CountryCode
        CountryName       = $geo.CountryName
        IsMainlandChina   = $isCn
        Source            = $geo.Provider
        Confidence        = $geo.Confidence
    }

    # 写缓存（只写稳定字段）
    Write-NetworkProbeCache -Payload ([pscustomobject]@{
        countryCode     = $result.CountryCode
        countryName     = $result.CountryName
        isMainlandChina = $result.IsMainlandChina
        confidence      = $result.Confidence
    })

    return $result
}

function Get-GitCloneCandidates {
    <#
    .SYNOPSIS
        从 sparkarc.json 派生仓库克隆地址；中国大陆优先公开 Gitee 镜像。
    #>
    param([bool]$Probe = $true)

    $repositoryUrl = "https://github.com/$($SparkArcConfig.repository.slug).git"
    $region = Get-NetworkRegion
    $mainlandCandidates = @($SparkArcConfig.repository.mainlandCloneUrls)
    $candidates = if ($region.IsMainlandChina) {
        $mainlandCandidates + @($repositoryUrl)
    }
    else {
        @($repositoryUrl) + $mainlandCandidates
    }
    $ordered = @($candidates | Select-Object -Unique)
    return [pscustomobject]@{
        Primary = $ordered | Select-Object -First 1
        Candidates = $ordered
        CountryCode = $region.CountryCode
    }
}

function Get-RecommendedMirror {
    <#
    .SYNOPSIS
        根据网络归属地返回某类下载资源的推荐镜像 URL。
    .PARAMETER Type
        资源类型：由 sparkarc.json 的 network.resources 声明。
    .PARAMETER Probe
        是否探测可达性并按可达性排序（默认 true）。
    #>
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("pypi", "github_release", "huggingface", "gh_proxy", "python_standalone", "node_distribution", "npm_registry")]
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
    $mirrors["git_clone"] = (Get-GitCloneCandidates -Probe $true).Primary

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
        "git_clone"       { (Get-GitCloneCandidates).Primary }
        "country"         { (Get-NetworkRegion).CountryCode }
        default           { Invoke-NetworkProbe | ConvertTo-Json -Depth 4 }
    }
}
