$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PythonBin = (Resolve-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")).Path

@'
import sys
from queue import Queue

sys.path.insert(0, r"C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend")
import claude_console_utils as u  # noqa: E402


class FakeProcess:
    def __init__(self):
        self._polled = False

    def poll(self):
        if not self._polled:
            self._polled = True
            return None
        return 0

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        return None

    def kill(self):
        return None


def json_line(event_type, payload):
    import json

    return json.dumps({"type": event_type, **payload}) + "\n"


def fake_spawn_stream_process(cmd, cwd):
    q = Queue()
    q.put(("pipe", json_line("system", {"subtype": "info", "message": "compat"})))
    q.put(("pipe", None))
    return FakeProcess(), q, "pipe", "pty unsupported on this platform"


original_spawn = u._spawn_stream_process
original_register = u.register_run
original_finish = u.finish_run
u._spawn_stream_process = fake_spawn_stream_process
u.register_run = lambda *args, **kwargs: None
u.finish_run = lambda *args, **kwargs: {}

try:
    events = list(u.stream_claude_session("claude", ".", "hello"))
finally:
    u._spawn_stream_process = original_spawn
    u.register_run = original_register
    u.finish_run = original_finish

messages = [str(item.get("message") or "") for item in events if isinstance(item, dict)]
assert not any("PTY" in message and "兼容" in message for message in messages), messages
print("compat notice suppressed")
'@ | & $PythonBin -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
