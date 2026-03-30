$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

$BinDir = Join-Path $HOME ".local\bin"
$LauncherPath = Join-Path $BinDir "cc.cmd"
$RepoRoot = (Resolve-Path $env:EASY_CLAUDECODE_ROOT).Path
$SwitchScript = (Resolve-Path (Join-Path $RepoRoot "scripts\cc-switch.ps1")).Path
$ClaudeRouterCmd = (Resolve-Path (Join-Path $RepoRoot "scripts\claude-local-router.cmd")).Path

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$content = @"
@echo off
setlocal
if /I "%~1"=="switch" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "$SwitchScript" %2 %3 %4 %5 %6 %7 %8 %9
  exit /b %errorlevel%
)
call "$ClaudeRouterCmd" %*
"@

[System.IO.File]::WriteAllText($LauncherPath, $content, [System.Text.UTF8Encoding]::new($false))
Write-Output $LauncherPath
