$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$LauncherDir = Join-Path $RepoRoot "apps\desktop-windows\bin"
$CanonicalLauncher = Join-Path $LauncherDir "Claude Code.app.exe"
$TempDesktop = Join-Path $env:TEMP ("easy-claudecode-shortcut-heal-" + [guid]::NewGuid().ToString("N"))
$ShortcutPath = Join-Path $TempDesktop "Claude Code.app.lnk"
$FallbackLauncher = Join-Path $LauncherDir ("Claude Code.app.smoketest-" + [guid]::NewGuid().ToString("N") + ".exe")

if (-not (Test-Path $CanonicalLauncher)) {
    & (Join-Path $RepoRoot "scripts\build-desktop-launcher.ps1") | Out-Null
}
if (-not (Test-Path $CanonicalLauncher)) {
    throw "canonical launcher missing: $CanonicalLauncher"
}

New-Item -ItemType Directory -Force -Path $TempDesktop | Out-Null
Copy-Item $CanonicalLauncher $FallbackLauncher -Force
$env:EASY_CLAUDECODE_SHORTCUT_DESKTOP_DIR = $TempDesktop
$env:EASY_CLAUDECODE_SHORTCUT_PATH = $ShortcutPath

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $FallbackLauncher
$Shortcut.WorkingDirectory = $RepoRoot
$Shortcut.IconLocation = "$FallbackLauncher,0"
$Shortcut.Save()

$ports = 18882,3456,3460
Get-NetTCPConnection -State Listen -LocalPort $ports -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object {
        try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {}
    }
Start-Sleep -Seconds 2

try {
    $launcherProcess = Start-Process -FilePath $FallbackLauncher -WorkingDirectory $RepoRoot -PassThru
    Start-Sleep -Seconds 18

    $RefreshedShortcut = $Shell.CreateShortcut($ShortcutPath)
    $ResolvedTarget = (Resolve-Path $RefreshedShortcut.TargetPath).Path
    if ($ResolvedTarget -eq (Resolve-Path $FallbackLauncher).Path) {
        throw "launcher did not refresh shortcut target away from stale fallback exe"
    }

    Write-Output $ResolvedTarget
} finally {
    Get-NetTCPConnection -State Listen -LocalPort $ports -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object {
            try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {}
        }
    if ($launcherProcess -and -not $launcherProcess.HasExited) {
        try { Stop-Process -Id $launcherProcess.Id -Force -ErrorAction Stop } catch {}
    }
    Remove-Item $TempDesktop -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $FallbackLauncher -Force -ErrorAction SilentlyContinue
}
