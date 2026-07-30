# network_probe.ps1 - Shared network region detection and mirror selection.
#
# Design goals:
#   1. Read mirror candidates and repository identity from sparkarc.json.
#   2. Use public GeoIP endpoints that do not require an API key.
#   3. Cache region detection for five minutes.
#   4. Select mirrors by region and provide endpoint reachability checks.
#
# Usage:
#   # Run directly and print JSON.
#   powershell.exe -File scripts/network_probe.ps1
#
#   # Dot-source and call functions.
#   . "scripts/network_probe.ps1"
#   $region = Get-NetworkRegion
#   $mirror = Get-RecommendedMirror -Type "pypi"
#   if (Test-EndpointReachable $mirror) { ... }
#
# Example result:
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

# ===== CONFIGURATION =====
Add-Type -AssemblyName System.Net.Http -ErrorAction Stop

$CacheSchemaVersion = 2
$CacheTtlSeconds = 300
$ProbeTimeoutSec = 3

# Public GeoIP endpoints are listed in priority order in sparkarc.json.
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SparkArcConfigPath = Join-Path $ProjectRoot "sparkarc.json"

function Get-SparkArcConfig {
    if (-not (Test-Path $SparkArcConfigPath)) {
        throw "Cross-language project configuration was not found: $SparkArcConfigPath"
    }
    try {
        $config = Get-Content -Path $SparkArcConfigPath -Raw | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Failed to parse ${SparkArcConfigPath}: $($_.Exception.Message)"
    }
    if ($config.schemaVersion -ne 1 -or $config.repository.provider -ne "github" -or -not $config.repository.slug -or $config.repository.mainlandRelease.provider -ne "gitee" -or -not $config.repository.mainlandRelease.slug -or @($config.repository.mainlandCloneUrls).Count -lt 1 -or @($config.network.geoIpProviders).Count -lt 2) {
        throw "sparkarc.json does not contain a valid repository identity and mainland clone source."
    }
    return $config
}

$SparkArcConfig = Get-SparkArcConfig
$GeoIpProviders = @($SparkArcConfig.network.geoIpProviders | ForEach-Object { [string]$_ })

# Build a region-aware mirror table from the shared configuration.
$MirrorTable = @{}
foreach ($property in $SparkArcConfig.network.resources.PSObject.Properties) {
    $route = $property.Value
    $MirrorTable[$property.Name] = @{
        default = @($route.default | ForEach-Object { [string]$_ })
        mainland = @($route.mainland | ForEach-Object { [string]$_ })
    }
}

# ===== PATHS AND CACHE =====
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

# ===== NETWORK DETECTION =====
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

        # Fall back to GET only when the server explicitly rejects HEAD.
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
        Request JSON without HTTP(S)_PROXY so a local proxy cannot alter region detection.
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
        Confirm the public network region using consistent results from GeoIP sources.
    #>
    $votes = @()
    foreach ($provider in $GeoIpProviders) {
        $data = Invoke-DirectJsonRequest -Url $provider
        if (-not $data) { continue }

        # Normalize the field names returned by different providers.
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
        Get the country code associated with the current public network address.
    .OUTPUTS
        A pscustomobject with CountryCode, CountryName, and IsMainlandChina.
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

    # Cache stable fields only.
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
        Build repository clone candidates from sparkarc.json.
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
        Return recommended mirror URLs for a resource type and network region.
    .PARAMETER Type
        Resource type declared by network.resources in sparkarc.json.
    .PARAMETER Probe
        Probe reachability and sort reachable candidates first. Defaults to true.
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
        Detect the network environment and return the complete result.
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

# ===== DIRECT EXECUTION OUTPUT =====
if ($MyInvocation.InvocationName -ne '.') {
    switch ($Output) {
        "pypi"            { (Get-RecommendedMirror -Type "pypi").Primary }
        "github_release"  { (Get-RecommendedMirror -Type "github_release").Primary }
        "huggingface"     { (Get-RecommendedMirror -Type "huggingface").Primary }
        "gh_proxy"        { (Get-RecommendedMirror -Type "gh_proxy").Primary }
        "python_standalone" {
            $url = (Get-RecommendedMirror -Type "python_standalone").Primary
            if (-not $url) {
                Write-Error "No python-build-standalone mirror index is configured for this network." -ErrorAction Stop
            }
            $url
        }
        "git_clone"       { (Get-GitCloneCandidates).Primary }
        "country"         { (Get-NetworkRegion).CountryCode }
        default           { Invoke-NetworkProbe | ConvertTo-Json -Depth 4 }
    }
}
