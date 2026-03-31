$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PythonBin = (Resolve-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")).Path

@'
import os
import sys
import tempfile
from pathlib import Path

repo_root = Path(sys.argv[1])
temp_root = Path(tempfile.mkdtemp(prefix="easy-claudecode-direct-reply-route-"))
env_file = temp_root / ".env"
env_file.write_text((repo_root / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
os.environ["EASY_CLAUDECODE_ENV_FILE"] = str(env_file)
os.environ["EASY_CLAUDECODE_HOME"] = str(temp_root / ".easy-home")

sys.path.insert(0, str(repo_root / "services" / "backend"))
import app  # noqa: E402

prompt = "Please reply with exactly: minimax-direct-reply"
prepared = app._prepare_claude_prompt(prompt, "compatible-coding,MiniMax-M2.7-highspeed", "none")

assert prepared.startswith("[route:compatible-coding,MiniMax-M2.7-highspeed]"), prepared
assert "minimax-direct-reply" in prepared, prepared
print(prepared)
'@ | & $PythonBin - $RepoRoot
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
