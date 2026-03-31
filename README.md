# easy-claudecode.app-win

Bring Claude Code into a Windows-friendly app with a local router, provider-aware model selection, desktop launcher, optional Everything Claude Code integration, and a browser workbench that feels closer to a native coding client.

## Features

- Desktop-style Claude Code launcher for Windows with shortcut repair and standalone app-window launch
- Provider-aware model routing instead of a single hardcoded vendor surface
- In-app settings for provider API keys, upstream URLs, default route, and UI language
- Optional `Everything Claude Code` install path from the official GitHub project
- Source-based open-source workflow plus packaged `.exe` release artifacts
- Local routing helpers so users can keep using `cc switch` and terminal-based Claude Code flows

## One-Line Install

Run this in PowerShell on Windows:

```powershell
powershell -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((Invoke-WebRequest 'https://raw.githubusercontent.com/Arthurescc/easy-claudecode.app-win/main/scripts/install-from-github.ps1' -UseBasicParsing).Content))"
```

What it does:

- checks `git`, `python`, `node`, `npm`, `claude`, and `ccr`
- installs missing source-environment prerequisites when it can
- clones or updates the repo
- prepares `.venv`
- installs Python and Node dependencies
- creates `.env` if missing
- launches `easy-claudecode.app-win`

If `claude` is present but not logged in yet, the app can still open, but Claude CLI features will require running `/login`.

## Install Options

### Option 1: Release Installer

Use the latest GitHub Release if you want the packaged Windows installer:

- [Latest Releases](https://github.com/Arthurescc/easy-claudecode.app-win/releases)

Each release publishes:

- `easy-claudecode.app-win-<version>-setup.exe`

### Option 2: Source Bootstrap

Use the one-line install command above if you want a source-based setup that can update in place and prepare dependencies automatically.

## How It Works

### Provider-Aware Models

The app no longer shows a giant global superset of historical models in the main selector. It now aims to show the models that belong to the currently connected provider family:

- MiniMax upstream -> MiniMax models
- Zhipu upstream -> GLM models
- Qwen/DashScope upstream -> Qwen models
- Moonshot upstream -> Kimi/Moonshot models
- Anthropic-compatible thinking provider -> Claude Opus variants

If a provider family supports a model but the current API key or plan does not, the model may still appear in the selector, but the app should warn instead of silently downgrading.

This keeps compatible provider access aligned with the upstream you actually connected, instead of showing every historical route at once.

### Settings

The in-app settings dialog lets users edit:

- coding provider API key
- coding provider upstream URL
- thinking provider API key
- thinking provider upstream URL
- default route
- router and proxy health URLs
- UI language

### Terminal Compatibility

Users can still switch routes from the terminal:

```powershell
cc switch --list
cc switch compatible-coding,MiniMax-M2.7
```

## Project Layout

- `apps/web/`: browser workbench UI
- `apps/desktop-windows/`: launcher and installer pieces
- `services/backend/`: Flask backend and local proxy
- `config/router/`: router config and custom routing
- `config/providers/`: provider registry and model metadata
- `scripts/`: startup, sync, packaging, bootstrap, and installer scripts
- `qa/`: Windows release smokes and router tests

## Source Commands

Common entrypoints:

- `scripts\open-claude-code.ps1`: start router, proxy, backend, and app
- `scripts\run-claude-console.ps1`: backend only
- `scripts\start-claude-code-router.ps1`: router only
- `scripts\start-claude-code-dashscope-proxy.ps1`: local compatible proxy only

## Notes

- Open-source releases do not ship private paths, secrets, runtime caches, or personal automation data.
- `Everything Claude Code` stays optional and unchecked by default in the installer.
- Full setup details live in [docs/SETUP.md](C:/Users/Administrator/Documents/Playground/easy-claudecode.app-win/docs/SETUP.md).
