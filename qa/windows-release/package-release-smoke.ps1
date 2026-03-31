$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Version = "0.0.0-test"
$ExpectedInstaller = Join-Path $RepoRoot "dist\easy-claudecode.app-win-$Version-setup.exe"

& (Join-Path $RepoRoot "scripts\package-release.ps1") -Version $Version | Out-Null

if (-not (Test-Path $ExpectedInstaller)) {
    throw "setup exe was not created: $ExpectedInstaller"
}

Write-Output $ExpectedInstaller
