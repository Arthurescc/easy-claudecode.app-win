$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

$DesktopDir = $env:EASY_CLAUDECODE_SHORTCUT_DESKTOP_DIR
$ShortcutPath = $env:EASY_CLAUDECODE_SHORTCUT_PATH
$WorkingDirectory = (Resolve-Path $env:EASY_CLAUDECODE_ROOT).Path
$TargetPath = $null

if (-not $DesktopDir) {
    throw "desktop directory is not configured"
}

New-Item -ItemType Directory -Force -Path $DesktopDir | Out-Null

try {
    $BuiltLauncher = & (Join-Path $PSScriptRoot "build-desktop-launcher.ps1")
    if ($BuiltLauncher) {
        $TargetPath = (Resolve-Path $BuiltLauncher | Select-Object -First 1).Path
    }
} catch {
    Write-Warning ("desktop launcher build skipped: " + $_.Exception.Message)
}

if (-not $TargetPath -and (Test-Path $env:EASY_CLAUDECODE_DESKTOP_LAUNCHER_PATH)) {
    $TargetPath = (Resolve-Path $env:EASY_CLAUDECODE_DESKTOP_LAUNCHER_PATH).Path
}

if (-not $TargetPath) {
    $TargetPath = (Resolve-Path (Join-Path $env:EASY_CLAUDECODE_ROOT "scripts\open-claude-code.cmd")).Path
}

$IconLocation = if ($TargetPath -like "*.exe" -and (Test-Path $TargetPath)) {
    "$TargetPath,0"
} elseif ($env:CLAUDE_REAL_BIN -and (Test-Path $env:CLAUDE_REAL_BIN)) {
    "$($env:CLAUDE_REAL_BIN),0"
} else {
    "$env:SystemRoot\System32\shell32.dll,220"
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = $WorkingDirectory
$Shortcut.Description = if ($TargetPath -like "*.exe") { "Launch easy-claudecode.app-win via launcher exe" } else { "Launch easy-claudecode.app-win" }
$Shortcut.IconLocation = $IconLocation
$Shortcut.WindowStyle = 1
$Shortcut.Save()

$IconRefreshBin = Join-Path $env:SystemRoot "System32\ie4uinit.exe"
if (Test-Path $IconRefreshBin) {
    try {
        & $IconRefreshBin -show | Out-Null
    } catch {
    }
}

Write-Output $ShortcutPath
