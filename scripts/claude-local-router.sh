#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common-env.sh"

REAL_CLAUDE_BIN="${CLAUDE_REAL_BIN:-$(command -v claude || true)}"
if [[ -z "$REAL_CLAUDE_BIN" ]]; then
  echo "claude binary not found in PATH" >&2
  exit 1
fi

export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://127.0.0.1:3456}"
export ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-easy-claudecode-local-router}"

exec "$REAL_CLAUDE_BIN" "$@"
