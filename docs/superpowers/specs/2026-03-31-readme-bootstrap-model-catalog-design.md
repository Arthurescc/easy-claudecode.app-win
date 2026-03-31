# README Bootstrap And Provider Model Catalog Design

## Goal

Make the public GitHub homepage look like a polished open-source project, add a one-line Windows bootstrap installer for source-based setup, and make the in-app model selector reflect the currently connected provider instead of a global superset.

## User Requirements

- The GitHub homepage should explain what the project does and how to install it.
- Users should be able to install from the terminal with one command that checks prerequisites, prepares the source checkout, installs dependencies, and launches the app.
- The model selector should only list models that belong to the currently connected provider family.
- Models that the provider supports but the current API key or plan does not support may still appear, but choosing them must surface a clear warning instead of silently degrading.
- Local configuration on this machine must be updated before release.

## Recommended Approach

### 1. Public README Refresh

Rewrite the top of `README.md` into a conventional project homepage:

- one-sentence project value
- key features
- one-line install command
- installer vs source-based setup notes
- provider/model configuration notes
- release download and FAQ

This keeps the repository landing page useful even before users open `docs/SETUP.md`.

### 2. One-Line Bootstrap Installer

Add a PowerShell bootstrap script that supports both:

- being run locally from the repo
- being invoked remotely via `iwr ... | iex`

The script should:

- verify required tools
- clone or update the repo in a stable local directory
- create `.venv` if missing
- install Python and Node dependencies if missing
- create `.env` from `.env.example` if missing
- launch `scripts/open-claude-code.ps1`

It should be idempotent so re-running it is safe.

### 3. Provider-Specific Model Catalog

The current model dropdown still exposes every model in the generic compatible provider. Replace that with a provider-profile-driven catalog.

The catalog should be derived from:

- the active upstream URL or provider hint
- a provider profile table in the registry
- the generated router config

For example:

- MiniMax upstream -> only MiniMax models
- Zhipu upstream -> only GLM models
- Moonshot upstream -> only Kimi/Moonshot models
- Anthropic-compatible thinking provider -> only Claude Opus variants

If the upstream is unknown, the UI should degrade gracefully and show the configured route catalog rather than the full historical superset.

### 4. Unsupported Model Warning

When the user picks a model that belongs to the provider family but the current API key/plan cannot access it:

- do not silently fallback
- do not keep the failure opaque
- show a user-facing warning like “Current API key or plan does not support this model”

The warning can be driven by a lightweight backend probe with caching, or by a cached provider error from a recent explicit request.

## Architecture Notes

- Keep the provider registry as the source of truth.
- Split “supported by provider family” from “available to this API key”.
- Let the selector show provider-family support, and let the warning layer communicate key/plan support.
- Preserve explicit route semantics: explicit selection should fail honestly.

## Testing

- README surface test for the one-line install command and feature sections
- bootstrap smoke test for local source bootstrap mode
- provider-profile catalog smoke test for MiniMax/local provider filtering
- frontend test for provider-specific model rendering
- unsupported-model warning smoke test for a known unsupported explicit model

## Local Validation Targets

- This machine should keep `compatible-coding,MiniMax-M2.7-highspeed` visible in the selector.
- If the current key still lacks M2.7 highspeed access, selecting it should warn instead of silently downgrading.
- The desktop launcher and source bootstrap should still start the app successfully.
