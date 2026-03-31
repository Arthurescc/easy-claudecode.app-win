# README Bootstrap And Provider Model Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public one-line bootstrap installer, refresh the GitHub homepage, and make the model selector show only the active provider family's models while warning on API-key/plan unsupported choices.

**Architecture:** Extend the provider registry with provider-family profiles, add a reusable bootstrap installer script, and update backend/frontend catalog generation so the UI only renders models that belong to the detected provider profile. Use explicit model probes or cached provider errors to warn on unsupported plans without silently falling back.

**Tech Stack:** PowerShell, Python/Flask, static HTML/JS, Node test runner

---

### Task 1: Lock README And Bootstrap Expectations

**Files:**
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\readme-bootstrap-surface.test.cjs`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\README.md`
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\install-from-github.ps1`

- [ ] Add a failing README surface test that expects:
  - a feature section
  - a one-line Windows install command
  - source bootstrap wording
- [ ] Add a failing local bootstrap smoke test or script-friendly execution path that can be verified without remote download.
- [ ] Run the test to confirm it fails before implementation.

### Task 2: Implement The One-Line Bootstrap Installer

**Files:**
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\install-from-github.ps1`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\README.md`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\docs\SETUP.md`

- [ ] Implement an idempotent bootstrap script that:
  - clones or updates the repo
  - ensures `.venv`
  - installs Python and Node dependencies
  - creates `.env` if missing
  - launches `scripts/open-claude-code.ps1`
- [ ] Keep the script usable both remotely and locally.
- [ ] Re-run the README/bootstrap checks until they pass.

### Task 3: Add Provider-Profile Model Filtering

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\config\providers\registry.json`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\sync-router.ps1`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\config\router\config.example.json`

- [ ] Add failing tests or smokes that expect MiniMax upstreams to expose only MiniMax-family models in `modelCatalog` and `routeOptions`.
- [ ] Add provider-profile metadata to the registry.
- [ ] Filter router/model catalog generation by detected provider profile.
- [ ] Re-run the catalog tests until they pass.

### Task 4: Add Unsupported Model Warning

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\claude_code_dashscope_proxy.js`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html`
- Create or modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\unsupported-model-warning-smoke.ps1`

- [ ] Add a failing smoke that simulates selecting a provider-family model that returns `2061`.
- [ ] Implement a lightweight warning path that surfaces “API key/plan does not support this model”.
- [ ] Keep explicit requests honest and avoid silent fallback.
- [ ] Re-run the warning smoke and frontend checks until they pass.

### Task 5: Verify Local Machine, Package, And Release

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\ci.yml`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\release.yml`

- [ ] Add the new README/bootstrap/catalog/warning checks to CI and release validation.
- [ ] Update local `.env` and runtime so this machine reflects the new model-filtering behavior.
- [ ] Run fresh local verification.
- [ ] Package the new `.exe`.
- [ ] Publish the next open-source release.
