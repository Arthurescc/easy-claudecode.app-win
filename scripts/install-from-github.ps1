param(
    [string]$RepoUrl = "https://github.com/Arthurescc/easy-claudecode.app-win.git",
    [string]$Branch = "main",
    [string]$InstallDir = "",
    [switch]$UseCurrentRepo,
    [switch]$NoLaunch,
    [switch]$SkipClaudeTools
)

$ErrorActionPreference = "Stop"
$BootstrapNpmVersion = "11.12.1"
$BootstrapNpmTarballUrl = "https://registry.npmjs.org/npm/-/npm-$BootstrapNpmVersion.tgz"

function Write-Step {
    param([string]$Message)
    Write-Host ("[easy-claudecode] " + $Message)
}

function Resolve-InstallDir {
    param([string]$ExplicitPath, [switch]$UseCurrentRepoMode)

    if ($UseCurrentRepoMode) {
        $candidate = if ($PSScriptRoot) {
            Resolve-Path (Join-Path $PSScriptRoot "..")
        } else {
            Resolve-Path .
        }
        return $candidate.Path
    }

    if ($ExplicitPath) {
        $resolved = Resolve-Path -LiteralPath $ExplicitPath -ErrorAction SilentlyContinue
        if ($resolved) {
            return $resolved.Path
        }
        return $ExplicitPath
    }

    $home = if ($env:USERPROFILE) { $env:USERPROFILE } else { [Environment]::GetFolderPath("UserProfile") }
    return (Join-Path $home "easy-claudecode.app-win")
}

function Get-CommandPath {
    param([string]$Name)
    return (Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
}

function Get-NodeCommand {
    $candidate = Get-CommandPath "node"
    if ($candidate) {
        return $candidate
    }
    $fallback = Join-Path $HOME ".local\bin\node.exe"
    if (Test-Path $fallback) {
        return $fallback
    }
    throw "Node.js is required before bootstrap can continue."
}

function Ensure-NpmCommand {
    $candidate = Get-CommandPath "npm"
    if ($candidate) {
        return $candidate
    }

    $nodePath = Get-NodeCommand
    $siblingDir = Split-Path -Parent $nodePath
    foreach ($sibling in @("npm.cmd", "npm")) {
        $siblingPath = Join-Path $siblingDir $sibling
        if (Test-Path $siblingPath) {
            return $siblingPath
        }
    }

    $homeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { [Environment]::GetFolderPath("UserProfile") }
    $bootstrapRoot = Join-Path $homeDir ".easy-claudecode\tools\npm\$BootstrapNpmVersion"
    $bootstrapPackageRoot = Join-Path $bootstrapRoot "package"
    $npmCli = Join-Path $bootstrapPackageRoot "bin\npm-cli.js"
    $shimPath = Join-Path $bootstrapRoot "npm.cmd"

    if (-not (Test-Path $npmCli)) {
        $archivePath = Join-Path $bootstrapRoot "npm.tgz"
        New-Item -ItemType Directory -Force -Path $bootstrapRoot | Out-Null
        Invoke-WebRequest -Uri $BootstrapNpmTarballUrl -OutFile $archivePath -UseBasicParsing
        tar -xzf $archivePath -C $bootstrapRoot
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $npmCli)) {
            throw "Failed to bootstrap npm from $BootstrapNpmTarballUrl"
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

function Install-WingetPackageIfMissing {
    param(
        [string]$CommandName,
        [string]$WingetId,
        [string]$DisplayName
    )

    if (Get-CommandPath $CommandName) {
        return
    }

    $winget = Get-CommandPath "winget"
    if (-not $winget) {
        throw "$DisplayName is missing and winget is not available to install it automatically."
    }

    Write-Step "Installing $DisplayName via winget"
    & $winget install --id $WingetId -e --accept-package-agreements --accept-source-agreements --source winget
    if ($LASTEXITCODE -ne 0 -or -not (Get-CommandPath $CommandName)) {
        throw "Failed to install $DisplayName via winget."
    }
}

function Ensure-GitRepo {
    param(
        [string]$TargetDir,
        [string]$RepositoryUrl,
        [string]$TargetBranch,
        [switch]$UseCurrentRepoMode
    )

    if ($UseCurrentRepoMode) {
        return $TargetDir
    }

    if (-not (Test-Path $TargetDir)) {
        Write-Step "Cloning repository into $TargetDir"
        & git clone --depth 1 --branch $TargetBranch $RepositoryUrl $TargetDir
        if ($LASTEXITCODE -ne 0) {
            throw "git clone failed"
        }
        return $TargetDir
    }

    if (-not (Test-Path (Join-Path $TargetDir ".git"))) {
        throw "Install directory exists but is not a git repository: $TargetDir"
    }

    Write-Step "Updating existing repository in $TargetDir"
    Push-Location $TargetDir
    try {
        & git fetch --tags origin
        if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
        & git checkout $TargetBranch
        if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }
        & git pull --ff-only origin $TargetBranch
        if ($LASTEXITCODE -ne 0) { throw "git pull failed" }
    } finally {
        Pop-Location
    }

    return $TargetDir
}

function Ensure-ClaudeTools {
    $npm = Ensure-NpmCommand
    if (-not $npm) {
        throw "npm is required before Claude CLI and CCR can be installed."
    }

    if (-not (Get-CommandPath "claude")) {
        Write-Step "Installing Claude Code CLI"
        & $npm install -g @anthropic-ai/claude-code
        if ($LASTEXITCODE -ne 0 -or -not (Get-CommandPath "claude")) {
            throw "Failed to install Claude Code CLI."
        }
    }

    if (-not (Get-CommandPath "ccr")) {
        Write-Step "Installing Claude Code Router"
        & $npm install -g @musistudio/claude-code-router
        if ($LASTEXITCODE -ne 0 -or -not (Get-CommandPath "ccr")) {
            throw "Failed to install Claude Code Router."
        }
    }
}

function Ensure-VenvAndDeps {
    param([string]$RepoRoot)

    $pyLauncher = Get-CommandPath "py"
    $python = if ($pyLauncher) { $pyLauncher } else { Get-CommandPath "python" }
    $npm = Ensure-NpmCommand
    if (-not $python) {
        throw "Python is not available after prerequisite setup."
    }

    Push-Location $RepoRoot
    try {
        $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
        if (-not (Test-Path $venvPython)) {
            Write-Step "Creating .venv"
            if ($pyLauncher) {
                & $pyLauncher -3 -m venv .venv
            } else {
                & $python -m venv .venv
            }
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
                throw "Failed to create .venv"
            }
        }

        Write-Step "Installing Python dependencies"
        & $venvPython -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
        & $venvPython -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

        Write-Step "Installing Node dependencies"
        & $npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    } finally {
        Pop-Location
    }
}

