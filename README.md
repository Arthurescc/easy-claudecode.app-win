# easy-claudecode.app-win

`easy-claudecode.app-win` brings Claude Code from the terminal into a Windows-friendly app flow with a local backend, router, compatible provider proxy, desktop launcher, and a browser workbench.

## What it includes

- `apps/web/`: the browser workbench UI
- `apps/desktop-windows/`: the Windows launcher and installer pieces
- `services/backend/`: the Flask backend and local compatible proxy
- `config/router/`: router config and custom routing logic
- `config/providers/`: provider registry metadata for settings and model surfaces
- `scripts/`: startup, sync, packaging, and installer scripts
- `qa/`: Windows release smoke tests and router tests

## Quick start

1. Install prerequisites:
   - `python3`
   - `node >= 20`
   - `claude`
   - `ccr`
   - `PowerShell`
2. Copy the example environment:
   - `Copy-Item .env.example .env`
3. Install Python dependencies:
   - `py -3 -m venv .venv`
   - `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
4. Install Node dependencies:
   - `npm install`
5. Start the app:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\open-claude-code.ps1`
6. Open:
   - [http://127.0.0.1:18882/claude-console](http://127.0.0.1:18882/claude-console)

## Settings and routing

The top-right Settings dialog lets users edit:

- default model route
- compatible provider API keys
- upstream URLs
- router and proxy health URLs
- UI language

The public release no longer exposes stale DashScope branding in the UI. The default coding chain is now described generically so users can point it at MiniMax or any other compatible upstream they prefer.

Model switching can stay in CLI or be changed from the settings dialog:

```powershell
cc switch --list
cc switch compatible-coding,MiniMax-M2.5
```

## Windows launch flow

The repo ships PowerShell entrypoints:

- `scripts\open-claude-code.ps1`: starts router, proxy, backend, and opens the app
- `scripts\run-claude-console.ps1`: backend only
- `scripts\start-claude-code-router.ps1`: router only
- `scripts\start-claude-code-dashscope-proxy.ps1`: compatible provider proxy only

On first launch, the repo also builds `apps\desktop-windows\bin\Claude Code.app.exe`, repairs the desktop shortcut, and installs `cc.cmd`.

## Release output

GitHub Releases publish a Windows installer:

- `easy-claudecode.app-win-<version>-setup.exe`

The installer keeps `Everything Claude Code` as an optional add-on and does not force-install it by default.

## Notes

- Open-source releases do not ship private paths, secrets, runtime caches, or personal automation data.
- See [docs/SETUP.md](C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\docs\SETUP.md) for setup details.
