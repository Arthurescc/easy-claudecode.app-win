param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

function Get-RouterConfigPath {
    $preferred = Join-Path $HOME ".claude-code-router\config.json"
    if (Test-Path $preferred) {
        return $preferred
    }
    return $env:CLAUDE_ROUTER_CONFIG_FILE
}

function Get-CurrentRoute {
    param([object]$Config)
    if ($Config.Router -and $Config.Router.default) {
        return [string]$Config.Router.default
    }
    if ($Config.router -and $Config.router.default) {
        return [string]$Config.router.default
    }
    return ""
}

function Get-RouteOptions {
    param([object]$Config)
    $providers = @()
    if ($Config.Providers) {
        $providers = @($Config.Providers)
    } elseif ($Config.providers) {
        $providers = @($Config.providers)
    }
    $items = @()
    foreach ($provider in $providers) {
        if (-not $provider -or -not $provider.name) {
            continue
        }
        foreach ($model in @($provider.models)) {
            if (-not $model) {
                continue
            }
            $items += [pscustomobject]@{
                Id = "$($provider.name),$model"
                Provider = [string]$provider.name
                Model = [string]$model
            }
        }
    }
    return $items
}

function Save-EnvValue {
    param(
        [string]$Key,
        [string]$Value
    )
    $envPath = $env:EASY_CLAUDECODE_ENV_FILE
    $lines = @()
    if (Test-Path $envPath) {
        $lines = Get-Content $envPath
    }
    $updated = $false
    $escapedKey = [regex]::Escape($Key)
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^${escapedKey}=") {
            $lines[$i] = "$Key=$Value"
            $updated = $true
            break
        }
    }
    if (-not $updated) {
        $lines += "$Key=$Value"
    }
    [System.IO.File]::WriteAllLines($envPath, $lines, [System.Text.UTF8Encoding]::new($false))
    [Environment]::SetEnvironmentVariable($Key, $Value, "Process")
}

function Resolve-RouteSelection {
    param(
        [string]$RawValue,
        [object[]]$Routes
    )
    $value = if ($null -ne $RawValue) { [string]$RawValue } else { "" }
    if (-not $value.Trim()) {
        return ""
    }
    $trimmed = $value.Trim()
    if ($trimmed -match '^\d+$') {
        $index = [int]$trimmed - 1
        if ($index -ge 0 -and $index -lt $Routes.Count) {
            return [string]$Routes[$index].Id
        }
    }
    $exact = @($Routes | Where-Object { $_.Id -eq $trimmed })
    if ($exact.Count -eq 1) {
        return [string]$exact[0].Id
    }
    $modelMatch = @($Routes | Where-Object { $_.Model -eq $trimmed })
    if ($modelMatch.Count -eq 1) {
        return [string]$modelMatch[0].Id
    }
    return ""
}

$configPath = Get-RouterConfigPath
if (-not (Test-Path $configPath)) {
    throw "router config not found: $configPath"
}

$config = Get-Content $configPath | ConvertFrom-Json
$routes = @(Get-RouteOptions -Config $config)
if (-not $routes.Count) {
    throw "no connected model routes found in $configPath"
}

$currentRoute = Get-CurrentRoute -Config $config
$routeArg = if ($Args.Count -gt 0) { [string]$Args[0] } else { "" }
$argOffset = if ($routeArg -eq "switch") { 1 } else { 0 }
if ($argOffset -gt 0) {
    $routeArg = if ($Args.Count -gt 1) { [string]$Args[1] } else { "" }
}
$currentLabel = if ($currentRoute) { $currentRoute } else { "<none>" }

if ($routeArg -eq "--list") {
    Write-Output ("Current: " + $currentLabel)
    for ($i = 0; $i -lt $routes.Count; $i++) {
        Write-Output ("[{0}] {1}" -f ($i + 1), $routes[$i].Id)
    }
    exit 0
}

if (-not $routeArg) {
    Write-Output ("Current: " + $currentLabel)
    for ($i = 0; $i -lt $routes.Count; $i++) {
        Write-Output ("[{0}] {1}" -f ($i + 1), $routes[$i].Id)
    }
    $routeArg = Read-Host "Switch to route number or provider,model"
}

$selectedRoute = Resolve-RouteSelection -RawValue $routeArg -Routes $routes
if (-not $selectedRoute) {
    throw "unknown route: $routeArg"
}

Save-EnvValue -Key "EASY_CLAUDECODE_DEFAULT_ROUTE" -Value $selectedRoute

$syncScript = Join-Path $PSScriptRoot "sync-router.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $syncScript | Out-Null

$ccrBin = if ($env:CCR_BIN) { $env:CCR_BIN } else { "ccr" }
& $ccrBin restart | Out-Null

Write-Output ("Switched route to " + $selectedRoute)
