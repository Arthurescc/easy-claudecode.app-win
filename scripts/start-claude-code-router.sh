#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common-env.sh"

CCR_BIN="${CCR_BIN:-$(command -v ccr || true)}"
if [[ -z "$CCR_BIN" ]]; then
  echo "ccr binary not found in PATH" >&2
  exit 1
fi

"$SCRIPT_DIR/sync-router.sh"

if curl --noproxy '*' -fsS --max-time 2 "$CLAUDE_ROUTER_HEALTH_URL" >/dev/null 2>&1; then
  exit 0
fi

cd "$CLAUDE_ROUTER_RUNTIME_DIR"
exec "$CCR_BIN" start
