# Architecture

## Runtime model

- Web UI: `apps/web/claude-console.html`
- Backend: `services/backend/app.py`
- Local Claude wrapper: `scripts/claude-local-router.sh`
- Router sync: `scripts/sync-router.sh`
- Runtime mirror: `${EASY_CLAUDECODE_HOME}/runtime/claude-console`

## Default behavior

- The repo runs in standalone mode by default.
- Claude CLI, Claude Code Router, and the optional DashScope/Opus providers are externally configured.
- External dispatch bridge behavior is feature-flagged and disabled in the public build.

## Config surfaces

- `.env`: user-local runtime configuration
- `config/router/config.example.json`: template for router runtime config
- `config/router/custom-router.js`: routing heuristics

## Public-release constraints

- No hardcoded personal paths
- No bundled credentials or account data
- No dependence on LaunchAgents for a successful local run
- Desktop app build remains source-root aware and should be rebuilt after moving the repo