function Ensure-EnvFile {
    param([string]$RepoRoot)

    $envExample = Join-Path $RepoRoot ".env.example"
    $envFile = Join-Path $RepoRoot ".env"
    if (-not (Test-Path $envFile)) {
        Write-Step "Creating .env from .env.example"
        Copy-Item $envExample $envFile -Force
    }
}

$resolvedInstallDir = Resolve-InstallDir -ExplicitPath $InstallDir -UseCurrentRepoMode:$UseCurrentRepo

Install-WingetPackageIfMissing -CommandName "git" -WingetId "Git.Git" -DisplayName "Git"
Install-WingetPackageIfMissing -CommandName "node" -WingetId "OpenJS.NodeJS.LTS" -DisplayName "Node.js LTS"
if (-not (Get-CommandPath "py") -and -not (Get-CommandPath "python")) {
    Install-WingetPackageIfMissing -CommandName "py" -WingetId "Python.Python.3.11" -DisplayName "Python 3.11"
}

$repoRoot = Ensure-GitRepo -TargetDir $resolvedInstallDir -RepositoryUrl $RepoUrl -TargetBranch $Branch -UseCurrentRepoMode:$UseCurrentRepo
Ensure-VenvAndDeps -RepoRoot $repoRoot
Ensure-EnvFile -RepoRoot $repoRoot
if (-not $SkipClaudeTools) {
    Ensure-ClaudeTools
}

if ($NoLaunch) {
    Write-Step "Bootstrap complete: $repoRoot"
    return
}

Write-Step "Launching easy-claudecode.app-win"
Push-Location $repoRoot
try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\open-claude-code.ps1")
} finally {
    Pop-Location
}
