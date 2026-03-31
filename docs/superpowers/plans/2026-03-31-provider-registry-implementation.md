# Provider Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded vendor/model plumbing with a provider-registry architecture, fix local MiniMax M2.7 highspeed behavior, and ship a corrected open-source release.

**Architecture:** Introduce a single provider registry consumed by backend settings/bootstrap, router/proxy config generation, and frontend selectors. Split explicit selection behavior from Auto fallback behavior so unsupported provider errors surface honestly.

**Tech Stack:** Python/Flask, Node.js, PowerShell, static HTML/JS, GitHub Actions

---

### Task 1: Reproduce And Lock The Current Provider Mismatch

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\frontend-install-surface.test.cjs`
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\provider-registry-settings-smoke.ps1`
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\explicit-model-no-fallback-smoke.ps1`

- [ ] **Step 1: Write failing selector/registry expectations**
- [ ] **Step 2: Verify `/claude-console/settings` exposes registry-driven provider/model data**
- [ ] **Step 3: Verify explicit selected model failure is not silently downgraded**
- [ ] **Step 4: Run the new tests and capture the failing behavior**

### Task 2: Introduce Provider Registry In Backend

**Files:**
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\config\providers\registry.json`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\sync-router.ps1`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\config\router\config.example.json`

- [ ] **Step 1: Add a registry format for provider metadata and models**
- [ ] **Step 2: Load registry data in backend bootstrap/settings**
- [ ] **Step 3: Make route options and provider settings come from the registry**
- [ ] **Step 4: Re-run backend smoke tests**

### Task 3: Replace Vendor-Specific Proxy Assumptions

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\claude_code_dashscope_proxy.js`
- Create or rename: protocol-oriented proxy/adapters under `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\config\router\custom-router.js`

- [ ] **Step 1: Separate provider identity from protocol implementation**
- [ ] **Step 2: Preserve explicit model choice without hidden fallback**
- [ ] **Step 3: Restrict fallback behavior to Auto/policy-controlled flows**
- [ ] **Step 4: Re-run MiniMax local smoke tests**

### Task 4: Unify Frontend Settings And Main Selector

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html`

- [ ] **Step 1: Replace hardcoded provider labels and mode descriptions that assume DashScope**
- [ ] **Step 2: Feed the settings dialog from backend provider registry data**
- [ ] **Step 3: Feed the main chat selector from the same registry-derived catalog**
- [ ] **Step 4: Surface requested model vs actual used model when fallback occurs**
- [ ] **Step 5: Re-run inline JS and frontend selector tests**

### Task 5: Fix Local MiniMax And Release The Corrected Open-Source Build

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\ci.yml`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\release.yml`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\README.md`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\docs\SETUP.md`

- [ ] **Step 1: Verify local MiniMax configuration with the supplied API key**
- [ ] **Step 2: Update docs to describe arbitrary providers instead of DashScope branding**
- [ ] **Step 3: Run full release verification locally**
- [ ] **Step 4: Publish the corrected open-source release**
