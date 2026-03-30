# Setup

## Required tools

- `python3`
- `node >= 20`
- `claude` (install separately and complete login before using the console)
- `ccr` (install separately; this repo assumes it is already on `PATH`)
- `PowerShell`（Windows 10/11 默认自带，推荐 PowerShell 7）

## Python setup

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` also includes `Pillow`, which the desktop build uses to generate the app icon.

## Node setup

```bash
npm install
```

## Environment

```powershell
Copy-Item .env.example .env
```

Fill in only the providers you want to use. `DASHSCOPE_CODINGPLAN_API_KEY` remains the compatibility env name for the default Coding Plan chain, which now points to the MiniMax Anthropic-compatible upstream by default. `AICODELINK_OPUS46_API_KEY` is optional.

If you enable the Opus provider, also set `CLAUDE_OPUS_PROXY_UPSTREAM`. The public example no longer hardcodes a private upstream URL.

The app also exposes a local settings dialog that writes these values into `.env` for you. After saving, restart the app so the router and proxy pick up the updated credentials.

`sync-router.ps1` / `sync-router.sh` now also mirrors the generated router config into `~/.claude-code-router/config.json` and updates `~/.claude/settings.json` with the current default route so recent Claude Code builds and `ccr` 2.x read the same model/provider pair.

## Run on Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open-claude-code.ps1
```

On Windows, the first launch now also builds `apps\desktop-windows\bin\Claude Code.app.exe`, creates or repairs the desktop shortcut `Claude Code.app.lnk`, installs `cc.cmd` into `~/.local/bin`, and opens Claude Code in a standalone app window instead of a normal browser tab.

Manual installers:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-desktop-shortcut.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\install-cc-launcher.ps1
```

Quick model switching stays in CLI only:

```powershell
cc switch --list
cc switch MiniMax-M2.7-highspeed
cc switch dashscope-codingplan,glm-5
```

也可以分开启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-claude-code-router.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-claude-code-dashscope-proxy.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run-claude-console.ps1
```

## GitHub publishing checklist

- Run a secrets/path scan before first push
- Confirm `.env` is not tracked
- Confirm `config/router/config.example.json` has no personal paths
- Confirm no runtime cache or uploads are tracked
