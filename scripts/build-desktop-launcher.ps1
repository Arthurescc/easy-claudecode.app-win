param(
    [string]$OutputDir = "",
    [switch]$SelfContained,
    [string]$RuntimeIdentifier = "win-x64"
)

$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

$ProjectDir = Join-Path $env:EASY_CLAUDECODE_ROOT "apps\desktop-windows\launcher"
$ProgramFile = Join-Path $ProjectDir "Program.cs"
$IconPath = Join-Path $env:EASY_CLAUDECODE_ROOT "apps\desktop-windows\assets\ClaudeCodeApp.ico"
$ResolvedOutputDir = if ($OutputDir) { $OutputDir } else { $env:EASY_CLAUDECODE_DESKTOP_LAUNCHER_DIR }
$CscCandidates = @(
    "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)
$CscPath = $CscCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not (Test-Path $ProgramFile)) {
    throw "launcher source not found: $ProgramFile"
}
if (-not $CscPath) {
    throw "csc.exe not found in the default .NET Framework paths"
}
if (-not (Test-Path $IconPath)) {
    throw "launcher icon not found: $IconPath"
}

New-Item -ItemType Directory -Force -Path $ResolvedOutputDir | Out-Null

$LauncherPath = Join-Path $ResolvedOutputDir "Claude Code.app.exe"
$CompileArgs = @(
    "/nologo",
    "/target:winexe",
    "/optimize+",
    "/out:$LauncherPath",
    "/win32icon:$IconPath",
    "/r:System.dll",
    "/r:System.Core.dll",
    "/r:System.Windows.Forms.dll",
    $ProgramFile
)

& $CscPath @CompileArgs
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $LauncherPath)) {
    throw "launcher compile failed"
}

Write-Output $LauncherPath
