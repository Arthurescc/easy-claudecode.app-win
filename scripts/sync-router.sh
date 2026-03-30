#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common-env.sh"

mkdir -p "$CLAUDE_ROUTER_RUNTIME_DIR"
cp "$CLAUDE_ROUTER_SOURCE_DIR/custom-router.js" "$CLAUDE_ROUTER_RUNTIME_DIR/custom-router.js"
CLAUDE_SETTINGS_FILE="$HOME/.claude/settings.json"
CCR_HOME_DIR="$HOME/.claude-code-router"
CCR_CONFIG_FILE="$CCR_HOME_DIR/config.json"
CCR_CUSTOM_ROUTER_FILE="$CCR_HOME_DIR/custom-router.js"

python3 - "$CLAUDE_ROUTER_SOURCE_DIR/config.example.json" "$CLAUDE_ROUTER_RUNTIME_DIR/config.json" "$CLAUDE_ROUTER_RUNTIME_DIR/custom-router.js" "$CLAUDE_SETTINGS_FILE" <<'PY'
import json
import os
import sys
src, dst, custom, settings_path = sys.argv[1:5]
data = json.load(open(src, "r", encoding="utf-8"))
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
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
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
PY

mkdir -p "$CCR_HOME_DIR"
cp "$CLAUDE_ROUTER_RUNTIME_DIR/config.json" "$CCR_CONFIG_FILE"
cp "$CLAUDE_ROUTER_RUNTIME_DIR/custom-router.js" "$CCR_CUSTOM_ROUTER_FILE"
