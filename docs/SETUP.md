# Setup

## Required tools

- `python3`
- `node >= 20`
- `claude`
- `ccr`
- `PowerShell`

## Python setup

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` also includes `Pillow`, which the desktop build uses to generate the launcher icon.

## Node setup

```bash
npm install
```

## Environment

```powershell
Copy-Item .env.example .env
```

## One-line Windows bootstrap

```powershell
powershell -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((Invoke-WebRequest 'https://raw.githubusercontent.com/Arthurescc/easy-claudecode.app-win/main/scripts/install-from-github.ps1' -UseBasicParsing).Content))"
```

The bootstrap script checks the source environment, prepares the repo, installs Python and Node dependencies, creates `.env` if needed, and launches the app.

The public setup now uses provider-generic environment names:

- `CODING_COMPATIBLE_API_KEY`
- `CODING_COMPATIBLE_UPSTREAM`
- `ANTHROPIC_THINKING_API_KEY`
- `ANTHROPIC_THINKING_UPSTREAM`

Older alias names are still mirrored into `.env` for backward compatibility with existing scripts and local installs.

The local Settings dialog can update these values for you. After saving, restart the app so the router and proxy pick up the new credentials and upstreams.

`sync-router.ps1` and `sync-router.sh` also mirror the generated router config into `~/.claude-code-router/config.json`. When a default route is selected, the same route can also be mirrored into Claude Code settings so `ccr` and recent Claude Code builds stay aligned.

## Run on Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open-claude-code.ps1
```

On first launch, the app flow also:

- builds `apps\desktop-windows\bin\Claude Code.app.exe`
- creates or repairs `Claude Code.app.lnk`
- installs `cc.cmd` into `~/.local/bin`

Manual launch commands:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-claude-code-router.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-claude-code-dashscope-proxy.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run-claude-console.ps1
```

Quick model switching can stay in CLI:

```powershell
cc switch --list
cc switch compatible-coding,MiniMax-M2.7
```

## GitHub publishing checklist

- confirm `.env` is not tracked
- confirm `config/router/config.example.json` has no personal paths
- confirm runtime caches and uploads are not tracked
- run the Windows release smoke checks before tagging
