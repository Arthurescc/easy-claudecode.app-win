#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common-env.sh"

NODE_BIN="${NODE_BIN:-$(command -v node || true)}"
if [[ -z "$NODE_BIN" ]]; then
  echo "node binary not found in PATH" >&2
  exit 1
fi

PROXY_SCRIPT="${CLAUDE_DASHSCOPE_PROXY_SCRIPT:-$CLAUDE_CONSOLE_RUNTIME_ROOT/services/backend/claude_code_dashscope_proxy.js}"
export NODE_PATH="${NODE_PATH:-$EASY_CLAUDECODE_ROOT/node_modules}"
"$SCRIPT_DIR/sync-runtime.sh"
exec "$NODE_BIN" "$PROXY_SCRIPT"
