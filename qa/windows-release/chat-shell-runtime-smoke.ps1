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
assert any(str(item.get("id") or "") == "skills" for item in shell.get("slashSections") or []), shell
assert any(str(item.get("id") or "") == "mcp" for item in shell.get("slashSections") or []), shell

print("chat shell runtime ok")
'@ | & $PythonBin -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
