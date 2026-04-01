$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$TempHome = Join-Path $env:TEMP ("easy-claudecode-sync-router-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $TempHome | Out-Null

try {
    $env:HOME = $TempHome
    $env:USERPROFILE = $TempHome
    $env:EASY_CLAUDECODE_ROOT = $RepoRoot
    $env:EASY_CLAUDECODE_HOME = Join-Path $TempHome ".easy-claudecode"
    $env:CLAUDE_WORKSPACE_ROOT = "C:/Users/Administrator/Documents/Playground"
    $env:CLAUDE_EXTRA_ALLOWED_DIRS = "C:/Users/Administrator/Documents,C:/Users/Administrator/Desktop"
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
    $dirs = @($settings.permissions.additionalDirectories)
    foreach ($dir in @("C:/Users/Administrator/Documents", "C:/Users/Administrator/Desktop", "C:/Users/Administrator/Documents/Playground", $RepoRoot)) {
        if ($dirs -notcontains $dir) {
            throw "missing additional directory: $dir"
        }
    }

    Write-Output "sync router permissions ok"
} finally {
    Remove-Item $TempHome -Recurse -Force -ErrorAction SilentlyContinue
}
