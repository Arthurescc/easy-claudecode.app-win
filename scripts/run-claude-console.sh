#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common-env.sh"

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
if [[ -n "${CLAUDE_CONSOLE_PYTHON:-}" && -z "${CLAUDE_CONSOLE_PYTHON_BIN:-}" ]]; then
  export CLAUDE_CONSOLE_PYTHON_BIN="$CLAUDE_CONSOLE_PYTHON"
fi
export CLAUDE_CONSOLE_PYTHON_BIN="${CLAUDE_CONSOLE_PYTHON_BIN:-$(command -v python3)}"
if [[ "$CLAUDE_CONSOLE_PYTHON_BIN" != /* ]]; then
  export CLAUDE_CONSOLE_PYTHON_BIN="$(cd "$PWD" && pwd)/$CLAUDE_CONSOLE_PYTHON_BIN"
fi

"$SCRIPT_DIR/sync-runtime.sh"
"$SCRIPT_DIR/sync-router.sh"

if [[ ! -x "$CLAUDE_CONSOLE_PYTHON_BIN" ]]; then
  echo "Python runtime not found: $CLAUDE_CONSOLE_PYTHON_BIN" >&2
  exit 1
fi

"$CLAUDE_CONSOLE_PYTHON_BIN" - <<'PY' >/dev/null 2>&1 || {
import importlib
for name in ("flask", "werkzeug"):
    importlib.import_module(name)
PY
  echo "Missing Python dependencies. Install them with: pip install -r requirements.txt" >&2
  exit 1
}

cd "$CLAUDE_CONSOLE_RUNTIME_ROOT"
exec "$CLAUDE_CONSOLE_PYTHON_BIN" "$CLAUDE_CONSOLE_RUNTIME_ROOT/services/backend/app.py"
