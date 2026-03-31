param(
    [Parameter(Mandatory = $true)]
    [string]$BundleZipPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

$ProjectDir = Join-Path $env:EASY_CLAUDECODE_ROOT "apps\desktop-windows\installer"
$ProgramFile = Join-Path $ProjectDir "Program.cs"
$IconPath = Join-Path $env:EASY_CLAUDECODE_ROOT "apps\desktop-windows\assets\ClaudeCodeApp.ico"
$CscCandidates = @(
    "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)
$CscPath = $CscCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not (Test-Path $ProgramFile)) {
    throw "installer source not found: $ProgramFile"
}
if (-not (Test-Path $BundleZipPath)) {
    throw "bundle zip not found: $BundleZipPath"
}
if (-not (Test-Path $IconPath)) {
    throw "installer icon not found: $IconPath"
}
if (-not $CscPath) {
    throw "csc.exe not found in the default .NET Framework paths"
}

$OutputDir = Split-Path -Parent $OutputPath
if ($OutputDir) {
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
}

$CompileArgs = @(
    "/nologo",
    "/target:winexe",
    "/optimize+",
    "/out:$OutputPath",
    "/win32icon:$IconPath",
    "/resource:$BundleZipPath,EasyClaudeCode.Bundle.zip",
    "/r:System.dll",
    "/r:System.Core.dll",
    "/r:System.Drawing.dll",
    "/r:System.Windows.Forms.dll",
    "/r:System.IO.Compression.dll",
    "/r:System.IO.Compression.FileSystem.dll",
    $ProgramFile
)

& $CscPath @CompileArgs
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $OutputPath)) {
    throw "installer compile failed"
}

Write-Output $OutputPath
