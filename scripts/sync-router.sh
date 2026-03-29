#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common-env.sh"

mkdir -p "$CLAUDE_ROUTER_RUNTIME_DIR"
cp "$CLAUDE_ROUTER_SOURCE_DIR/custom-router.js" "$CLAUDE_ROUTER_RUNTIME_DIR/custom-router.js"

python3 - "$CLAUDE_ROUTER_SOURCE_DIR/config.example.json" "$CLAUDE_ROUTER_RUNTIME_DIR/config.json" "$CLAUDE_ROUTER_RUNTIME_DIR/custom-router.js" <<'PY'
import json
import os
import sys
src, dst, custom = sys.argv[1:4]
data = json.load(open(src, "r", encoding="utf-8"))
data["CUSTOM_ROUTER_PATH"] = custom
for provider in data.get("Providers", []):
    if not isinstance(provider, dict):
        continue
    env_url = str(provider.get("api_base_url") or "").strip()
    if env_url.startswith("$"):
        provider["api_base_url"] = os.getenv(env_url[1:], "")
with open(dst, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY
