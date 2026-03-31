param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
if (-not $Version) {
    $PackageJson = Get-Content (Join-Path $RepoRoot "package.json") | ConvertFrom-Json
    $Version = [string]$PackageJson.version
}

$PackageName = "easy-claudecode.app-win-$Version"
$OutputDir = Join-Path $RepoRoot "dist"
$StageDir = Join-Path $OutputDir $PackageName
$BundleZipPath = Join-Path $OutputDir "$PackageName-bundle.zip"
$LegacyZipPath = Join-Path $OutputDir "$PackageName.zip"
$InstallerPath = Join-Path $OutputDir "$PackageName-setup.exe"
$LauncherOutputDir = Join-Path $StageDir "apps\desktop-windows\bin"

$IncludePaths = @(
    ".env.example",
    ".gitignore",
    ".github",
    "apps",
    "config",
    "docs",
    "LICENSE",
    "package-lock.json",
    "package.json",
    "qa",
    "README.md",
    "requirements.txt",
    "scripts",
    "services"
)

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
Remove-Item $StageDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $BundleZipPath -Force -ErrorAction SilentlyContinue
Remove-Item $LegacyZipPath -Force -ErrorAction SilentlyContinue
Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null

foreach ($RelativePath in $IncludePaths) {
    $SourcePath = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path $SourcePath)) {
        continue
    }
    $DestinationPath = Join-Path $StageDir $RelativePath
    $DestinationParent = Split-Path -Parent $DestinationPath
    if ($DestinationParent) {
        New-Item -ItemType Directory -Force -Path $DestinationParent | Out-Null
    }
    Copy-Item $SourcePath $DestinationPath -Recurse -Force
}

& (Join-Path $RepoRoot "scripts\build-desktop-launcher.ps1") -OutputDir $LauncherOutputDir -SelfContained | Out-Null

Compress-Archive -Path (Join-Path $StageDir "*") -DestinationPath $BundleZipPath -Force
Copy-Item $BundleZipPath $LegacyZipPath -Force
& (Join-Path $RepoRoot "scripts\build-release-installer.ps1") -BundleZipPath $BundleZipPath -OutputPath $InstallerPath | Out-Null

Write-Output $InstallerPath
