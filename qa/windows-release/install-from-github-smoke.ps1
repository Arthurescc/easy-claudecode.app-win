$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ScriptPath = Join-Path $RepoRoot "scripts\install-from-github.ps1"

if (-not (Test-Path $ScriptPath)) {
    throw "bootstrap script missing: $ScriptPath"
}

& $ScriptPath -UseCurrentRepo -NoLaunch -SkipClaudeTools
if ($LASTEXITCODE -ne 0) {
    throw "bootstrap script returned exit code $LASTEXITCODE"
}
