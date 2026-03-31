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
assert shell["permissionDefault"] == "auto", shell
assert payload.get("webDefaults", {}).get("permissionMode") == shell["permissionDefault"], payload.get("webDefaults")
assert any(str(item.get("id") or "") == "skills" for item in shell.get("slashSections") or []), shell
assert any(str(item.get("id") or "") == "mcp" for item in shell.get("slashSections") or []), shell

assert app._claude_normalize_permission_mode("default") == "default"
assert app._claude_normalize_permission_mode("") == "auto"

auto_args = []
app._claude_append_permission_flags(auto_args, "auto")
assert auto_args == ["--enable-auto-mode", "--permission-mode", "auto"], auto_args

default_args = []
app._claude_append_permission_flags(default_args, "default")
assert default_args == ["--permission-mode", "default"], default_args

original_permission_default = app.CLAUDE_WEB_PERMISSION_MODE
try:
    app.CLAUDE_WEB_PERMISSION_MODE = "default"
    payload = app._build_status(force_refresh=True)
    shell = payload.get("chatShell") or {}
    assert shell.get("permissionDefault") == "default", shell
    assert payload.get("webDefaults", {}).get("permissionMode") == "default", payload.get("webDefaults")
finally:
    app.CLAUDE_WEB_PERMISSION_MODE = original_permission_default

print("chat shell runtime ok")
'@ | & $PythonBin -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
