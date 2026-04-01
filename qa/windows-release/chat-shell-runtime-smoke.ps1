$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PreferredPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PythonBin = $null

if (Test-Path $PreferredPython) {
    try {
        & $PreferredPython -c "import flask" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PythonBin = $PreferredPython
        }
    } catch {
    }
}

if (-not $PythonBin) {
    $PythonBin = (Get-Command python -ErrorAction Stop).Source
}

$env:CHAT_SHELL_REPO_ROOT = $RepoRoot

@'
import os
import sys

repo_root = os.environ["CHAT_SHELL_REPO_ROOT"]
sys.path.insert(0, os.path.join(repo_root, "services", "backend"))
import app  # noqa: E402

payload = app._build_status(force_refresh=True)
shell = payload.get("chatShell") or {}

assert shell, payload
assert "contextUsage" in shell, shell
assert "slashSections" in shell, shell
assert "permissionDefault" in shell, shell
assert payload.get("webDefaults", {}).get("permissionMode") == shell["permissionDefault"], payload.get("webDefaults")
assert payload.get("webDefaults", {}).get("requestedPermissionMode") in {"", "auto", "default", "acceptEdits", "bypassPermissions", "dontAsk", "plan"}, payload.get("webDefaults")
assert any(str(item.get("id") or "") == "skills" for item in shell.get("slashSections") or []), shell
assert any(str(item.get("id") or "") == "mcp" for item in shell.get("slashSections") or []), shell
assert any(str(item.get("id") or "") == "brainstorming" for item in (payload.get("library", {}) or {}).get("skills", []) or app._build_library(force_refresh=True).get("skills", [])), "brainstorming skill should be preinstalled"

assert app._claude_normalize_permission_mode("default") == "default"
assert app._claude_normalize_permission_mode("") == "auto"

auto_args = []
app._claude_append_permission_flags(auto_args, "auto")
assert auto_args == ["--enable-auto-mode", "--permission-mode", "auto"], auto_args

default_args = []
app._claude_append_permission_flags(default_args, "default")
assert default_args == ["--permission-mode", "default"], default_args

shell_prompt = app._apply_shell_selections_to_prompt(
    "Ship the fix",
    [
        {"sectionId": "reasoning", "label": "Reasoning High"},
        {"sectionId": "skills", "label": "Brainstorming"},
        {"sectionId": "mcp", "label": "Context7"},
    ],
)
assert "Reasoning preference: Reasoning High." in shell_prompt
assert "If relevant, use these skills: Brainstorming." in shell_prompt
assert "If relevant, use these MCP servers: Context7." in shell_prompt
assert shell_prompt.endswith("User request:\nShip the fix"), shell_prompt

client = app.app.test_client()
original_run_capture = app._claude_run_capture
original_open_terminal_script = app._open_terminal_script
original_resolve_agent_name = app._resolve_agent_name
try:
    app._claude_run_capture = lambda *args, **kwargs: {
        "ok": True,
        "stdout": "ok",
        "stderr": "",
        "returncode": 0,
        "timedOut": False,
        "transport": "compat",
        "transportError": "",
    }
    response = client.post(
        "/claude-console/quick-run",
        json={
            "prompt": "Ship the fix",
            "shellSelections": [
                {"sectionId": "reasoning", "label": "Reasoning High"},
                {"sectionId": "skills", "label": "Brainstorming"},
            ],
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    quick_run_payload = response.get_json()
    assert "Reasoning preference: Reasoning High." in str(quick_run_payload.get("preparedPrompt") or "")
    assert "If relevant, use these skills: Brainstorming." in str(quick_run_payload.get("preparedPrompt") or "")

    captured = {}
    app._open_terminal_script = lambda script_path: {"ok": True, "scriptPath": script_path}
    original_write_terminal_script = app._write_terminal_script
    app._write_terminal_script = lambda mode, prompt, continue_latest, session_id="", agent_mode="auto", permission_mode=app.CLAUDE_WEB_PERMISSION_MODE, **kwargs: captured.update({
        "mode": mode,
        "prompt": prompt,
        "continueLatest": continue_latest,
        "sessionId": session_id,
        "agentMode": agent_mode,
        "permissionMode": permission_mode,
        "preparedPromptOverride": kwargs.get("prepared_prompt_override"),
        "agentPrompt": kwargs.get("agent_prompt"),
    }) or "captured-script"
    response = client.post(
        "/claude-console/open-session",
        json={
            "prompt": "Continue in terminal",
            "shellSelections": [
                {"sectionId": "personality", "label": "Collaborative"},
                {"sectionId": "plan", "label": "Plan Mode"},
            ],
            "sessionId": "",
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    assert "Response personality: Collaborative." in str(captured.get("preparedPromptOverride") or "")
    assert "Plan behavior: Plan Mode." in str(captured.get("preparedPromptOverride") or "")
    assert captured.get("agentPrompt") == "Continue in terminal", captured

    observed = {}
    app._write_terminal_script = original_write_terminal_script
    app._resolve_agent_name = lambda agent_mode, prompt, mode="auto": observed.setdefault("prompt", prompt) or ""
    script_path = app._write_terminal_script(
        "auto",
        "Raw prompt",
        False,
        "",
        "auto",
        "auto",
        prepared_prompt_override=app._apply_shell_selections_to_prompt(
            "Raw prompt",
            [{"sectionId": "mcp", "label": "Context7"}],
        ),
        agent_prompt="Raw prompt",
    )
    assert observed.get("prompt") == "Raw prompt", observed
    if os.path.exists(script_path):
        os.remove(script_path)
finally:
    app._claude_run_capture = original_run_capture
    app._open_terminal_script = original_open_terminal_script
    app._resolve_agent_name = original_resolve_agent_name
    if 'original_write_terminal_script' in locals():
        app._write_terminal_script = original_write_terminal_script

original_permission_default = app.CLAUDE_WEB_PERMISSION_MODE
original_model_reader = app._read_claude_settings_model
try:
    app.CLAUDE_WEB_PERMISSION_MODE = "auto"
    app._read_claude_settings_model = lambda: "compatible-coding,MiniMax-M2.7"
    payload = app._build_status(force_refresh=True)
    shell = payload.get("chatShell") or {}
    assert shell.get("permissionDefault") == "acceptEdits", shell
    assert payload.get("webDefaults", {}).get("permissionMode") == "acceptEdits", payload.get("webDefaults")
    assert payload.get("webDefaults", {}).get("requestedPermissionMode") == "auto", payload.get("webDefaults")
    assert payload.get("webDefaults", {}).get("permissionModeReason") == "auto_unsupported", payload.get("webDefaults")
finally:
    app.CLAUDE_WEB_PERMISSION_MODE = original_permission_default
    app._read_claude_settings_model = original_model_reader

print("chat shell runtime ok")
'@ | & $PythonBin -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
