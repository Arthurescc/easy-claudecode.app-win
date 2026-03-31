# Provider Registry And Model Routing Design

## Goal

Replace the current DashScope-branded hardcoding with a provider-registry architecture that can represent arbitrary vendors, protocols, models, credentials, and fallback rules, while fixing the local MiniMax M2.7 highspeed experience so explicit model selection shows the real provider error instead of silently degrading.

## Current Problem

The current app mixes three incompatible layers:

- UI-facing labels and provider IDs still say `dashscope-codingplan`
- the proxy upstream already points to MiniMax Anthropic-compatible messages
- the main chat selector uses a hand-written task-mode matrix instead of the real connected provider/model catalog

This creates false branding, mismatched selectors, and hidden model fallback. Local evidence also shows MiniMax sometimes returns `2061` for `MiniMax-M2.7-highspeed` and `2062`/`2056` for rate/plan limits, but the app currently hides that by falling back to `MiniMax-M2.5`.

## Recommended Approach

Build a provider registry with protocol adapters.

Each provider entry should define:

- stable provider id
- display name
- protocol type such as `anthropic-compatible`, `openai-compatible`, or `gemini-compatible`
- base URL
- API key env var name
- health endpoint
- supported models
- fallback rules
- capability flags such as streaming, tool calls, images, reasoning

Backend APIs and frontend selectors should consume the same registry-derived model catalog instead of separate hardcoded lists.

## Alternatives

### Option 1: Rename DashScope To MiniMax Only

Fastest, but still leaves the architecture vendor-bound and does not solve arbitrary providers or mismatched selectors.

### Option 2: Provider Registry With Protocol Adapters

Recommended. Fixes the current mismatch and gives us a scalable path for MiniMax, OpenRouter, Gemini compatibility, Zhipu, Moonshot, and future providers.

### Option 3: Remote Dynamic Catalog Fetch

Most flexible, but too risky for the immediate release because it adds caching, schema, and auth complexity before the local architecture is stable.

## Architecture

### Provider Registry

Create a single source of truth for provider definitions and exposed models. This should be readable by:

- backend settings/bootstrap endpoints
- proxy launch scripts
- router config generation
- frontend settings dialog
- frontend main chat model selector

### Protocol Adapters

Split the current vendor-specific proxy into protocol-aware adapters:

- Anthropic-compatible adapter for providers like MiniMax and compatible routes
- OpenAI-compatible adapter for providers like OpenRouter and Moonshot-compatible endpoints
- Gemini/OpenAI-compat adapter path when official compatibility mode is used

The app should no longer assume one provider implementation file equals one vendor brand.

### Selection Semantics

- Explicit model selection: no silent fallback
- Auto selection: fallback allowed only within policy and with visible notice
- Unsupported/plan-limited model errors must surface provider-native reason codes in the UI

### Settings And Main Chat Selector

Settings should expose:

- provider credentials
- provider endpoints
- optional default route

Main chat model selector should expose:

- actual connected provider/model choices, grouped by provider
- only models present in the active registry/config

## Research Summary

Current official documentation confirms the ecosystem is mixed-protocol:

- MiniMax exposes an Anthropic-compatible text API and model lineup including `MiniMax-M2.7-highspeed`
- Google documents OpenAI compatibility for Gemini
- OpenRouter exposes an OpenAI-compatible API surface across many models
- current Chinese vendor ecosystems commonly expose either Anthropic-compatible or OpenAI-compatible surfaces rather than one shared native schema

This supports a protocol-adapter architecture more strongly than a vendor-specific proxy.

## Error Handling

- If a provider returns a model-not-supported error such as MiniMax `2061`, surface it directly for explicit selections
- If a provider returns plan/rate-limit errors such as `2062` or `2056`, show actionable UI status instead of masking them
- If a fallback path is used in Auto mode, include the requested model and actual model used in backend and frontend status

## Testing

- regression test for provider registry settings payload
- regression test that explicit model selection does not silently fallback
- regression test that Auto mode can fallback with a visible used-model indicator
- frontend test that settings and main selector are fed by the same model catalog
- local smoke test for MiniMax provider configuration

## Assumptions

- The user wants the open-source release to allow arbitrary vendors instead of shipping with one vendor name hardcoded
- The current local MiniMax API key remains the immediate validation target
- Explicitly selected models should prefer truthful failures over hidden downgrade behavior
