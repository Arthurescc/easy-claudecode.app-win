#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common-env.sh"

SOURCE_ROOT="$CLAUDE_CONSOLE_SOURCE_ROOT"
RUNTIME_ROOT="$CLAUDE_CONSOLE_RUNTIME_ROOT"

mkdir -p "$RUNTIME_ROOT"

for path_name in apps services config scripts docs; do
  if [[ -d "$SOURCE_ROOT/$path_name" ]]; then
    rsync -a --delete \
      --exclude '__pycache__' \
      --exclude '.DS_Store' \
      --exclude '.env' \
      --exclude '.venv' \
      --exclude 'dist' \
      --exclude 'runtime' \
      "$SOURCE_ROOT/$path_name"/ "$RUNTIME_ROOT/$path_name"/
  fi
done

for file_name in README.md LICENSE package.json requirements.txt .env.example .gitignore; do
  if [[ -f "$SOURCE_ROOT/$file_name" ]]; then
    rsync -a "$SOURCE_ROOT/$file_name" "$RUNTIME_ROOT/$file_name"
  fi
done
