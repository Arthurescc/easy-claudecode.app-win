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
import claude_console_utils as utils  # noqa: E402

workspace_root = r"C:\Users\Administrator\Documents\Playground"
claude_home = r"C:\Users\Administrator\.claude"
expected_slug = "C--Users-Administrator-Documents-Playground"
expected_project_dir = os.path.join(claude_home, "projects", expected_slug)

assert utils.project_slug_from_path(workspace_root) == expected_slug
assert utils.project_sessions_dir(claude_home, workspace_root) == expected_project_dir

fallback = app._resolve_permission_mode_request(
    "auto",
    "compatible-coding,MiniMax-M2.7",
    current_model="compatible-coding,MiniMax-M2.7",
)
assert fallback["requested"] == "auto", fallback
assert fallback["effective"] == "acceptEdits", fallback
assert fallback["reason"] == "auto_unsupported", fallback

official = app._resolve_permission_mode_request(
    "auto",
    "auto",
    current_model="claude-sonnet-4-6",
)
assert official["requested"] == "auto", official
assert official["effective"] == "auto", official
assert official["reason"] == "", official

original_permission_mode = app.CLAUDE_WEB_PERMISSION_MODE
original_model_reader = app._read_claude_settings_model
try:
    app.CLAUDE_WEB_PERMISSION_MODE = "auto"
    app._read_claude_settings_model = lambda: "compatible-coding,MiniMax-M2.7"
    payload = app._build_status(force_refresh=True)
    assert payload.get("webDefaults", {}).get("permissionMode") == "acceptEdits", payload.get("webDefaults")
    assert payload.get("chatShell", {}).get("permissionDefault") == "acceptEdits", payload.get("chatShell")
finally:
    app.CLAUDE_WEB_PERMISSION_MODE = original_permission_mode
    app._read_claude_settings_model = original_model_reader

print("session store permission policy ok")
'@ | & $PythonBin -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
