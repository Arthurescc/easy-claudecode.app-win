param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

$BackendStdoutLog = Join-Path $env:CLAUDE_CONSOLE_LOG_ROOT "claude-console-backend.stdout.log"
$BackendStderrLog = Join-Path $env:CLAUDE_CONSOLE_LOG_ROOT "claude-console-backend.stderr.log"
$RouterStdoutLog = Join-Path $env:CLAUDE_CONSOLE_LOG_ROOT "claude-code-router.stdout.log"
$RouterStderrLog = Join-Path $env:CLAUDE_CONSOLE_LOG_ROOT "claude-code-router.stderr.log"
$ProxyStdoutLog = Join-Path $env:CLAUDE_CONSOLE_LOG_ROOT "claude-code-proxy.stdout.log"
$ProxyStderrLog = Join-Path $env:CLAUDE_CONSOLE_LOG_ROOT "claude-code-proxy.stderr.log"
$ConsoleUrl = "http://127.0.0.1:$($env:CLAUDE_CONSOLE_PORT)/claude-console"
$StatusUrl = "http://127.0.0.1:$($env:CLAUDE_CONSOLE_PORT)/claude-console/status"
$ShellBin = if ($env:EASY_POWERSHELL_BIN) { $env:EASY_POWERSHELL_BIN } else { "powershell" }

function Test-Healthy($Url) {
    try {
        $Response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 300)
    } catch {
        return $false
    }
}

if ($env:EASY_CLAUDECODE_AUTO_INSTALL_SHORTCUT -ne "0") {
    try {
        & (Join-Path $PSScriptRoot "install-desktop-shortcut.ps1") | Out-Null
    } catch {
        Write-Warning ("desktop shortcut install skipped: " + $_.Exception.Message)
    }
}

if ($env:EASY_CLAUDECODE_AUTO_INSTALL_CC -ne "0") {
    try {
        & (Join-Path $PSScriptRoot "install-cc-launcher.ps1") | Out-Null
    } catch {
        Write-Warning ("cc launcher install skipped: " + $_.Exception.Message)
    }
}

if (-not (Test-Healthy $env:CLAUDE_ROUTER_HEALTH_URL)) {
    Start-Process $ShellBin -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File",(Join-Path $PSScriptRoot "start-claude-code-router.ps1")) -WindowStyle Hidden -RedirectStandardOutput $RouterStdoutLog -RedirectStandardError $RouterStderrLog | Out-Null
    Start-Sleep -Seconds 1
}

if (-not (Test-Healthy $env:CLAUDE_PROXY_HEALTH_URL)) {
    Start-Process $ShellBin -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File",(Join-Path $PSScriptRoot "start-claude-code-dashscope-proxy.ps1")) -WindowStyle Hidden -RedirectStandardOutput $ProxyStdoutLog -RedirectStandardError $ProxyStderrLog | Out-Null
    Start-Sleep -Seconds 1
}

if (-not (Test-Healthy $StatusUrl)) {
    Start-Process $ShellBin -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File",(Join-Path $PSScriptRoot "run-claude-console.ps1")) -WindowStyle Hidden -RedirectStandardOutput $BackendStdoutLog -RedirectStandardError $BackendStderrLog | Out-Null
}

for ($i = 0; $i -lt 20; $i++) {
    if (Test-Healthy $StatusUrl) {
        break
    }
    Start-Sleep -Seconds 1
}

if ($NoBrowser) {
    Write-Output $ConsoleUrl
} else {
    Start-Process $ConsoleUrl
}
