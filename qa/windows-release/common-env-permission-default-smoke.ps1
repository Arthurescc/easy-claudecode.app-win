$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ScriptPath = Join-Path $RepoRoot "scripts\common-env.ps1"

function Invoke-CommonEnvValue {
    param(
        [string]$InitialValue
    )

    $command = @"
`$env:CLAUDE_WEB_PERMISSION_MODE = '$InitialValue'
. '$ScriptPath'
Write-Output `$env:CLAUDE_WEB_PERMISSION_MODE
"@
    powershell -NoProfile -ExecutionPolicy Bypass -Command $command
}

$fromDefault = (Invoke-CommonEnvValue -InitialValue "default" | Select-Object -Last 1).Trim()
if ($fromDefault -ne "auto") {
    throw "expected inherited default permission mode to normalize to auto, got '$fromDefault'"
}

$fromEmpty = (Invoke-CommonEnvValue -InitialValue "" | Select-Object -Last 1).Trim()
if ($fromEmpty -ne "auto") {
    throw "expected empty permission mode to normalize to auto, got '$fromEmpty'"
}

$fromBypass = (Invoke-CommonEnvValue -InitialValue "bypassPermissions" | Select-Object -Last 1).Trim()
if ($fromBypass -ne "bypassPermissions") {
    throw "expected explicit bypassPermissions to be preserved, got '$fromBypass'"
}

Write-Output "common env permission default ok"
