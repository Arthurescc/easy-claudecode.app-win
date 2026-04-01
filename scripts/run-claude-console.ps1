$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")
if (-not $env:CLAUDE_WEB_PERMISSION_MODE -or $env:CLAUDE_WEB_PERMISSION_MODE.Trim().ToLowerInvariant() -eq "default") {
    $env:CLAUDE_WEB_PERMISSION_MODE = "auto"
}

function Resolve-PythonBin {
    $candidates = @()
    if ($env:CLAUDE_CONSOLE_PYTHON_BIN) {
        $candidates += $env:CLAUDE_CONSOLE_PYTHON_BIN
    }
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $candidates += $pythonCommand.Source
    }
    foreach ($candidate in $candidates) {
        $text = [string]$(if ($null -ne $candidate) { $candidate } else { "" })
        $text = $text.Trim()
        if (-not $text) {
            continue
        }
        if (Test-Path $text) {
            return (Resolve-Path $text).Path
        }
    }
    throw "python executable not found for Claude Console backend"
}

$PythonBin = Resolve-PythonBin
& (Join-Path $PSScriptRoot "sync-router.ps1")
Set-Location $env:EASY_CLAUDECODE_ROOT
& $PythonBin "services/backend/app.py"
