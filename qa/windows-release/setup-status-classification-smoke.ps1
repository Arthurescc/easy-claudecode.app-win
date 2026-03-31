$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PythonBin = (Resolve-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")).Path
$env:SETUP_STATUS_REPO_ROOT = $RepoRoot

@'
import os
import sys

repo_root = os.environ["SETUP_STATUS_REPO_ROOT"]
sys.path.insert(0, os.path.join(repo_root, "services", "backend"))
import app  # noqa: E402


def build_case(*, values, auth_payload, library_counts, route_options):
    original_load = app._load_editable_settings
    original_capture = app._run_capture
    original_library = app._build_library
    original_routes = app._route_options

    def fake_run_capture(args, **kwargs):
        cmd = " ".join(str(part) for part in args)
        if "auth status" in cmd:
            return auth_payload
        if "--version" in cmd:
            return {"ok": True, "returncode": 0, "stdout": "2.1.87 (Claude Code)", "stderr": ""}
        return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}

    try:
        app._load_editable_settings = lambda: values
        app._run_capture = fake_run_capture
        app._build_library = lambda: {
            "counts": library_counts,
            "skills": [],
            "agents": [],
            "mcps": [],
            "automations": [],
        }
        app._route_options = lambda: route_options
        payload = app._build_status(force_refresh=True)
        return payload["setupStatus"]
    finally:
        app._load_editable_settings = original_load
        app._run_capture = original_capture
        app._build_library = original_library
        app._route_options = original_routes


custom_ready = build_case(
    values={
        "CODING_COMPATIBLE_API_KEY": "sk-test",
        "CODING_COMPATIBLE_UPSTREAM": "https://api.minimaxi.com/anthropic/v1/messages",
        "ANTHROPIC_THINKING_API_KEY": "",
        "ANTHROPIC_THINKING_UPSTREAM": "",
        "EASY_CLAUDECODE_DEFAULT_ROUTE": "compatible-coding,MiniMax-M2.7",
        "CLAUDE_ROUTER_HEALTH_URL": "http://127.0.0.1:3456/health",
        "CLAUDE_PROXY_HEALTH_URL": "http://127.0.0.1:3460/health",
        "CLAUDE_CONSOLE_LOCALE": "zh-CN",
    },
    auth_payload={"ok": False, "returncode": 1, "stdout": '{"loggedIn": false, "authMethod": "none"}', "stderr": ""},
    library_counts={"skills": 2, "agents": 1, "mcps": 0, "automations": 0},
    route_options=[{"id": "compatible-coding,MiniMax-M2.7", "label": "MiniMax-compatible · MiniMax M2.7"}],
)
assert custom_ready["isReady"] is True, custom_ready
assert custom_ready["customProviderReady"] is True, custom_ready
assert custom_ready["officialClaudeReady"] is False, custom_ready
assert custom_ready["recommendedPath"] == "custom-provider", custom_ready
assert custom_ready["shouldPromptSettings"] is False, custom_ready

official_ready = build_case(
    values={
        "CODING_COMPATIBLE_API_KEY": "",
        "CODING_COMPATIBLE_UPSTREAM": "",
        "ANTHROPIC_THINKING_API_KEY": "",
        "ANTHROPIC_THINKING_UPSTREAM": "",
        "EASY_CLAUDECODE_DEFAULT_ROUTE": "",
        "CLAUDE_ROUTER_HEALTH_URL": "http://127.0.0.1:3456/health",
        "CLAUDE_PROXY_HEALTH_URL": "http://127.0.0.1:3460/health",
        "CLAUDE_CONSOLE_LOCALE": "zh-CN",
    },
    auth_payload={"ok": True, "returncode": 0, "stdout": '{"loggedIn": true, "authMethod": "oauth"}', "stderr": ""},
    library_counts={"skills": 0, "agents": 0, "mcps": 0, "automations": 0},
    route_options=[],
)
assert official_ready["isReady"] is True, official_ready
assert official_ready["customProviderReady"] is False, official_ready
assert official_ready["officialClaudeReady"] is True, official_ready
assert official_ready["recommendedPath"] == "official-claude", official_ready
assert official_ready["shouldPromptSettings"] is False, official_ready

unconfigured = build_case(
    values={
        "CODING_COMPATIBLE_API_KEY": "",
        "CODING_COMPATIBLE_UPSTREAM": "",
        "ANTHROPIC_THINKING_API_KEY": "",
        "ANTHROPIC_THINKING_UPSTREAM": "",
        "EASY_CLAUDECODE_DEFAULT_ROUTE": "",
        "CLAUDE_ROUTER_HEALTH_URL": "http://127.0.0.1:3456/health",
        "CLAUDE_PROXY_HEALTH_URL": "http://127.0.0.1:3460/health",
        "CLAUDE_CONSOLE_LOCALE": "zh-CN",
    },
    auth_payload={"ok": False, "returncode": 1, "stdout": '{"loggedIn": false, "authMethod": "none"}', "stderr": ""},
    library_counts={"skills": 0, "agents": 0, "mcps": 0, "automations": 0},
    route_options=[],
)
assert unconfigured["isReady"] is False, unconfigured
assert unconfigured["customProviderReady"] is False, unconfigured
assert unconfigured["officialClaudeReady"] is False, unconfigured
assert unconfigured["recommendedPath"] == "settings", unconfigured
assert unconfigured["shouldPromptSettings"] is True, unconfigured

print("setup status classification ok")
'@ | & $PythonBin -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
