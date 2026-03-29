$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

New-Item -ItemType Directory -Force -Path $env:CLAUDE_ROUTER_RUNTIME_DIR | Out-Null
Copy-Item (Join-Path $env:CLAUDE_ROUTER_SOURCE_DIR "custom-router.js") $env:CLAUDE_ROUTER_CUSTOM_FILE -Force

$PythonBin = if ($env:CLAUDE_CONSOLE_PYTHON_BIN) { $env:CLAUDE_CONSOLE_PYTHON_BIN } else { "python" }
$SourceConfig = Join-Path $env:CLAUDE_ROUTER_SOURCE_DIR "config.example.json"
$TargetConfig = $env:CLAUDE_ROUTER_CONFIG_FILE
$CustomRouter = $env:CLAUDE_ROUTER_CUSTOM_FILE

@'
import json
import os
import sys

src, dst, custom = sys.argv[1:4]
with open(src, "r", encoding="utf-8") as fh:
    data = json.load(fh)
data["CUSTOM_ROUTER_PATH"] = custom
for provider in data.get("Providers", []):
    if not isinstance(provider, dict):
        continue
    env_url = str(provider.get("api_base_url") or "").strip()
    if env_url.startswith("$"):
        provider["api_base_url"] = os.getenv(env_url[1:], "")
with open(dst, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
'@ | & $PythonBin - $SourceConfig $TargetConfig $CustomRouter
