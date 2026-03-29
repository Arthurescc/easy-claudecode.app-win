$ErrorActionPreference = "Stop"

$ShareCandidates = @("\\10.0.2.2\Data", "\\host.lan\Data")
$RepoName = "easy-claudecode.app-win"
$Result = [ordered]@{
    startedAt = (Get-Date).ToString("o")
    shareRoot = $null
    repoRoot = $null
    pythonReady = $false
    pipInstallOk = $false
    backendStarted = $false
    statusOk = $false
    bootstrapOk = $false
    errors = @()
}

function Add-ResultError([string]$Message) {
    $Result.errors += @($Message)
}

function Resolve-ShareRoot {
    foreach ($candidate in $ShareCandidates) {
        for ($i = 0; $i -lt 20; $i++) {
            if (Test-Path $candidate) {
                return $candidate
            }
            Start-Sleep -Seconds 5
        }
    }
    return $null
}

function Resolve-PythonCommand {
    foreach ($cmd in @("py", "python")) {
        $candidate = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($candidate) {
            return $cmd
        }
    }
    return $null
}

function Install-PythonIfNeeded {
    $pythonCmd = Resolve-PythonCommand
    if ($pythonCmd) {
        return $pythonCmd
    }
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --disable-interactivity
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Start-Sleep -Seconds 5
    return (Resolve-PythonCommand)
}

function Invoke-HealthJson([string]$Url) {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
    return [pscustomobject]@{
        StatusCode = $response.StatusCode
        Body = $response.Content
    }
}

$shareRoot = Resolve-ShareRoot
if (-not $shareRoot) {
    Add-ResultError "Shared host path not reachable."
} else {
    $Result.shareRoot = $shareRoot
    $repoRoot = Join-Path $shareRoot $RepoName
    if (Test-Path $repoRoot) {
        $Result.repoRoot = $repoRoot
    } else {
        Add-ResultError "Repository path missing on share: $repoRoot"
    }
}

if ($Result.repoRoot) {
    try {
        $pythonCmd = Install-PythonIfNeeded
        if (-not $pythonCmd) {
            throw "Python install failed."
        }
        $Result.pythonReady = $true

        if (-not (Test-Path (Join-Path $Result.repoRoot ".env"))) {
            Copy-Item (Join-Path $Result.repoRoot ".env.example") (Join-Path $Result.repoRoot ".env") -Force
        }

        Set-Location $Result.repoRoot

        if ($pythonCmd -eq "py") {
            & py -3 -m pip install -r requirements.txt
        } else {
            & python -m pip install -r requirements.txt
        }
        $Result.pipInstallOk = $true

        $env:EASY_CLAUDECODE_ROOT = $Result.repoRoot
        $env:CLAUDE_CONSOLE_ENABLE_OPENCLAW = "0"
        $env:CLAUDE_CONSOLE_PORT = "18882"

        Start-Process powershell -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", (Join-Path $Result.repoRoot "scripts\run-claude-console.ps1")
        ) -WorkingDirectory $Result.repoRoot -WindowStyle Hidden | Out-Null
        $Result.backendStarted = $true

        $statusUrl = "http://127.0.0.1:18882/claude-console/status"
        $bootstrapUrl = "http://127.0.0.1:18882/claude-console/bootstrap"

        for ($i = 0; $i -lt 30; $i++) {
            try {
                $status = Invoke-HealthJson $statusUrl
                if ($status.StatusCode -ge 200 -and $status.StatusCode -lt 300) {
                    $Result.statusOk = $true
                    break
                }
            } catch {
            }
            Start-Sleep -Seconds 2
        }

        if ($Result.statusOk) {
            try {
                $bootstrap = Invoke-HealthJson $bootstrapUrl
                if ($bootstrap.StatusCode -ge 200 -and $bootstrap.StatusCode -lt 300) {
                    $Result.bootstrapOk = $true
                }
            } catch {
                Add-ResultError "Bootstrap endpoint failed: $($_.Exception.Message)"
            }
        } else {
            Add-ResultError "Status endpoint never became healthy."
        }
    } catch {
        Add-ResultError $_.Exception.Message
    }
}

$Result.finishedAt = (Get-Date).ToString("o")
$Result.ok = ($Result.repoRoot -and $Result.pythonReady -and $Result.pipInstallOk -and $Result.backendStarted -and $Result.statusOk -and $Result.bootstrapOk)

$json = ($Result | ConvertTo-Json -Depth 8)

if ($Result.shareRoot) {
    $resultFile = Join-Path $Result.shareRoot "vm-validation-result.json"
    Set-Content -Path $resultFile -Value $json -Encoding UTF8
} else {
    Set-Content -Path "C:\OEM\vm-validation-result.json" -Value $json -Encoding UTF8
}
