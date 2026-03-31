$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$TempRoot = Join-Path $env:TEMP ("easy-claudecode-launcher-lock-" + [guid]::NewGuid().ToString("N"))
$OutputDir = Join-Path $TempRoot "bin"
$LockedPath = Join-Path $OutputDir "Claude Code.app.exe"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
[System.IO.File]::WriteAllBytes($LockedPath, [byte[]](1..32))
$lockStream = [System.IO.File]::Open($LockedPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)

try {
    $builtPath = & (Join-Path $RepoRoot "scripts\build-desktop-launcher.ps1") -OutputDir $OutputDir
    if (-not $builtPath) {
        throw "build script did not return a launcher path"
    }
    $resolvedBuiltPath = (Resolve-Path $builtPath).Path
    if (-not (Test-Path $resolvedBuiltPath)) {
        throw "returned launcher path does not exist: $resolvedBuiltPath"
    }
    if ($resolvedBuiltPath -eq $LockedPath) {
        throw "build script should not reuse the locked output path"
    }

    Add-Type -AssemblyName System.Drawing
    $icon = [System.Drawing.Icon]::ExtractAssociatedIcon($resolvedBuiltPath)
    $pngPath = Join-Path $TempRoot "built-launcher-icon.png"
    $icon.ToBitmap().Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
    if (-not (Test-Path $pngPath)) {
        throw "failed to extract icon from fallback launcher"
    }

    Write-Output $resolvedBuiltPath
} finally {
    if ($lockStream) {
        $lockStream.Close()
        $lockStream.Dispose()
    }
    Remove-Item $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
