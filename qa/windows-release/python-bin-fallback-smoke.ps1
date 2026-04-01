$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

$command = @"
`$env:CLAUDE_CONSOLE_PYTHON_BIN = 'C:/missing-python/python.exe'
. '$RepoRoot\scripts\common-env.ps1'
. '$RepoRoot\scripts\sync-router.ps1'
Write-Output 'sync router fallback ok'
"@

$output = powershell -NoProfile -ExecutionPolicy Bypass -Command $command
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (-not ($output | Select-String -SimpleMatch 'sync router fallback ok')) {
    throw "expected sync router fallback marker in output"
}

Write-Output "python bin fallback ok"
