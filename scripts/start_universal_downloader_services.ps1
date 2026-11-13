param(
    [int]$DownloaderPort = 5678,
    [switch]$StartBridge,
    [int]$BridgePort = 8765
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
    $pythonw = (Get-Command python.exe -ErrorAction Stop).Source
}

function Get-ListeningPid([int]$Port) {
    $connection = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($connection) { return [int]$connection.OwningProcess }
    return $null
}

function Ensure-Service([string]$Name, [string]$Arguments, [int]$Port, [string]$LogName, [string]$ErrorLogName) {
    $existing = Get-ListeningPid $Port
    if ($existing) {
        return [pscustomobject]@{ name = $Name; port = $Port; pid = $existing; started = $false; healthy = $true }
    }

    $log = Join-Path $projectRoot $LogName
    $errorLog = Join-Path $projectRoot $ErrorLogName
    $process = Start-Process -FilePath $pythonw -ArgumentList $Arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $errorLog -PassThru
    $deadline = (Get-Date).AddSeconds(12)
    do {
        Start-Sleep -Milliseconds 250
        $listening = Get-ListeningPid $Port
    } while (-not $listening -and (Get-Date) -lt $deadline)

    if (-not $listening) {
        throw "$Name 未能监听 127.0.0.1:$Port；请查看 $errorLog"
    }
    return [pscustomobject]@{ name = $Name; port = $Port; pid = $listening; started = $true; healthy = $true }
}

$results = @()
$results += Ensure-Service "universal-downloader-web" "-m xhs_dl.web.app" $DownloaderPort "universal_downloader_web.log" "universal_downloader_web.err.log"
if ($StartBridge) {
    $results += Ensure-Service "collector-bridge" "collector_bridge_api.py --host 127.0.0.1 --port $BridgePort" $BridgePort "collector_bridge_runtime.log" "collector_bridge_runtime.err.log"
}

foreach ($result in $results) {
    try {
        $url = if ($result.name -eq "collector-bridge") { "http://127.0.0.1:$($result.port)/api/v1/status" } else { "http://127.0.0.1:$($result.port)/api/capabilities" }
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
        if ($response.StatusCode -ne 200) { throw "HTTP $($response.StatusCode)" }
    } catch {
        throw "$($result.name) 已监听但 HTTP 健康检查失败：$($_.Exception.Message)"
    }
}

$results | ConvertTo-Json -Compress
