$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PythonBin = (Resolve-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")).Path

@'
import os
import sys
import tempfile
from pathlib import Path

repo_root = Path(sys.argv[1])
temp_root = Path(tempfile.mkdtemp(prefix="easy-claudecode-model-probe-"))
env_file = temp_root / ".env"
env_file.write_text((repo_root / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
os.environ["EASY_CLAUDECODE_ENV_FILE"] = str(env_file)
os.environ["EASY_CLAUDECODE_HOME"] = str(temp_root / ".easy-home")

sys.path.insert(0, str(repo_root / "services" / "backend"))
import app  # noqa: E402

app._probe_model_access = lambda route_id, force_refresh=False: {
    "ok": True,
    "routeId": route_id,
    "supported": False,
    "reason": "plan_unsupported",
    "errorCode": "2061",
}
client = app.app.test_client()
response = client.post("/claude-console/models/probe", json={"routeId": "compatible-coding,MiniMax-M2.7-highspeed"})
payload = response.get_json()

assert response.status_code == 200, response.status_code
assert payload["supported"] is False, payload
assert payload["reason"] == "plan_unsupported", payload
assert payload["errorCode"] == "2061", payload
print(payload["reason"])
'@ | & $PythonBin - $RepoRoot
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
