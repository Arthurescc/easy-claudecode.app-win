$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

& (Join-Path $PSScriptRoot "sync-router.ps1")
$CcrBin = if ($env:CCR_BIN) { $env:CCR_BIN } else { "ccr" }

try {
    $Health = Invoke-WebRequest -Uri $env:CLAUDE_ROUTER_HEALTH_URL -UseBasicParsing -TimeoutSec 2
    if ($Health.StatusCode -ge 200 -and $Health.StatusCode -lt 300) {
        exit 0
    }
} catch {
}

Set-Location $env:CLAUDE_ROUTER_RUNTIME_DIR
& $CcrBin "start"
