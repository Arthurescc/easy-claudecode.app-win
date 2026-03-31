# Codex-Style Chat Shell Design

## Goal

Upgrade the Windows Claude Code chat shell so it behaves and looks much closer to Codex while keeping Claude Code as the execution core. The shell should expose real runtime state, structured slash commands, Codex-like run-step rendering, and smoother chat scrolling without turning the app into a different product internally.

## User Requirements

- Keep the execution core as Claude Code, local router, local proxy, and the existing skill / agent / MCP environment.
- Make the interaction behavior and information structure feel much closer to Codex.
- Make the visual style also move closer to Codex rather than keeping the current more decorative layout.
- Add a small context usage ring near the chat controls that shows real backend context usage on hover.
- Default permission mode should behave like Codex auto mode and map to `claude --enable-auto-mode` semantics for both local use and the published open-source build.
- While a task is streaming or running, users must still be able to scroll upward naturally without the UI forcing them back to the bottom.
- Tool / shell / run steps should render as collapsible execution records similar to Codex instead of only raw tool-result blocks.
- Typing `/` in the composer should open a structured chooser similar to Codex.
- The slash chooser should cover `MCP / Model / Reasoning / Personality / Status / Plan / Skills`.
- Choosing slash items should create structured tags inside the composer, not plain inserted text.
- The published open-source release should include the new defaults and shell behavior.

## Current State

- The current frontend already has:
  - model selection
  - agent mode selection
  - permission mode selection
  - message rendering with text / thinking / tool blocks
  - sidebar-driven skills / agents / MCP discovery
- The current shell does not yet have:
  - a Codex-like top status strip
  - real context usage display
  - structured slash chooser and inline capability chips
  - compact collapsible execution cards for shell/tool steps
  - proper scroll lock release while streaming
- The backend already exposes useful runtime state such as:
  - active model catalog
  - agent modes
  - setup status
  - skills / agents / MCP inventory
- But it does not yet expose a dedicated Codex-style shell metadata layer for:
  - real context usage
  - slash palette sections
  - structured composer chip payloads
  - permission default profile metadata

## Alternatives Considered

### 1. Cosmetic-only Codex skin

This would copy some visual affordances but keep the existing message and composer architecture mostly unchanged. It is fast, but it would fail the user's requirement for real context usage and structured slash selection.

### 2. Interaction-first upgrade with limited visual restyling

This would fix behavior and data shape first, then revisit visual parity in another release. It is safer, but it would leave the shell feeling half-finished and inconsistent with the request to bring both interaction and look closer to Codex now.

### 3. Recommended: complete shell-layer upgrade

Treat this as a shell-layer redesign:

- backend adds runtime shell metadata
- frontend reorganizes the top bar, composer, slash chooser, and execution rendering together
- release defaults are updated in the same pass

This keeps Claude Code intact underneath while making the UI and interaction model coherent.

## Recommended Approach

### 1. Introduce a chat-shell metadata layer in backend bootstrap

Extend bootstrap and related runtime responses with a new shell-oriented payload, for example `chatShell` or `shellState`, that includes:

- current effective model
- current reasoning profile
- current permission profile
- current branch / repo state if already available
- real context usage information
- slash chooser sections and selectable items
- currently selected structured chips in the composer session state if needed

This layer should remain descriptive and frontend-facing. It should not change Claude Code internals, only describe them to the UI.

### 2. Use real context usage, not frontend estimation

The context ring must be backed by real backend values. The backend should derive or collect:

- used context
- maximum context window
- percentage used
- optionally split usage such as input / output / system overhead when available

If exact values are unavailable for a turn, the backend should surface that explicitly as unavailable rather than letting the frontend fabricate a number.

### 3. Promote permission mode to an auto-first default

Change the default permission mode behavior to align with the user's requested Codex-like auto mode. This should apply consistently across:

- current local runtime defaults
- startup bootstrap defaults
- terminal launch helpers
- published open-source release defaults

The UI should describe this as the normal mode rather than an advanced override.

### 4. Rebuild the top bar as a compact Codex-like control strip

The upper composer control region should become a compact status/control strip that includes:

- file add button
- current model selector
- current reasoning selector
- current permission selector
- context ring
- lightweight branch / refresh indicators

This should reduce the current visual bulk and move closer to Codex information density.

### 5. Replace raw tool-result emphasis with collapsible run-step cards

The current message renderer already has enough structure to distinguish tool-ish output. Build a Codex-like execution presentation layer on top of it:

- compact collapsed summary by default
- expandable detailed list of executed shell/tool steps
- success / failure markers
- empty-output handling
- separate long outputs from the main conversational text

This keeps execution history readable during longer coding sessions.

### 6. Add structured slash chooser and composer chips

Typing `/` in the composer should open a chooser overlay anchored to the composer. It should provide these sections:

- `MCP`
- `Model`
- `Reasoning`
- `Personality`
- `Status`
- `Plan`
- `Skills`

Selecting items should create structured chips inside the composer. These chips should submit structured metadata alongside the natural-language prompt rather than only inserting raw text.

The backend should then translate selected chips into:

- mode changes
- reasoning hints
- skill / MCP references
- runtime prompt augmentation
- status visibility actions

### 7. Make slash chooser reflect real machine state

The chooser must be driven by real runtime data:

- `MCP` from connected MCP servers
- `Skills` from detected skill inventory
- `Model` from current model catalog
- `Reasoning` from supported shell reasoning levels
- `Status` from available runtime diagnostics
- `Plan` from planning-capable modes or actions
- `Personality` from supported persona presets or equivalent prompt overlays

No fake static menu should be shown for items that the current runtime cannot actually support.

### 8. Fix streaming scroll behavior at the shell level

Current streaming behavior still pulls users toward the bottom too aggressively. Update the renderer so that:

- auto-stick only happens when the user is already near the bottom
- upward manual scrolling disables auto-stick for the current interaction
- a clear return-to-bottom path exists without hijacking normal scroll behavior

This must work for both text streaming and expanding execution cards.

## Architecture Notes

- Keep Claude Code as the executor. Do not replace the runtime with Codex-specific internals.
- Concentrate most UI work inside `apps/web/claude-console.html`, but avoid making it even harder to maintain than it already is. If a focused split is needed for helper logic, it should still preserve the current delivery model.
- Prefer extending existing bootstrap responses over introducing many new endpoints, unless context usage or run-step detail requires a dedicated runtime endpoint.
- Keep slash selections structured through request payloads where possible, instead of encoding everything into synthetic prompt text.
- Permission auto mode must be consistent between chat UI, quick run, terminal launch, and release defaults.

## Testing

- backend smoke test for context usage payload shape and availability semantics
- backend / frontend test for default permission mode being auto-first
- frontend surface test for slash chooser sections and structured chip rendering
- frontend behavior test for startup shell strip and context ring presence
- frontend behavior test for streaming scroll release when the user scrolls upward
- frontend / backend regression test for run-step collapse / expand rendering
- release workflow coverage for the new startup shell tests and permission defaults

## Local Validation Targets

- Hovering the context ring should show real backend usage rather than a frontend estimate.
- Default permission mode should come up as auto mode in the UI and release build.
- During a running task, the user should be able to scroll up and stay there until they choose to return to the bottom.
- `/` should open a structured chooser and insert chips for `MCP / Model / Reasoning / Personality / Status / Plan / Skills`.
- Sending a prompt with selected chips should still run correctly through the Claude Code runtime.
- The published release should ship with the same defaults and shell behavior as the local validated build.
