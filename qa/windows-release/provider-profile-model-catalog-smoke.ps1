$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PythonBin = (Resolve-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")).Path

@'
import os
import sys
import tempfile
from pathlib import Path

repo_root = Path(sys.argv[1])
temp_root = Path(tempfile.mkdtemp(prefix="easy-claudecode-provider-profile-"))
env_file = temp_root / ".env"
env_file.write_text((repo_root / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
with env_file.open("a", encoding="utf-8") as fh:
    fh.write("CODING_COMPATIBLE_UPSTREAM=https://api.minimaxi.com/anthropic/v1/messages\n")
os.environ["EASY_CLAUDECODE_ENV_FILE"] = str(env_file)
os.environ["EASY_CLAUDECODE_HOME"] = str(temp_root / ".easy-home")

sys.path.insert(0, str(repo_root / "services" / "backend"))
import app  # noqa: E402

client = app.app.test_client()
payload = client.get("/claude-console/settings").get_json()
catalog = payload.get("modelCatalog") or []
labels = " | ".join(str(item.get("label") or "") for item in catalog if isinstance(item, dict))

assert any(str(item.get("model") or "") == "MiniMax-M2.7" for item in catalog), labels
assert any(str(item.get("model") or "") == "MiniMax-M2.7-highspeed" for item in catalog), labels
assert all(str(item.get("model") or "") not in {"glm-5", "qwen3-max-2026-01-23", "kimi-k2.5"} for item in catalog), labels
print(labels)
'@ | & $PythonBin - $RepoRoot
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
