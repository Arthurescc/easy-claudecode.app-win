param(
    [string]$Target = "claude",
    [string]$Profile = "full",
    [switch]$StatusOnly
)

$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

$VendorRoot = Join-Path $env:EASY_CLAUDECODE_HOME "vendor"
$RepoPath = Join-Path $VendorRoot "everything-claude-code"
$StateRoot = Join-Path $env:EASY_CLAUDECODE_HOME "state"
$StatePath = Join-Path $StateRoot "everything-claude-code.json"
$RepoUrl = "https://github.com/affaan-m/everything-claude-code.git"
$KnownTargets = @("claude", "cursor", "antigravity", "codex", "opencode")
$KnownProfiles = @("core", "developer", "security", "research", "full")
$BootstrapNpmVersion = "11.12.1"
$BootstrapNpmTarballUrl = "https://registry.npmjs.org/npm/-/npm-$BootstrapNpmVersion.tgz"

if ($KnownTargets -notcontains $Target) {
    throw "unsupported target: $Target"
}
if ($KnownProfiles -notcontains $Profile) {
    throw "unsupported profile: $Profile"
}

function Get-GitRevision {
    param([string]$Path)

    if (-not (Test-Path (Join-Path $Path ".git"))) {
        return ""
    }

    try {
        return (git -C $Path rev-parse --short HEAD 2>$null).Trim()
    } catch {
        return ""
    }
}

function Get-NodeCommand {
    $candidate = Get-Command node -ErrorAction SilentlyContinue
    if ($candidate) {
        return $candidate.Source
    }
    $fallback = Join-Path $HOME ".local\bin\node.exe"
    if (Test-Path $fallback) {
        return $fallback
    }
    throw "node is required to install Everything Claude Code"
}

function Ensure-NpmCommand {
    $candidate = Get-Command npm -ErrorAction SilentlyContinue
    if ($candidate) {
        return $candidate.Source
    }

    $nodePath = Get-NodeCommand
    $bootstrapRoot = Join-Path $env:EASY_CLAUDECODE_HOME "tools\npm\$BootstrapNpmVersion"
    $bootstrapPackageRoot = Join-Path $bootstrapRoot "package"
    $npmCli = Join-Path $bootstrapPackageRoot "bin\npm-cli.js"
    $shimPath = Join-Path $bootstrapRoot "npm.cmd"

    if (-not (Test-Path $npmCli)) {
        $archivePath = Join-Path $bootstrapRoot "npm.tgz"
        New-Item -ItemType Directory -Force -Path $bootstrapRoot | Out-Null
        Invoke-WebRequest -Uri $BootstrapNpmTarballUrl -OutFile $archivePath -UseBasicParsing
        tar -xzf $archivePath -C $bootstrapRoot
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $npmCli)) {
            throw "failed to bootstrap npm from $BootstrapNpmTarballUrl"
        }
    }

    $shimContent = @"
@echo off
"$nodePath" "$npmCli" %*
"@
    [System.IO.File]::WriteAllText($shimPath, $shimContent, [System.Text.UTF8Encoding]::new($false))
    $env:PATH = "$bootstrapRoot;$env:PATH"
    return $shimPath
}

function Read-State {
    if (-not (Test-Path $StatePath)) {
        return @{}
    }
    try {
        return Get-Content -Raw $StatePath | ConvertFrom-Json -AsHashtable
    } catch {
        return @{}
    }
}

function Write-State {
    param([hashtable]$State)

    New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
    ($State | ConvertTo-Json -Depth 6) | Set-Content -Path $StatePath -Encoding utf8
}

function Get-InstallStatus {
    $state = Read-State
    $revision = Get-GitRevision -Path $RepoPath
    $rulesRoot = Join-Path $HOME ".claude\rules"
    $likelyInstalled = (Test-Path (Join-Path $rulesRoot "common")) -or (Test-Path (Join-Path $HOME ".claude\agents"))

    return @{
        available = $true
        installed = [bool]($state.installed -or $likelyInstalled)
        repoPath = $RepoPath
        repoUrl = $RepoUrl
        target = if ($state.target) { $state.target } else { $Target }
        profile = if ($state.profile) { $state.profile } else { $Profile }
        revision = if ($state.revision) { $state.revision } else { $revision }
        lastInstalledAt = if ($state.lastInstalledAt) { $state.lastInstalledAt } else { "" }
        source = "official-github"
        optional = $true
        defaultSelected = $false
    }
}

if ($StatusOnly) {
    Get-InstallStatus | ConvertTo-Json -Depth 6
    exit 0
}

Ensure-NpmCommand | Out-Null

New-Item -ItemType Directory -Force -Path $VendorRoot | Out-Null

if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
    git clone --depth 1 $RepoUrl $RepoPath | Out-Null
} else {
    git -C $RepoPath pull --ff-only | Out-Null
}

Push-Location $RepoPath
try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoPath "install.ps1") --target $Target --profile $Profile
    if ($LASTEXITCODE -ne 0) {
        throw "Everything Claude Code installer exited with code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$revision = Get-GitRevision -Path $RepoPath
$state = @{
    installed = $true
    repoPath = $RepoPath
    repoUrl = $RepoUrl
    target = $Target
    profile = $Profile
    revision = $revision
    lastInstalledAt = (Get-Date).ToString("o")
    source = "official-github"
    optional = $true
    defaultSelected = $false
}
Write-State -State $state
$state | ConvertTo-Json -Depth 6
