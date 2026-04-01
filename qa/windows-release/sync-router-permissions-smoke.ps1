$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$TempHome = Join-Path $env:TEMP ("easy-claudecode-sync-router-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $TempHome | Out-Null

try {
    $DocumentsPath = Join-Path $TempHome "docs"
    $DesktopPath = Join-Path $TempHome "desktop"
    $WorkspaceRoot = (Resolve-Path (Join-Path $RepoRoot "..")).Path
    New-Item -ItemType Directory -Force -Path $DocumentsPath | Out-Null
    New-Item -ItemType Directory -Force -Path $DesktopPath | Out-Null

    $env:HOME = $TempHome
    $env:USERPROFILE = $TempHome
    $env:EASY_CLAUDECODE_ROOT = $RepoRoot
    $env:EASY_CLAUDECODE_ENV_FILE = Join-Path $TempHome ".env"
    $env:EASY_CLAUDECODE_HOME = Join-Path $TempHome ".easy-claudecode"
    $env:CLAUDE_WORKSPACE_ROOT = $WorkspaceRoot
    $env:CLAUDE_EXTRA_ALLOWED_DIRS = "$DocumentsPath,$DesktopPath"
    $env:EASY_CLAUDECODE_DEFAULT_ROUTE = "compatible-coding,MiniMax-M2.7"

    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\sync-router.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "sync-router.ps1 failed"
    }

    $settingsPath = Join-Path $TempHome ".claude\settings.json"
    if (-not (Test-Path $settingsPath)) {
        throw "settings.json was not created"
    }

    $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
    if ($settings.model -ne "compatible-coding,MiniMax-M2.7") {
        throw "unexpected model value: $($settings.model)"
    }
    if ($settings.permissions.defaultMode -ne "acceptEdits") {
        throw "expected acceptEdits defaultMode, got $($settings.permissions.defaultMode)"
    }
    $allow = @($settings.permissions.allow)
    foreach ($tool in @("Bash", "WebFetch", "Read", "Edit", "Write", "MultiEdit", "Task")) {
        if ($allow -notcontains $tool) {
            throw "missing allowed tool: $tool"
        }
    }
    $dirs = @($settings.permissions.additionalDirectories) | ForEach-Object { ([string]$_).Replace('\', '/').TrimEnd('/') }
    foreach ($dir in @($DocumentsPath, $DesktopPath, $WorkspaceRoot, $RepoRoot)) {
        $normalizedDir = ([string]$dir).Replace('\', '/').TrimEnd('/')
        if ($dirs -notcontains $normalizedDir) {
            throw "missing additional directory: $dir"
        }
    }

    Write-Output "sync router permissions ok"
} finally {
    Remove-Item $TempHome -Recurse -Force -ErrorAction SilentlyContinue
}
