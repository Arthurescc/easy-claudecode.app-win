# Startup Setup And Existing Config Reuse Design

## Goal

Make the open-source Windows build detect and reuse the user's existing Claude Code environment on first launch, only prompt for setup when the machine is genuinely unconfigured, and stop nudging self-hosted API users toward official Claude login when their own provider route already works.

## User Requirements

- The app should check the machine's current state on startup instead of assuming every user needs fresh setup.
- If the user already has working API configuration, logged-in official Claude access, or both, the app should reuse that state directly.
- If the user already has `skills`, `agents`, or `MCP` configured on the machine, the app should surface and use them without asking the user to rebuild that environment.
- The first-run experience for the open-source build should open settings only when the machine does not already have a usable path to send tasks.
- Users who rely on their own API key and URL should not be pushed toward `/login` or official Claude authentication.
- Settings should clearly separate:
  - reuse what is already available on this machine
  - connect with custom API key / upstream URL
  - connect with official Claude login

## Current Behavior And Root Cause

- The backend bootstrap already exposes useful runtime signals:
  - local provider settings from `.env`
  - Claude CLI presence/version
  - library inventory for `skills`, `agents`, and `MCP`
  - router/proxy health
- The frontend already renders a welcome state and a settings dialog, but it does not yet make a startup decision based on those runtime signals.
- The app can already run chats through the local router and self-hosted MiniMax path even when `claude auth status` reports `loggedIn: false`.
- Because the UI does not currently distinguish "official Claude login is optional here" from "official Claude login is required here", users can still be misled into thinking `/login` is mandatory.

## Alternatives Considered

### 1. Always force the settings dialog on first launch

This is simple, but it is noisy for users whose machines are already configured. It also makes the open-source build feel less intelligent than the environment it is already capable of detecting.

### 2. Never auto-open settings and rely on the welcome page alone

This avoids interruption, but it is too passive for genuinely new users who have neither official Claude login nor self-hosted API configuration.

### 3. Recommended: state-driven onboarding

Use backend-detected machine state to decide whether setup is needed, and tailor the UI copy to the user's actual situation. This gives first-time users guidance without blocking already-configured users.

## Recommended Approach

### 1. Add a backend startup readiness summary

Extend bootstrap payloads with a compact `setupStatus` object that answers:

- is official Claude CLI installed
- is official Claude CLI logged in
- does the machine already have at least one configured provider API key / upstream pair
- does the router currently have a usable default or available route catalog
- does the machine already expose local `skills`, `agents`, or `MCP`
- should the UI recommend opening settings immediately
- which connection paths are available right now

This should be derived from existing backend signals rather than re-inventing new state files.

### 2. Define "ready enough to use" conservatively

The app should consider the machine immediately usable if either of these is true:

- the self-hosted/provider route path is already configured well enough to send tasks
- official Claude CLI login is already available and usable

If both are present, treat that as an even stronger reuse case.

The app should only recommend setup if neither path is currently usable.

### 3. Reframe startup onboarding around connection strategy

Keep the welcome surface lightweight, but let it adapt to current machine state:

- already configured machine:
  - show a "ready to use" note
  - mention which path is currently available, such as custom provider route or official Claude login
  - offer settings as an optional adjustment entry point
- unconfigured machine:
  - show a stronger onboarding prompt
  - auto-open settings once on first launch
  - explain the three setup choices clearly

### 4. Make the settings dialog strategy-aware

Add a connection strategy section at the top of settings that communicates:

- reuse existing machine configuration
- custom API key / upstream URL
- official Claude login

This does not need to become a complicated wizard. It can remain a single dialog, but the top copy and status chips should make it obvious which path is currently active and whether the user actually needs to do anything.

### 5. Suppress official-login nudges for self-hosted users

When the machine already has a usable self-hosted route:

- do not show "please run /login" as a default remedy
- do not frame `claude auth status = loggedOut` as blocking
- keep official login as an optional alternate path only

If the user explicitly chooses the official Claude path, then official login guidance is appropriate.

### 6. Reuse existing machine libraries automatically

Continue treating the machine's existing Claude environment as the source of truth for:

- `~/.claude/skills`
- `~/.claude/agents`
- `~/.claude.json` `mcpServers`
- existing provider settings already saved by the user

The onboarding layer should present these as already detected capabilities rather than as missing prerequisites the user must re-enter.

## Architecture Notes

- Keep detection logic in the backend so the frontend stays declarative.
- Do not gate local-router execution on official Claude login when a working provider route already exists.
- Keep "machine capability detection" separate from "user preference editing".
- Reuse the existing bootstrap payload rather than adding another startup endpoint.
- Persist only minimal onboarding state on the frontend, such as "auto-opened once", instead of writing more global config.

## Testing

- backend smoke test for `setupStatus` classification:
  - configured provider route without official Claude login should still be considered usable
  - official Claude login without provider route should also be considered usable
  - no provider route and no official login should recommend setup
- frontend test for startup auto-open behavior:
  - already configured bootstrap should not auto-open settings
  - unconfigured bootstrap should auto-open settings once
- frontend test for settings strategy messaging:
  - custom-provider-ready state should not show official login as required
- regression test for task execution:
  - a self-hosted route should still run chat successfully while `claude auth status` is logged out

## Local Validation Targets

- This machine should be classified as usable via custom provider route even while official Claude login remains logged out.
- Existing `skills`, `agents`, and connected `MCP` on this machine should continue appearing automatically after startup.
- The open-source build should only auto-open settings on a machine that has neither self-hosted provider configuration nor official Claude login.
