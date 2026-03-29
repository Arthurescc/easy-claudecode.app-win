#!/bin/zsh
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <project_dir> <composition_id> <output_path> [extra remotion args...]" >&2
  exit 64
fi

PROJECT_DIR="$(cd "$1" && pwd)"
COMPOSITION_ID="$2"
OUTPUT_PATH="$3"
shift 3

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "[remotion-wrapper] project not found: $PROJECT_DIR" >&2
  exit 66
fi

LOG_FILE="$(mktemp "/tmp/remotion-render-log.XXXXXX")"
START_TS="$(date +%s)"

cleanup() {
  local status=$?
  if [[ -n "${RENDER_PID:-}" ]] && kill -0 "${RENDER_PID}" >/dev/null 2>&1; then
    kill "${RENDER_PID}" >/dev/null 2>&1 || true
  fi
  exit $status
}
trap cleanup INT TERM

echo "[remotion-wrapper] project=$PROJECT_DIR"
echo "[remotion-wrapper] composition=$COMPOSITION_ID"
echo "[remotion-wrapper] output=$OUTPUT_PATH"

(
  cd "$PROJECT_DIR"
  npx remotion render "$COMPOSITION_ID" "$OUTPUT_PATH" "$@"
) >"$LOG_FILE" 2>&1 &
RENDER_PID=$!

while kill -0 "$RENDER_PID" >/dev/null 2>&1; do
  sleep 15
  ELAPSED="$(( $(date +%s) - START_TS ))"
  OUTPUT_BYTES="0"
  if [[ -f "$OUTPUT_PATH" ]]; then
    OUTPUT_BYTES="$(stat -f%z "$OUTPUT_PATH" 2>/dev/null || echo 0)"
  fi
  echo "[remotion-wrapper] heartbeat elapsed=${ELAPSED}s output_bytes=${OUTPUT_BYTES}"
done

wait "$RENDER_PID"
STATUS=$?

if [[ -s "$LOG_FILE" ]]; then
  echo "[remotion-wrapper] render log tail:"
  tail -n 120 "$LOG_FILE"
fi

echo "[remotion-wrapper] exit=$STATUS"
if [[ -f "$OUTPUT_PATH" ]]; then
  ls -lh "$OUTPUT_PATH"
  file "$OUTPUT_PATH" || true
fi

exit "$STATUS"
