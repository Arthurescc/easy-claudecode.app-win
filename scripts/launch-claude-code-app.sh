#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common-env.sh"

URL="${CLAUDE_CONSOLE_URL:-http://127.0.0.1:${CLAUDE_CONSOLE_PORT}/claude-console}"
HEALTH_URL="${CLAUDE_CONSOLE_HEALTH_URL:-http://127.0.0.1:${CLAUDE_CONSOLE_PORT}/health}"
STATUS_URL="${CLAUDE_CONSOLE_STATUS_URL:-http://127.0.0.1:${CLAUDE_CONSOLE_PORT}/claude-console/status}"
LOG_FILE="${CLAUDE_CODE_APP_LOG_FILE:-$CLAUDE_CONSOLE_LOG_ROOT/claude-code-app-launcher.log}"
BACKEND_LOG="${CLAUDE_CODE_BACKEND_LOG_FILE:-$CLAUDE_CONSOLE_LOG_ROOT/claude-console-backend.log}"
ROUTER_LOG="${CLAUDE_CODE_ROUTER_LOG_FILE:-$CLAUDE_CONSOLE_LOG_ROOT/claude-code-router.log}"
PROXY_LOG="${CLAUDE_CODE_PROXY_LOG_FILE:-$CLAUDE_CONSOLE_LOG_ROOT/claude-code-proxy.log}"
SKIP_OPEN="${CLAUDE_CODE_SKIP_OPEN:-0}"

backend_ready() {
  /usr/bin/curl --noproxy '*' -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1 &&
    /usr/bin/curl --noproxy '*' -fsS --max-time 3 "$STATUS_URL" >/dev/null 2>&1
}

router_ready() {
  /usr/bin/curl --noproxy '*' -fsS --max-time 2 "$CLAUDE_ROUTER_HEALTH_URL" >/dev/null 2>&1
}

proxy_ready() {
  /usr/bin/curl --noproxy '*' -fsS --max-time 2 "$CLAUDE_PROXY_HEALTH_URL" >/dev/null 2>&1
}

{
  echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S')] launch requested"
  "$SCRIPT_DIR/sync-runtime.sh"
  "$SCRIPT_DIR/sync-router.sh"

  if ! router_ready; then
    echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S')] starting router"
    /usr/bin/nohup /bin/zsh "$SCRIPT_DIR/start-claude-code-router.sh" >> "$ROUTER_LOG" 2>&1 &
    /bin/sleep 1
  fi

  if ! proxy_ready; then
    echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S')] starting proxy"
    /usr/bin/nohup /bin/zsh "$SCRIPT_DIR/start-claude-code-dashscope-proxy.sh" >> "$PROXY_LOG" 2>&1 &
    /bin/sleep 1
  fi

  if ! backend_ready; then
    echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S')] starting backend"
    /usr/bin/nohup /bin/zsh "$SCRIPT_DIR/run-claude-console.sh" >> "$BACKEND_LOG" 2>&1 &
  fi

  ready=0
  for _ in $(/usr/bin/seq 1 20); do
    if backend_ready; then
      ready=1
      break
    fi
    /bin/sleep 1
  done
  echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S')] status_ready=$ready"

  if [[ "$SKIP_OPEN" == "1" ]]; then
    echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S')] browser_open_skipped=1"
  else
    /usr/bin/open "$URL"
  fi
} >> "$LOG_FILE" 2>&1
