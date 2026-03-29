$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

$BackendLog = Join-Path $env:CLAUDE_CONSOLE_LOG_ROOT "claude-console-backend.log"
$RouterLog = Join-Path $env:CLAUDE_CONSOLE_LOG_ROOT "claude-code-router.log"
$ProxyLog = Join-Path $env:CLAUDE_CONSOLE_LOG_ROOT "claude-code-proxy.log"
$ConsoleUrl = "http://127.0.0.1:$($env:CLAUDE_CONSOLE_PORT)/claude-console"
$StatusUrl = "http://127.0.0.1:$($env:CLAUDE_CONSOLE_PORT)/claude-console/status"

function Test-Healthy($Url) {
    try {
        $Response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 300)
    } catch {
        return $false
    }
}

if (-not (Test-Healthy $env:CLAUDE_ROUTER_HEALTH_URL)) {
    Start-Process powershell -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File",(Join-Path $PSScriptRoot "start-claude-code-router.ps1")) -WindowStyle Hidden -RedirectStandardOutput $RouterLog -RedirectStandardError $RouterLog | Out-Null
    Start-Sleep -Seconds 1
}

if (-not (Test-Healthy $env:CLAUDE_PROXY_HEALTH_URL)) {
    Start-Process powershell -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File",(Join-Path $PSScriptRoot "start-claude-code-dashscope-proxy.ps1")) -WindowStyle Hidden -RedirectStandardOutput $ProxyLog -RedirectStandardError $ProxyLog | Out-Null
    Start-Sleep -Seconds 1
}

if (-not (Test-Healthy $StatusUrl)) {
    Start-Process powershell -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File",(Join-Path $PSScriptRoot "run-claude-console.ps1")) -WindowStyle Hidden -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendLog | Out-Null
}

for ($i = 0; $i -lt 20; $i++) {
    if (Test-Healthy $StatusUrl) {
        break
    }
    Start-Sleep -Seconds 1
}

Start-Process $ConsoleUrl
