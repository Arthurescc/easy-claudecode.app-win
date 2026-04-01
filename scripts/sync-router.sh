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
DEFAULT_ALLOWED_TOOLS = [
    "Bash",
    "Read",
    "Edit",
    "Write",
    "MultiEdit",
    "Glob",
    "Grep",
    "LS",
    "WebFetch",
    "WebSearch",
    "Task",
    "TodoRead",
    "TodoWrite",
    "NotebookRead",
    "NotebookEdit",
]
AUTO_PERMISSION_SUPPORTED_MODEL_PREFIXES = ("claude-sonnet-4-6", "claude-opus-4-6")

def split_route_id(route_id: str):
    route_text = str(route_id or "").strip()
    if not route_text:
        return "", ""
    provider_name, _, model_name = route_text.partition(",")
    return provider_name.strip(), model_name.strip()

def resolve_permission_default(route_id: str, settings: dict):
    effective_model = str(route_id or settings.get("model") or "").strip()
    provider_name, model_name = split_route_id(effective_model)
    if provider_name:
        provider = next(
            (
                item
                for item in data.get("Providers", [])
                if isinstance(item, dict) and str(item.get("name") or "").strip() == provider_name
            ),
            None,
        )
        upstream = str(provider.get("api_base_url") or "").strip().lower() if isinstance(provider, dict) else ""
        if "api.anthropic.com" in upstream and str(model_name or "").strip().lower().startswith(AUTO_PERMISSION_SUPPORTED_MODEL_PREFIXES):
            return "auto"
        return "acceptEdits"
    if effective_model.lower().startswith(AUTO_PERMISSION_SUPPORTED_MODEL_PREFIXES):
        return "auto"
    return "acceptEdits"

def merge_unique_strings(existing, additions):
    ordered = []
    seen = set()
    for source in (existing or []), (additions or []):
        for item in source:
            value = str(item or "").strip()
            if value and value not in seen:
                ordered.append(value)
                seen.add(value)
    return ordered

def extra_allowed_directories():
    items = []
    for raw in str(os.getenv("CLAUDE_EXTRA_ALLOWED_DIRS", "") or "").split(","):
        candidate = str(raw or "").strip()
        if candidate:
            items.append(candidate)
    workspace_root = str(os.getenv("CLAUDE_WORKSPACE_ROOT", "") or "").strip()
    if workspace_root:
        items.append(workspace_root)
    repo_root = str(os.getenv("EASY_CLAUDECODE_ROOT", "") or "").strip()
    if repo_root:
        items.append(repo_root)
    return merge_unique_strings([], items)

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
else:
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as fh:
                settings = json.load(fh)
        except Exception:
            settings = {}
permissions = settings.get("permissions") if isinstance(settings.get("permissions"), dict) else {}
permissions["defaultMode"] = resolve_permission_default(resolved_default_route, settings)
permissions["allow"] = merge_unique_strings(permissions.get("allow"), DEFAULT_ALLOWED_TOOLS)
permissions["additionalDirectories"] = merge_unique_strings(
    permissions.get("additionalDirectories"),
    extra_allowed_directories(),
)
settings["permissions"] = permissions
with open(settings_path, "w", encoding="utf-8") as fh:
    json.dump(settings, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

mkdir -p "$CCR_HOME_DIR"
cp "$CLAUDE_ROUTER_RUNTIME_DIR/config.json" "$CCR_CONFIG_FILE"
cp "$CLAUDE_ROUTER_RUNTIME_DIR/custom-router.js" "$CCR_CUSTOM_ROUTER_FILE"
