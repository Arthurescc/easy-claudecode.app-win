$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = if ($env:EASY_CLAUDECODE_ROOT) { $env:EASY_CLAUDECODE_ROOT } else { (Resolve-Path (Join-Path $ScriptDir "..")).Path }
$EnvFile = if ($env:EASY_CLAUDECODE_ENV_FILE) { $env:EASY_CLAUDECODE_ENV_FILE } else { Join-Path $RepoRoot ".env" }

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $Line = $_.Trim()
        if (-not $Line -or $Line.StartsWith("#") -or $Line.IndexOf("=") -lt 1) {
            return
        }
        $Parts = $Line -split "=", 2
        $Key = $Parts[0].Trim()
        $Value = $Parts[1].Trim()
        if (($Value.StartsWith('"') -and $Value.EndsWith('"')) -or ($Value.StartsWith("'") -and $Value.EndsWith("'"))) {
            $Value = $Value.Substring(1, $Value.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($Key, $Value, "Process")
    }
}

$HomeDir = $HOME
$EasyHome = if ($env:EASY_CLAUDECODE_HOME) { $env:EASY_CLAUDECODE_HOME } else { Join-Path $HomeDir ".easy-claudecode" }
$RouterRuntime = if ($env:CLAUDE_ROUTER_RUNTIME_DIR) { $env:CLAUDE_ROUTER_RUNTIME_DIR } else { Join-Path $EasyHome "router" }

$env:EASY_CLAUDECODE_ROOT = $RepoRoot
$env:EASY_CLAUDECODE_ENV_FILE = $EnvFile
$env:EASY_CLAUDECODE_HOME = $EasyHome
$env:CLAUDE_CONSOLE_SOURCE_ROOT = if ($env:CLAUDE_CONSOLE_SOURCE_ROOT) { $env:CLAUDE_CONSOLE_SOURCE_ROOT } else { $RepoRoot }
$env:CLAUDE_CONSOLE_FRONTEND_ROOT = if ($env:CLAUDE_CONSOLE_FRONTEND_ROOT) { $env:CLAUDE_CONSOLE_FRONTEND_ROOT } else { Join-Path $RepoRoot "apps\web" }
$env:CLAUDE_CONSOLE_RUNTIME_ROOT = if ($env:CLAUDE_CONSOLE_RUNTIME_ROOT) { $env:CLAUDE_CONSOLE_RUNTIME_ROOT } else { Join-Path $EasyHome "runtime\claude-console" }
$env:CLAUDE_CONSOLE_UPLOAD_ROOT = if ($env:CLAUDE_CONSOLE_UPLOAD_ROOT) { $env:CLAUDE_CONSOLE_UPLOAD_ROOT } else { Join-Path $EasyHome "uploads" }
$env:CLAUDE_CHAT_META_FILE = if ($env:CLAUDE_CHAT_META_FILE) { $env:CLAUDE_CHAT_META_FILE } else { Join-Path $EasyHome "claude-chat-meta.json" }
$env:CLAUDE_CONSOLE_LOG_ROOT = if ($env:CLAUDE_CONSOLE_LOG_ROOT) { $env:CLAUDE_CONSOLE_LOG_ROOT } else { Join-Path $EasyHome "logs" }
$env:CLAUDE_ROUTER_SOURCE_DIR = if ($env:CLAUDE_ROUTER_SOURCE_DIR) { $env:CLAUDE_ROUTER_SOURCE_DIR } else { Join-Path $RepoRoot "config\router" }
$env:CLAUDE_ROUTER_RUNTIME_DIR = $RouterRuntime
$env:CLAUDE_ROUTER_CONFIG_FILE = if ($env:CLAUDE_ROUTER_CONFIG_FILE) { $env:CLAUDE_ROUTER_CONFIG_FILE } else { Join-Path $RouterRuntime "config.json" }
$env:CLAUDE_ROUTER_CUSTOM_FILE = if ($env:CLAUDE_ROUTER_CUSTOM_FILE) { $env:CLAUDE_ROUTER_CUSTOM_FILE } else { Join-Path $RouterRuntime "custom-router.js" }
$env:CLAUDE_CONSOLE_HOST = if ($env:CLAUDE_CONSOLE_HOST) { $env:CLAUDE_CONSOLE_HOST } else { "127.0.0.1" }
$env:CLAUDE_CONSOLE_PORT = if ($env:CLAUDE_CONSOLE_PORT) { $env:CLAUDE_CONSOLE_PORT } else { "18882" }
$env:CLAUDE_ROUTER_HEALTH_URL = if ($env:CLAUDE_ROUTER_HEALTH_URL) { $env:CLAUDE_ROUTER_HEALTH_URL } else { "http://127.0.0.1:3456/health" }
$env:CLAUDE_PROXY_HEALTH_URL = if ($env:CLAUDE_PROXY_HEALTH_URL) { $env:CLAUDE_PROXY_HEALTH_URL } else { "http://127.0.0.1:3460/health" }
$env:CLAUDE_WEB_PERMISSION_MODE = if ($env:CLAUDE_WEB_PERMISSION_MODE) { $env:CLAUDE_WEB_PERMISSION_MODE } else { "bypassPermissions" }
$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = if ($env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS) { $env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS } else { "1" }
$env:CLAUDE_WORKSPACE_ROOT = if ($env:CLAUDE_WORKSPACE_ROOT) { $env:CLAUDE_WORKSPACE_ROOT } else { $RepoRoot }
$env:CLAUDE_WRAPPER_PATH = if ($env:CLAUDE_WRAPPER_PATH) { $env:CLAUDE_WRAPPER_PATH } else { Join-Path $RepoRoot "scripts\claude-local-router.cmd" }
$env:CLAUDE_REAL_BIN = if ($env:CLAUDE_REAL_BIN) { $env:CLAUDE_REAL_BIN } else { "claude" }
$env:CLAUDE_EXTRA_ALLOWED_DIRS = if ($env:CLAUDE_EXTRA_ALLOWED_DIRS) { $env:CLAUDE_EXTRA_ALLOWED_DIRS } else { "$RepoRoot,$HomeDir\Desktop" }
$env:NODE_PATH = if ($env:NODE_PATH) { $env:NODE_PATH } else { Join-Path $RepoRoot "node_modules" }
$env:NO_PROXY = "127.0.0.1,localhost"
$env:no_proxy = "127.0.0.1,localhost"

foreach ($ProxyKey in @("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy")) {
    Remove-Item "Env:$ProxyKey" -ErrorAction SilentlyContinue
}

foreach ($Dir in @($EasyHome, $env:CLAUDE_CONSOLE_LOG_ROOT, $env:CLAUDE_CONSOLE_UPLOAD_ROOT, $RouterRuntime)) {
    if ($Dir) {
        New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    }
}
