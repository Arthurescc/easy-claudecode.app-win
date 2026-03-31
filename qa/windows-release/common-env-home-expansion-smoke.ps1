$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$TempRoot = Join-Path $env:TEMP ("easy-claudecode-common-env-" + [guid]::NewGuid().ToString("N"))
$TempHome = Join-Path $TempRoot "home"
$EnvFile = Join-Path $TempRoot ".env"

New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
New-Item -ItemType Directory -Force -Path $TempHome | Out-Null

@"
EASY_CLAUDECODE_HOME=`$HOME/.easy-claudecode
"@ | Set-Content -Path $EnvFile -Encoding utf8

$oldHome = $env:HOME
$oldUserProfile = $env:USERPROFILE
$oldEnvFile = $env:EASY_CLAUDECODE_ENV_FILE

try {
    $env:HOME = $TempHome
    $env:USERPROFILE = $TempHome
    $env:EASY_CLAUDECODE_ENV_FILE = $EnvFile

    . (Join-Path $RepoRoot "scripts\common-env.ps1")

    $expected = [System.IO.Path]::GetFullPath((Join-Path $TempHome ".easy-claudecode"))
    $actual = [System.IO.Path]::GetFullPath($env:EASY_CLAUDECODE_HOME)
    if ($actual -ne $expected) {
        throw "common-env should expand `$HOME paths. expected: $expected actual: $actual"
    }

    Write-Output $env:EASY_CLAUDECODE_HOME
} finally {
    if ($null -ne $oldHome) { $env:HOME = $oldHome } else { Remove-Item Env:HOME -ErrorAction SilentlyContinue }
    if ($null -ne $oldUserProfile) { $env:USERPROFILE = $oldUserProfile } else { Remove-Item Env:USERPROFILE -ErrorAction SilentlyContinue }
    if ($null -ne $oldEnvFile) { $env:EASY_CLAUDECODE_ENV_FILE = $oldEnvFile } else { Remove-Item Env:EASY_CLAUDECODE_ENV_FILE -ErrorAction SilentlyContinue }
    Remove-Item $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
