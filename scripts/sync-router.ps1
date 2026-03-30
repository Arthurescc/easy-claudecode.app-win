$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

New-Item -ItemType Directory -Force -Path $env:CLAUDE_ROUTER_RUNTIME_DIR | Out-Null
Copy-Item (Join-Path $env:CLAUDE_ROUTER_SOURCE_DIR "custom-router.js") $env:CLAUDE_ROUTER_CUSTOM_FILE -Force

$PythonBin = if ($env:CLAUDE_CONSOLE_PYTHON_BIN) { $env:CLAUDE_CONSOLE_PYTHON_BIN } else { "python" }
$SourceConfig = Join-Path $env:CLAUDE_ROUTER_SOURCE_DIR "config.example.json"
$TargetConfig = $env:CLAUDE_ROUTER_CONFIG_FILE
$CustomRouter = $env:CLAUDE_ROUTER_CUSTOM_FILE
$ClaudeSettingsFile = Join-Path $HOME ".claude\settings.json"
$CcrHomeDir = Join-Path $HOME ".claude-code-router"
$CcrConfigFile = Join-Path $CcrHomeDir "config.json"
$CcrCustomRouterFile = Join-Path $CcrHomeDir "custom-router.js"

@'
import json
import os
import sys

src, dst, custom, settings_path = sys.argv[1:5]
with open(src, "r", encoding="utf-8") as fh:
    data = json.load(fh)
data["CUSTOM_ROUTER_PATH"] = custom
default_route = str(os.getenv("EASY_CLAUDECODE_DEFAULT_ROUTE", "") or "").strip()
if default_route:
    for key in ("default", "background", "think", "longContext"):
        if isinstance(data.get("Router"), dict):
            data["Router"][key] = default_route
for provider in data.get("Providers", []):
    if not isinstance(provider, dict):
        continue
    env_url = str(provider.get("api_base_url") or "").strip()
    if env_url.startswith("$"):
        provider["api_base_url"] = os.getenv(env_url[1:], "")
with open(dst, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

resolved_default_route = str(data.get("Router", {}).get("default") or "").strip()
if resolved_default_route:
    settings_dir = os.path.dirname(settings_path)
    if settings_dir:
        os.makedirs(settings_dir, exist_ok=True)
    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as fh:
                settings = json.load(fh)
        except Exception:
            settings = {}
    settings["model"] = resolved_default_route
    with open(settings_path, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
'@ | & $PythonBin - $SourceConfig $TargetConfig $CustomRouter $ClaudeSettingsFile

New-Item -ItemType Directory -Force -Path $CcrHomeDir | Out-Null
Copy-Item $TargetConfig $CcrConfigFile -Force
Copy-Item $CustomRouter $CcrCustomRouterFile -Force
