$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PythonBin = (Resolve-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")).Path

@'
import json
import os
import sys
import tempfile
from pathlib import Path

repo_root = Path(sys.argv[1])
temp_root = Path(tempfile.mkdtemp(prefix="easy-claudecode-settings-route-"))
env_file = temp_root / ".env"
env_file.write_text((repo_root / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
os.environ["EASY_CLAUDECODE_ENV_FILE"] = str(env_file)
os.environ["EASY_CLAUDECODE_HOME"] = str(temp_root / ".easy-home")

sys.path.insert(0, str(repo_root / "services" / "backend"))
import app  # noqa: E402

app._sync_router_runtime = lambda: {"ok": True, "mocked": True}
client = app.app.test_client()

settings = client.get("/claude-console/settings")
payload = settings.get_json()
assert settings.status_code == 200, settings.status_code
assert "EASY_CLAUDECODE_DEFAULT_ROUTE" in payload["values"], payload["values"]
assert payload.get("routeOptions"), payload

chosen_route = "compatible-coding,MiniMax-M2.5"
response = client.post(
    "/claude-console/settings",
    json={
        "values": {
            "CODING_COMPATIBLE_API_KEY": "",
            "ANTHROPIC_THINKING_API_KEY": "",
            "CODING_COMPATIBLE_UPSTREAM": "https://api.minimaxi.com/anthropic/v1/messages",
            "ANTHROPIC_THINKING_UPSTREAM": "https://aicodelink.shop/v1/messages",
            "CLAUDE_ROUTER_HEALTH_URL": "http://127.0.0.1:3456/health",
            "CLAUDE_PROXY_HEALTH_URL": "http://127.0.0.1:3460/health",
            "CLAUDE_CONSOLE_LOCALE": "zh-CN",
            "EASY_CLAUDECODE_DEFAULT_ROUTE": chosen_route,
        }
    },
)
updated = response.get_json()
assert response.status_code == 200, response.status_code
assert updated["values"]["EASY_CLAUDECODE_DEFAULT_ROUTE"] == chosen_route, updated
print(chosen_route)
'@ | & $PythonBin - $RepoRoot
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
