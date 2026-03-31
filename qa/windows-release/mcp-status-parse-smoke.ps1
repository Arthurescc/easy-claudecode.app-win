$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PythonBin = (Resolve-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")).Path

@'
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend")
import app  # noqa: E402


with tempfile.TemporaryDirectory() as tmpdir:
    settings_path = Path(tmpdir) / "claude.json"
    settings_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "context7": {"command": "npm", "args": ["exec", "--yes", "--", "@upstash/context7-mcp@latest"]},
                    "memory": {"command": "npm", "args": ["exec", "--yes", "--", "@modelcontextprotocol/server-memory"]},
                }
            }
        ),
        encoding="utf-8",
    )

    original_settings = app.CLAUDE_USER_SETTINGS_FILE
    original_resolve = app._resolve_real_claude_bin
    original_run_capture = app._run_capture
    app.CLAUDE_USER_SETTINGS_FILE = str(settings_path)
    app._resolve_real_claude_bin = lambda: (True, "claude")
    app._run_capture = lambda *args, **kwargs: {
        "ok": True,
        "returncode": 0,
        "stdout": (
            "Checking MCP server health...\n"
            "context7: npm exec -- @upstash/context7-mcp@latest - ✓ Connected\n"
            "memory: npm exec -- @modelcontextprotocol/server-memory - ✗ Failed to connect\n"
        ),
        "stderr": "",
    }

    try:
        items = {item["id"]: item for item in app._read_mcp_servers()}
    finally:
        app.CLAUDE_USER_SETTINGS_FILE = original_settings
        app._resolve_real_claude_bin = original_resolve
        app._run_capture = original_run_capture

assert items["context7"]["status"] == "connected", items
assert items["memory"]["status"] == "failed", items
print("mcp status parsing ok")
'@ | & $PythonBin -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
