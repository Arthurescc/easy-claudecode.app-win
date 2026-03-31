$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")
$env:CLAUDE_WEB_PERMISSION_MODE = if ($env:CLAUDE_WEB_PERMISSION_MODE) { $env:CLAUDE_WEB_PERMISSION_MODE } else { "auto" }

$PythonBin = if ($env:CLAUDE_CONSOLE_PYTHON_BIN) { $env:CLAUDE_CONSOLE_PYTHON_BIN } else { "python" }
& (Join-Path $PSScriptRoot "sync-router.ps1")
Set-Location $env:EASY_CLAUDECODE_ROOT
& $PythonBin "services/backend/app.py"
