# easy-claudecode.app-win desktop entry

This folder contains the Windows desktop launcher source for `easy-claudecode.app-win`.

Recommended flow:

1. Run `scripts/open-claude-code.cmd` or `scripts/open-claude-code.ps1` once. The repo will build `apps/desktop-windows/bin/Claude Code.app.exe` and create or repair the desktop shortcut `Claude Code.app.lnk`.
2. Copy `.env.example` to `.env` before first launch and fill in the API keys you actually use.
3. Double-click the desktop shortcut to start Router, Proxy, and Backend, then open the console in a standalone app window.
4. Use `cc switch` from the terminal when you need to change the default provider/model; this stays out of the web UI on purpose.

The GitHub release package includes the built launcher exe. A source checkout can rebuild it with `npm run build:launcher`.
