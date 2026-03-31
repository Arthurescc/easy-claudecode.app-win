# Codex-Style Chat Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Claude Code Windows chat shell to a Codex-like interaction model with real backend context usage, auto-first permissions, structured slash chips, collapsible run-step records, improved streaming scroll behavior, and matching release defaults.

**Architecture:** Keep Claude Code, the router, proxy, and local skills / agents / MCP as the execution core, then add a dedicated shell metadata layer in the backend that feeds a redesigned frontend control strip and composer workflow. Implement the UI changes mostly inside the existing `claude-console.html`, but separate runtime shell state, structured slash selection, and execution-card rendering into clear helper boundaries so the shell remains testable.

**Tech Stack:** Flask backend, Python stream/session helpers, single-file HTML/JS frontend, PowerShell smoke tests, Node `--test` surface tests, Windows release packaging scripts

---

## File Structure

- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\claude_console_utils.py`
  - Add runtime usage extraction and normalized execution-step metadata from Claude stream events.
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py`
  - Add `chatShell`/runtime metadata, slash section payloads, permission default changes, and structured chip handling.
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html`
  - Rebuild top control strip, composer slash workflow, context ring, execution cards, scroll behavior, and structured chip submission.
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\common-env.ps1`
  - Set auto-first permission defaults for local runtime bootstrapping.
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\run-claude-console.ps1`
  - Ensure backend launches with the new permission default semantics.
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\open-claude-code.ps1`
  - Keep release-launch defaults aligned with the new permission mode.
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\chat-shell-runtime-smoke.ps1`
  - Verify backend shell metadata contains usage, permission default, slash sections, and run-step shape.
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\codex-shell-surface.test.cjs`
  - Verify frontend contains Codex-style shell strip, context ring, slash chooser, and run-step collapse hooks.
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\scroll-autostick-smoke.ps1`
  - Verify streaming autostick is released once the user scrolls away from bottom.
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\ci.yml`
  - Add the new shell upgrade checks.
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\release.yml`
  - Add the new shell upgrade checks for release validation.

### Task 1: Add Failing Backend Shell-Metadata Smoke Coverage

**Files:**
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\chat-shell-runtime-smoke.ps1`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\claude_console_utils.py`

- [ ] **Step 1: Write the failing shell-runtime smoke test**

```powershell
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PythonBin = (Resolve-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")).Path

@'
import json
import sys

sys.path.insert(0, r"C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend")
import app  # noqa: E402

payload = app._build_status(force_refresh=True)
shell = payload.get("chatShell") or {}

assert shell, payload
assert "contextUsage" in shell, shell
assert "slashSections" in shell, shell
assert "permissionDefault" in shell, shell
assert shell["permissionDefault"] == "auto", shell
assert any(str(item.get("id") or "") == "skills" for item in shell.get("slashSections") or []), shell
assert any(str(item.get("id") or "") == "mcp" for item in shell.get("slashSections") or []), shell

print("chat shell runtime ok")
'@ | & $PythonBin -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
```

- [ ] **Step 2: Run the new smoke test to verify it fails**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\chat-shell-runtime-smoke.ps1
```

Expected: FAIL because `chatShell`, `contextUsage`, and the new slash section metadata do not exist yet.

- [ ] **Step 3: Commit the failing backend smoke scaffold**

```bash
git add qa/windows-release/chat-shell-runtime-smoke.ps1
git commit -m "test: add chat shell runtime smoke"
```

### Task 2: Implement Backend Chat-Shell Metadata And Auto Permission Defaults

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\claude_console_utils.py`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\common-env.ps1`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\run-claude-console.ps1`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\open-claude-code.ps1`
- Test: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\chat-shell-runtime-smoke.ps1`

- [ ] **Step 1: Add normalized runtime usage and execution-step helpers**

```python
def normalize_context_usage(raw_usage: dict | None) -> dict[str, object]:
    usage = raw_usage or {}
    used = int(usage.get("totalTokens") or usage.get("input_tokens") or 0)
    maximum = int(usage.get("maxTokens") or usage.get("context_window") or 0)
    percent = round((used / maximum) * 100, 1) if maximum > 0 else None
    return {
        "usedTokens": used,
        "maxTokens": maximum,
        "percentUsed": percent,
        "available": maximum > 0,
        "inputTokens": int(usage.get("input_tokens") or 0),
        "outputTokens": int(usage.get("output_tokens") or 0),
    }


def normalize_run_step(event: dict[str, object]) -> dict[str, object]:
    return {
        "kind": str(event.get("type") or ""),
        "label": str(event.get("tool") or event.get("name") or event.get("type") or ""),
        "summary": str(event.get("summary") or event.get("message") or ""),
        "command": str(event.get("command") or ""),
        "status": "error" if bool(event.get("isError")) else "ok",
        "rawText": str(event.get("rawText") or ""),
    }
```

- [ ] **Step 2: Add shell metadata builder in backend status/bootstrap**

```python
def _chat_shell_payload() -> dict[str, object]:
    model_catalog = _model_catalog()
    library = _build_library()
    permission_default = "auto"
    return {
        "permissionDefault": permission_default,
        "contextUsage": {
            "available": False,
            "usedTokens": 0,
            "maxTokens": 0,
            "percentUsed": None,
            "inputTokens": 0,
            "outputTokens": 0,
        },
        "slashSections": [
            {"id": "mcp", "label": "MCP", "count": len(library.get("mcps") or [])},
            {"id": "model", "label": "Model", "count": len(model_catalog)},
            {"id": "reasoning", "label": "Reasoning", "count": 3},
            {"id": "personality", "label": "Personality", "count": 3},
            {"id": "status", "label": "Status", "count": 3},
            {"id": "plan", "label": "Plan", "count": 2},
            {"id": "skills", "label": "Skills", "count": len(library.get("skills") or [])},
        ],
    }
```

And wire it into `_build_status()`:

```python
payload = {
    ...,
    "chatShell": _chat_shell_payload(),
    "webDefaults": {
        "permissionMode": "auto",
        ...
    },
}
```

- [ ] **Step 3: Update permission defaults in scripts and request handling**

```powershell
$env:CLAUDE_WEB_PERMISSION_MODE = if ($env:CLAUDE_WEB_PERMISSION_MODE) { $env:CLAUDE_WEB_PERMISSION_MODE } else { "auto" }
```

And in Python:

```python
permission_mode = str(data.get("permissionMode") or CLAUDE_WEB_PERMISSION_MODE or "auto").strip()
if permission_mode == "auto":
    command.append("--enable-auto-mode")
```

- [ ] **Step 4: Run the backend verification set**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\chat-shell-runtime-smoke.ps1
python -m py_compile .\services\backend\app.py .\services\backend\claude_console_utils.py
```

Expected:

- `chat shell runtime ok`
- `py_compile` exits `0`

- [ ] **Step 5: Commit backend shell metadata and default-permission changes**

```bash
git add services/backend/claude_console_utils.py services/backend/app.py scripts/common-env.ps1 scripts/run-claude-console.ps1 scripts/open-claude-code.ps1 qa/windows-release/chat-shell-runtime-smoke.ps1
git commit -m "feat: add codex-style shell runtime metadata"
```

### Task 3: Add Failing Frontend Surface Tests For Codex-Style Shell Controls

**Files:**
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\codex-shell-surface.test.cjs`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html`

- [ ] **Step 1: Write the failing frontend shell surface test**

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const htmlPath = path.join(__dirname, '..', '..', 'apps', 'web', 'claude-console.html');
const html = fs.readFileSync(htmlPath, 'utf8');

test('codex shell surface exposes context ring, slash chooser, and run-step controls', () => {
  assert.match(html, /context-ring/, 'frontend should render a context ring surface');
  assert.match(html, /function renderContextUsageRing\(/, 'frontend should render context ring state');
  assert.match(html, /function openSlashChooser\(/, 'frontend should expose slash chooser opening');
  assert.match(html, /function renderComposerChips\(/, 'frontend should render structured composer chips');
  assert.match(html, /function toggleRunStepExpanded\(/, 'frontend should support run-step collapse and expand');
});
```

- [ ] **Step 2: Run the new surface test to verify it fails**

Run:

```powershell
node --test .\qa\windows-release\codex-shell-surface.test.cjs
```

Expected: FAIL because the Codex-style shell widgets do not exist yet.

- [ ] **Step 3: Commit the failing surface test scaffold**

```bash
git add qa/windows-release/codex-shell-surface.test.cjs
git commit -m "test: add codex shell surface coverage"
```

### Task 4: Rebuild The Frontend Top Strip, Context Ring, And Auto Permission UX

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html`
- Test: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\codex-shell-surface.test.cjs`

- [ ] **Step 1: Add the Codex-style top strip and context ring nodes**

```html
<div class="shell-strip" id="shell-strip">
  <button class="shell-icon-btn" id="btn-attach-file" type="button">＋</button>
  <div class="shell-pill"><select class="composer-select" id="model-route"></select></div>
  <div class="shell-pill"><select class="composer-select" id="reasoning-mode"></select></div>
  <div class="shell-pill"><select class="composer-select" id="permission-mode"></select></div>
  <button class="context-ring" id="context-ring" type="button" title="Context usage">
    <span class="context-ring-label" id="context-ring-label">--</span>
  </button>
</div>
```

- [ ] **Step 2: Render real backend context usage in the ring**

```javascript
function renderContextUsageRing() {
  const node = document.getElementById('context-ring');
  const label = document.getElementById('context-ring-label');
  if (!node || !label) return;
  const usage = appState.bootstrap?.chatShell?.contextUsage || {};
  if (!usage.available) {
    label.textContent = '--';
    node.title = 'Context usage not available yet';
    return;
  }
  label.textContent = `${Math.round(Number(usage.percentUsed || 0))}%`;
  node.title = `Used ${usage.usedTokens} / ${usage.maxTokens} tokens`;
}
```

- [ ] **Step 3: Make auto permission the visible default**

```javascript
const optionLabels = {
  auto: 'Auto',
  default: t('permission_default'),
  acceptEdits: t('permission_accept_edits'),
  bypassPermissions: t('permission_bypass'),
};
```

And ensure bootstrap hydration prefers auto:

```javascript
appState.permissionMode = payload.webDefaults?.permissionMode || 'auto';
document.getElementById('permission-mode').value = appState.permissionMode;
```

- [ ] **Step 4: Run shell surface and inline JS validation**

Run:

```powershell
node --test .\qa\windows-release\codex-shell-surface.test.cjs
python .\.github\scripts\check_inline_js.py .\apps\web\claude-console.html
```

Expected:

- `ok 1 - codex shell surface exposes context ring, slash chooser, and run-step controls`
- `inline JS ok: ...\apps\web\claude-console.html`

- [ ] **Step 5: Commit top strip, context ring, and auto permission UI**

```bash
git add apps/web/claude-console.html qa/windows-release/codex-shell-surface.test.cjs
git commit -m "feat: add codex-style shell strip and context ring"
```

### Task 5: Add Structured Slash Chooser And Composer Chips

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html`
- Test: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\codex-shell-surface.test.cjs`

- [ ] **Step 1: Extend backend shell payload with slash sections and items**

```python
def _chat_shell_payload() -> dict[str, object]:
    ...
    return {
        ...,
        "slashSections": [
            {"id": "mcp", "label": "MCP", "items": _slash_items_for_mcp()},
            {"id": "model", "label": "Model", "items": _slash_items_for_models()},
            {"id": "reasoning", "label": "Reasoning", "items": _slash_items_for_reasoning()},
            {"id": "personality", "label": "Personality", "items": _slash_items_for_personality()},
            {"id": "status", "label": "Status", "items": _slash_items_for_status()},
            {"id": "plan", "label": "Plan", "items": _slash_items_for_plan()},
            {"id": "skills", "label": "Skills", "items": _slash_items_for_skills()},
        ],
    }
```

- [ ] **Step 2: Add composer chip state and slash chooser rendering**

```javascript
const appState = {
  ...,
  composerChips: [],
  slashChooserOpen: false,
  slashChooserQuery: '',
  slashChooserSection: 'skills',
};

function openSlashChooser() {
  appState.slashChooserOpen = true;
  renderSlashChooser();
}

function selectSlashItem(sectionId, item) {
  appState.composerChips.push({
    id: `${sectionId}:${item.id}`,
    sectionId,
    label: item.label,
    value: item.id,
  });
  renderComposerChips();
}
```

- [ ] **Step 3: Submit chips as structured metadata**

```javascript
body: JSON.stringify({
  prompt,
  mode: appState.mode,
  agentMode: appState.agentMode,
  permissionMode: appState.permissionMode,
  sessionId: requestSessionId,
  chipSelections: appState.composerChips,
})
```

And in backend:

```python
chip_selections = data.get("chipSelections") if isinstance(data.get("chipSelections"), list) else []
prepared_prompt = _apply_chip_selections_to_prompt(prepared_prompt, chip_selections)
```

- [ ] **Step 4: Verify slash chooser surface stays green**

Run:

```powershell
node --test .\qa\windows-release\codex-shell-surface.test.cjs
python .\.github\scripts\check_inline_js.py .\apps\web\claude-console.html
```

Expected: both commands pass.

- [ ] **Step 5: Commit structured slash chooser and chip submission**

```bash
git add services/backend/app.py apps/web/claude-console.html
git commit -m "feat: add structured codex-style slash chooser"
```

### Task 6: Replace Raw Tool Flow With Collapsible Run-Step Cards

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\claude_console_utils.py`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html`
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\run-step-collapse-smoke.ps1`

- [ ] **Step 1: Add failing run-step collapse smoke**

```powershell
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Html = Get-Content -Raw (Join-Path $RepoRoot "apps\web\claude-console.html")
if ($Html -notmatch "toggleRunStepExpanded") { throw "missing run-step toggle support" }
if ($Html -notmatch "renderRunStepCards") { throw "missing run-step renderer" }
Write-Output "run step collapse surface ok"
```

- [ ] **Step 2: Emit normalized execution-step metadata from backend events**

```python
yield {
    "type": "run_step",
    "runId": run_id,
    "sessionId": actual_session_id,
    "step": normalize_run_step({...}),
}
```

- [ ] **Step 3: Render collapsible execution cards in frontend**

```javascript
function toggleRunStepExpanded(messageId) {
  appState.runStepExpanded[messageId] = !appState.runStepExpanded[messageId];
  scheduleMessagesRender({ force: true });
}

function renderRunStepCards(steps, messageId) {
  const expanded = !!appState.runStepExpanded[messageId];
  ...
}
```

- [ ] **Step 4: Run collapse smoke and JS validation**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\run-step-collapse-smoke.ps1
python .\.github\scripts\check_inline_js.py .\apps\web\claude-console.html
```

Expected: both commands pass.

- [ ] **Step 5: Commit run-step card rendering**

```bash
git add services/backend/claude_console_utils.py apps/web/claude-console.html qa/windows-release/run-step-collapse-smoke.ps1
git commit -m "feat: add collapsible codex-style run steps"
```

### Task 7: Fix Streaming Scroll Lock And Add Return-To-Bottom Behavior

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html`
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\scroll-autostick-smoke.ps1`

- [ ] **Step 1: Add failing streaming-scroll smoke**

```powershell
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Html = Get-Content -Raw (Join-Path $RepoRoot "apps\web\claude-console.html")
if ($Html -notmatch "userDetachedFromBottom") { throw "missing detached-from-bottom state" }
if ($Html -notmatch "returnToBottom") { throw "missing return-to-bottom handler" }
Write-Output "scroll autostick surface ok"
```

- [ ] **Step 2: Track manual upward scrolling and suppress auto-stick**

```javascript
const appState = {
  ...,
  userDetachedFromBottom: false,
};

function messageShouldStickToBottom(container) {
  if (appState.userDetachedFromBottom) return false;
  ...
}

messagesNode.addEventListener('scroll', () => {
  const gap = messagesNode.scrollHeight - (messagesNode.scrollTop + messagesNode.clientHeight);
  appState.userDetachedFromBottom = gap > 96;
});
```

- [ ] **Step 3: Add explicit return-to-bottom control**

```javascript
function returnToBottom() {
  appState.userDetachedFromBottom = false;
  appState.forceMessageScroll = true;
  renderMessages();
}
```

- [ ] **Step 4: Run the scroll smoke and JS validation**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\scroll-autostick-smoke.ps1
python .\.github\scripts\check_inline_js.py .\apps\web\claude-console.html
```

Expected: both commands pass.

- [ ] **Step 5: Commit scroll behavior fixes**

```bash
git add apps/web/claude-console.html qa/windows-release/scroll-autostick-smoke.ps1
git commit -m "fix: release streaming autostick when user scrolls away"
```

### Task 8: Wire New Shell Tests Into CI And Release Validation

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\ci.yml`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\release.yml`
- Test: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\chat-shell-runtime-smoke.ps1`
- Test: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\codex-shell-surface.test.cjs`
- Test: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\run-step-collapse-smoke.ps1`
- Test: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\scroll-autostick-smoke.ps1`

- [ ] **Step 1: Add new shell-upgrade checks to CI and release workflows**

```yaml
node --test qa/router/custom-router.test.cjs qa/windows-release/frontend-install-surface.test.cjs qa/windows-release/readme-bootstrap-surface.test.cjs qa/windows-release/release-workflow.test.cjs qa/windows-release/library-collapse-surface.test.cjs qa/windows-release/startup-setup-surface.test.cjs qa/windows-release/codex-shell-surface.test.cjs
.\qa\windows-release\pty-compat-notice-smoke.ps1
.\qa\windows-release\mcp-status-parse-smoke.ps1
.\qa\windows-release\setup-status-classification-smoke.ps1
.\qa\windows-release\chat-shell-runtime-smoke.ps1
.\qa\windows-release\run-step-collapse-smoke.ps1
.\qa\windows-release\scroll-autostick-smoke.ps1
```

- [ ] **Step 2: Run workflow surface verification locally**

Run:

```powershell
node --test .\qa\windows-release\release-workflow.test.cjs .\qa\windows-release\codex-shell-surface.test.cjs
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\chat-shell-runtime-smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\run-step-collapse-smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\scroll-autostick-smoke.ps1
```

Expected: all commands pass.

- [ ] **Step 3: Commit workflow coverage updates**

```bash
git add .github/workflows/ci.yml .github/workflows/release.yml
git commit -m "test: cover codex-style shell upgrade in ci"
```

### Task 9: Final Validation And Release

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\package.json`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\package-lock.json`

- [ ] **Step 1: Run the full shell-upgrade validation set**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\pty-compat-notice-smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\mcp-status-parse-smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\setup-status-classification-smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\chat-shell-runtime-smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\run-step-collapse-smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\scroll-autostick-smoke.ps1
node --test .\qa\windows-release\library-collapse-surface.test.cjs .\qa\windows-release\startup-setup-surface.test.cjs .\qa\windows-release\codex-shell-surface.test.cjs .\qa\windows-release\release-workflow.test.cjs
python .\.github\scripts\check_inline_js.py .\apps\web\claude-console.html
python -m py_compile .\services\backend\app.py .\services\backend\claude_console_utils.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\package-release-smoke.ps1
```

Expected: all commands pass.

- [ ] **Step 2: Verify the real local runtime behavior**

Run:

```powershell
Invoke-WebRequest 'http://127.0.0.1:18882/claude-console/bootstrap' -UseBasicParsing | Select-Object -ExpandProperty Content
claude auth status
@'
import json, urllib.request
req = urllib.request.Request(
    'http://127.0.0.1:18882/claude-console/chat',
    data=json.dumps({
        'prompt': 'reply with ok',
        'mode': 'compatible-coding,MiniMax-M2.7',
        'agentMode': 'none',
        'permissionMode': 'auto',
        'sessionId': ''
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req, timeout=120) as resp:
    print(resp.status)
    print(resp.read(1200).decode('utf-8', errors='replace'))
'@ | .\.venv\Scripts\python.exe -
```

Expected:

- bootstrap returns the new shell metadata
- auth status is informative but not required for the custom-provider route
- chat still succeeds through `MiniMax-M2.7`

- [ ] **Step 3: Bump version and package the release**

```bash
git add package.json package-lock.json
git commit -m "chore: release v0.1.15"
```

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\package-release.ps1 -Version 0.1.15
```

Expected: `dist/easy-claudecode.app-win-0.1.15-setup.exe` exists.

- [ ] **Step 4: Publish**

```bash
git push origin main
git tag v0.1.15
git push origin v0.1.15
```

- [ ] **Step 5: Confirm GitHub release artifact**

```powershell
Invoke-RestMethod 'https://api.github.com/repos/Arthurescc/easy-claudecode.app-win/releases/tags/v0.1.15' | ConvertTo-Json -Depth 6
```

Expected: release exists with `easy-claudecode.app-win-0.1.15-setup.exe`.

## Self-Review

- Spec coverage:
  - backend shell metadata is covered in Tasks 1-2
  - Codex-style top strip and context ring are covered in Task 4
  - structured slash chooser and chips are covered in Task 5
  - collapsible run-step cards are covered in Task 6
  - streaming scroll behavior is covered in Task 7
  - CI/release and final publish are covered in Tasks 8-9
- Placeholder scan:
  - no `TBD`, `TODO`, or undefined “handle later” steps remain
- Type consistency:
  - the plan consistently uses `chatShell`, `contextUsage`, `slashSections`, `permissionDefault`, and `chipSelections`
