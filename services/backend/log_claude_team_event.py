#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import select
import sys
import time
from pathlib import Path


LOG_PATH = Path(
    os.path.expanduser(
        os.getenv("CLAUDE_TEAM_EVENT_LOG_PATH", "~/.easy-claudecode/logs/agent-team-events.jsonl")
    )
)
SAFE_ENV_KEYS = {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_PROJECT_DIR",
    "CLAUDE_SESSION_ID",
    "PWD",
    "TMUX",
    "TERM",
}


def read_stdin_nonblocking() -> str:
    try:
        if select.select([sys.stdin], [], [], 0.15)[0]:
            return sys.stdin.read()
    except Exception:
        return ""
    return ""


def main() -> int:
    event_name = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    raw = read_stdin_nonblocking().strip()
    payload = None
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
    record = {
        "ts": int(time.time()),
        "event": event_name,
        "argv": sys.argv[1:],
        "cwd": os.getcwd(),
        "pid": os.getpid(),
        "env": {key: os.environ.get(key, "") for key in SAFE_ENV_KEYS if os.environ.get(key)},
    }
    if payload is not None:
        record["payload"] = payload
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
