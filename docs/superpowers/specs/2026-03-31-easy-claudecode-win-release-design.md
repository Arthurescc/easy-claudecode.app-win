# Windows Launcher And Release Design

## Goal

Deliver `easy-claudecode.app-win` as a Windows-first open-source release that behaves like a real desktop app, keeps route-based model selection working in PTY compatibility mode, exposes optional Everything Claude Code setup, and publishes a single-file `.exe` release artifact instead of a browser-first HTML handoff.

## Scope

This design intentionally stays inside the existing `Flask + local router + Windows launcher + static web console` architecture. We are not rewriting the app to Electron or Tauri. The work is limited to:

- fixing the route-prefix leak that causes `[route:glm5]` to reach the upstream model as user text
- giving the Windows launcher and shortcut a stable branded icon
- adding an installer-oriented Windows release flow that emits a distributable `.exe`
- exposing optional Everything Claude Code setup in the product surface so open-source users can choose whether to install it

## Architecture

The runtime will continue to use the local Claude router for model selection, but route tags will become routing-only metadata at the edge of the router path. The router custom script will choose the target model from `[route:...]`, then sanitize the user-authored message body before it reaches the upstream provider. This keeps per-request routing while preventing prompt pollution.

Windows packaging will gain a second compiled app: a setup executable that embeds the staged release payload as a zip resource. The setup app extracts the package into a local install directory, offers optional post-install actions, and can launch the desktop app immediately. The existing launcher executable remains the runtime entry point that opens the standalone browser-shell window.

## Components

### Router And Backend

- `config/router/custom-router.js`
  Strip `[route:...]` markers from forwarded message content after route selection succeeds.
- `services/backend/claude_console_utils.py`
  Preserve the user's in-flight Windows compatibility changes, but make subprocess invocation keep the router wrapper behavior instead of leaking route-only prompt markers upstream.
- `services/backend/app.py`
  Add install-state/config surfaces for Everything Claude Code and any installer-related frontend metadata.

### Windows Desktop And Installer

- `apps/desktop-windows/launcher/Program.cs`
  Keep the existing runtime launcher, but embed a real icon.
- `apps/desktop-windows/installer/Program.cs`
  Add a new setup executable that extracts the staged release bundle, offers install options, and runs post-install actions.
- `apps/desktop-windows/assets/*`
  Store the shared Windows icon resource.
- `scripts/build-desktop-launcher.ps1`
  Compile the launcher with the icon.
- `scripts/package-release.ps1`
  Stage the runtime payload, build the installer executable, and output `.exe` assets instead of zip-only artifacts.

### Frontend Adaptation

- `apps/web/claude-console.html`
  Surface Windows install state and an optional Everything Claude Code install action in the existing welcome/settings experience.
- `services/backend/app.py`
  Add the HTTP endpoints the frontend needs for install status and install triggers.

## Data Flow

1. The web console still prepares prompts with route hints for explicit model selection.
2. The custom router selects the target provider/model from the route hint.
3. Before the request leaves the router boundary, the route hint is removed from forwarded user text.
4. The upstream model receives only the real task content.
5. On Windows release installs, the setup executable extracts the release payload to a stable local directory, optionally creates shortcuts, optionally installs helper tooling, and optionally kicks off Everything Claude Code setup.

## Error Handling

- If route stripping fails, the router should still choose a safe default route and log the issue rather than crashing the chat request.
- If the installer cannot extract or write to the target directory, it should show a blocking Windows dialog with the exact path and failure reason.
- Everything Claude Code setup is optional and must fail softly. A failed ECC install must not block the base app install.
- If icon compilation or setup compilation fails during CI, the release workflow should fail before publishing assets.

## Testing

- Add a route-router regression test that proves `[route:glm5]` still selects `glm-5` while the forwarded prompt no longer contains the route marker.
- Extend Windows smoke verification to assert the launcher icon asset exists and the setup executable is produced.
- Run a quick-run regression against the local backend: `glm5` mode should answer the prompt content instead of asking what `[route:glm5]` means.
- Run a release packaging smoke test that validates the `.exe` asset path expected by GitHub Actions.

## Assumptions

- The official Everything Claude Code repository remains the upstream source of truth, and this repo should install it as an optional add-on rather than vendoring the whole project.
- The user wants the public GitHub repo to remain open-source and self-installable on Windows without requiring a manual HTML/browser launch flow.
