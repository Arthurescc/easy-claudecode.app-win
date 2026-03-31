$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PythonBin = (Resolve-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")).Path

@'
import os
import sys
import tempfile
from pathlib import Path

repo_root = Path(sys.argv[1])
temp_root = Path(tempfile.mkdtemp(prefix="easy-claudecode-provider-registry-"))
env_file = temp_root / ".env"
env_file.write_text((repo_root / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
os.environ["EASY_CLAUDECODE_ENV_FILE"] = str(env_file)
os.environ["EASY_CLAUDECODE_HOME"] = str(temp_root / ".easy-home")

sys.path.insert(0, str(repo_root / "services" / "backend"))
import app  # noqa: E402

client = app.app.test_client()
payload = client.get("/claude-console/settings").get_json()

assert payload["ok"] is True, payload
assert payload.get("providers"), payload
assert payload.get("routeOptions"), payload
assert "CODING_COMPATIBLE_API_KEY" in payload["values"], payload["values"]
assert "CODING_COMPATIBLE_UPSTREAM" in payload["values"], payload["values"]

provider_labels = " ".join(str(item.get("displayName") or "") for item in payload["providers"] if isinstance(item, dict))
assert provider_labels, payload["providers"]
assert "DashScope" not in provider_labels, provider_labels
print(provider_labels)
'@ | & $PythonBin - $RepoRoot
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
