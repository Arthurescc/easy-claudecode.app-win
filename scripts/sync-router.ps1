$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

function Resolve-PythonBin {
    $candidates = @()
    if ($env:CLAUDE_CONSOLE_PYTHON_BIN) {
        $candidates += $env:CLAUDE_CONSOLE_PYTHON_BIN
    }
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $candidates += $pythonCommand.Source
    }
    foreach ($candidate in $candidates) {
        $text = [string]$(if ($null -ne $candidate) { $candidate } else { "" })
        $text = $text.Trim()
        if (-not $text) {
            continue
        }
        if (Test-Path $text) {
            return (Resolve-Path $text).Path
        }
    }
    throw "python executable not found for router sync"
}

New-Item -ItemType Directory -Force -Path $env:CLAUDE_ROUTER_RUNTIME_DIR | Out-Null
Copy-Item (Join-Path $env:CLAUDE_ROUTER_SOURCE_DIR "custom-router.js") $env:CLAUDE_ROUTER_CUSTOM_FILE -Force

$PythonBin = Resolve-PythonBin
$SourceConfig = Join-Path $env:CLAUDE_ROUTER_SOURCE_DIR "config.example.json"
$TargetConfig = $env:CLAUDE_ROUTER_CONFIG_FILE
$CustomRouter = $env:CLAUDE_ROUTER_CUSTOM_FILE
$ClaudeSettingsFile = Join-Path $HOME ".claude\settings.json"
$CcrHomeDir = Join-Path $HOME ".claude-code-router"
$CcrConfigFile = Join-Path $CcrHomeDir "config.json"
$CcrCustomRouterFile = Join-Path $CcrHomeDir "custom-router.js"
$RegistryFile = Join-Path $env:EASY_CLAUDECODE_ROOT "config\providers\registry.json"

@'
import json
import os
import sys

src, dst, custom, settings_path, registry_path = sys.argv[1:6]
with open(src, "r", encoding="utf-8") as fh:
    data = json.load(fh)
with open(registry_path, "r", encoding="utf-8") as fh:
    registry = json.load(fh)
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

registry_entries = [item for item in (registry.get("providers") or []) if isinstance(item, dict)]

def resolve_provider_entry(provider_name: str):
    normalized = str(provider_name or "").strip()
    for entry in registry_entries:
        if normalized == str(entry.get("id") or "").strip():
            return entry
        for legacy_id in entry.get("legacyIds") or []:
            if normalized == str(legacy_id or "").strip():
                return entry
    return None

def resolve_provider_profile(provider_name: str, upstream_url: str):
    entry = resolve_provider_entry(provider_name) or {}
    profiles = [item for item in (entry.get("profiles") or []) if isinstance(item, dict)]
    if not profiles:
        return {}
    upstream_lower = str(upstream_url or "").strip().lower()
    for profile in profiles:
        for matcher in profile.get("matchers") or []:
            needle = str(matcher or "").strip().lower()
            if needle and needle in upstream_lower:
                return profile
    return profiles[0]

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
for provider in data.get("Providers", []):
    if not isinstance(provider, dict):
        continue
    env_url = str(provider.get("api_base_url") or "").strip()
    if env_url.startswith("$"):
        provider["api_base_url"] = os.getenv(env_url[1:], "")
    profile = resolve_provider_profile(provider.get("name"), provider.get("api_base_url"))
    profile_models = [str(item or "").strip() for item in (profile.get("models") or []) if str(item or "").strip()]
    if profile_models:
        provider["models"] = profile_models

router_section = data.get("Router") if isinstance(data.get("Router"), dict) else {}
if default_route:
    for key in ("default", "background", "think", "longContext"):
        if isinstance(router_section, dict):
            router_section[key] = default_route
else:
    current_default = str(router_section.get("default") or "").strip()
    provider_name, _, current_model = current_default.partition(",")
    active_provider = next((item for item in data.get("Providers", []) if isinstance(item, dict) and str(item.get("name") or "").strip() == provider_name.strip()), None)
    active_models = [str(item or "").strip() for item in (active_provider.get("models") or [])] if isinstance(active_provider, dict) else []
    if active_models and current_model.strip() not in active_models:
        replacement_model = active_models[0]
        replacement_route = f"{provider_name.strip()},{replacement_model}".strip(",")
        for key in ("default", "background", "think", "longContext", "image"):
            value = str(router_section.get(key) or "").strip()
            route_provider, _, route_model = value.partition(",")
            if route_provider.strip() == provider_name.strip() and route_model.strip() not in active_models:
                router_section[key] = replacement_route
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
else:
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
    permissions = settings.get("permissions") if isinstance(settings.get("permissions"), dict) else {}
    permissions["defaultMode"] = resolve_permission_default("", settings)
    permissions["allow"] = merge_unique_strings(permissions.get("allow"), DEFAULT_ALLOWED_TOOLS)
    permissions["additionalDirectories"] = merge_unique_strings(
        permissions.get("additionalDirectories"),
        extra_allowed_directories(),
    )
    settings["permissions"] = permissions
    with open(settings_path, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
'@ | & $PythonBin - $SourceConfig $TargetConfig $CustomRouter $ClaudeSettingsFile $RegistryFile

New-Item -ItemType Directory -Force -Path $CcrHomeDir | Out-Null
Copy-Item $TargetConfig $CcrConfigFile -Force
Copy-Item $CustomRouter $CcrCustomRouterFile -Force
