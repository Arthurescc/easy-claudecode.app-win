# Startup Setup And Existing Config Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Windows app reuse a machine's existing provider/login/library state on startup, auto-open settings only when the machine is not ready, and stop presenting official Claude login as required when a self-hosted provider route already works.

**Architecture:** Extend backend bootstrap/settings payloads with a `setupStatus` summary derived from existing runtime signals, then let the frontend drive welcome-screen copy and one-time startup prompting from that single source of truth. Keep execution routing unchanged for working custom-provider paths, and limit UI changes to onboarding/status presentation plus one-time localStorage-based auto-open behavior.

**Tech Stack:** Flask backend, single-file HTML/JS frontend, PowerShell smoke tests, Node `--test` surface checks

---

## File Structure

- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py`
  - Add helper functions that classify machine readiness, Claude auth state, provider configuration, and recommended setup behavior.
  - Include `setupStatus` in bootstrap and settings responses.
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html`
  - Add startup prompt state, one-time settings auto-open logic, and connection-strategy UI/copy that reflects `setupStatus`.
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\setup-status-classification-smoke.ps1`
  - Verify backend setup classification for configured-provider, official-login, and unconfigured cases.
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\startup-setup-surface.test.cjs`
  - Verify frontend contains the startup setup decision helpers and strategy UI hooks.
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\ci.yml`
  - Add the new startup setup smoke tests.
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\release.yml`
  - Add the new startup setup smoke tests to release validation.

### Task 1: Add Backend Setup-Status Regression Coverage

**Files:**
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\setup-status-classification-smoke.ps1`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py`

- [ ] **Step 1: Write the failing backend smoke test**

```powershell
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PythonBin = (Resolve-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")).Path

@'
import json
import sys

sys.path.insert(0, r"C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend")
import app  # noqa: E402


def build_case(*, values, auth_result, library_counts, routes):
    original_load = app._load_editable_settings
    original_capture = app._run_capture
    original_library = app._build_library
    original_route_options = app._route_options
    try:
        app._load_editable_settings = lambda: values
        app._run_capture = lambda *args, **kwargs: auth_result
        app._build_library = lambda: {"counts": library_counts, "skills": [], "agents": [], "mcps": [], "automations": []}
        app._route_options = lambda: routes
        payload = app._build_status(force_refresh=True)
        return payload["setupStatus"]
    finally:
        app._load_editable_settings = original_load
        app._run_capture = original_capture
        app._build_library = original_library
        app._route_options = original_route_options


custom_ready = build_case(
    values={
        "CODING_COMPATIBLE_API_KEY": "sk-test",
        "CODING_COMPATIBLE_UPSTREAM": "https://api.minimaxi.com/anthropic/v1/messages",
        "ANTHROPIC_THINKING_API_KEY": "",
        "ANTHROPIC_THINKING_UPSTREAM": "",
        "EASY_CLAUDECODE_DEFAULT_ROUTE": "compatible-coding,MiniMax-M2.7",
        "CLAUDE_CONSOLE_LOCALE": "zh-CN",
    },
    auth_result={"ok": False, "stdout": '{"loggedIn": false, "authMethod": "none"}', "stderr": "", "returncode": 1},
    library_counts={"skills": 2, "agents": 1, "mcps": 0, "automations": 0},
    routes=[{"id": "compatible-coding,MiniMax-M2.7", "label": "MiniMax-compatible · MiniMax M2.7"}],
)
assert custom_ready["isReady"] is True, custom_ready
assert custom_ready["recommendedPath"] == "custom-provider", custom_ready
assert custom_ready["shouldPromptSettings"] is False, custom_ready

official_ready = build_case(
    values={
        "CODING_COMPATIBLE_API_KEY": "",
        "CODING_COMPATIBLE_UPSTREAM": "",
        "ANTHROPIC_THINKING_API_KEY": "",
        "ANTHROPIC_THINKING_UPSTREAM": "",
        "EASY_CLAUDECODE_DEFAULT_ROUTE": "",
        "CLAUDE_CONSOLE_LOCALE": "zh-CN",
    },
    auth_result={"ok": True, "stdout": '{"loggedIn": true, "authMethod": "oauth"}', "stderr": "", "returncode": 0},
    library_counts={"skills": 0, "agents": 0, "mcps": 0, "automations": 0},
    routes=[],
)
assert official_ready["isReady"] is True, official_ready
assert official_ready["recommendedPath"] == "official-claude", official_ready
assert official_ready["shouldPromptSettings"] is False, official_ready

unconfigured = build_case(
    values={
        "CODING_COMPATIBLE_API_KEY": "",
        "CODING_COMPATIBLE_UPSTREAM": "",
        "ANTHROPIC_THINKING_API_KEY": "",
        "ANTHROPIC_THINKING_UPSTREAM": "",
        "EASY_CLAUDECODE_DEFAULT_ROUTE": "",
        "CLAUDE_CONSOLE_LOCALE": "zh-CN",
    },
    auth_result={"ok": False, "stdout": '{"loggedIn": false, "authMethod": "none"}', "stderr": "", "returncode": 1},
    library_counts={"skills": 0, "agents": 0, "mcps": 0, "automations": 0},
    routes=[],
)
assert unconfigured["isReady"] is False, unconfigured
assert unconfigured["shouldPromptSettings"] is True, unconfigured
assert unconfigured["recommendedPath"] == "settings", unconfigured
print("setup status classification ok")
'@ | & $PythonBin -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
```

- [ ] **Step 2: Run the new smoke test to verify it fails**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\setup-status-classification-smoke.ps1
```

Expected: FAIL because `setupStatus` is missing from `_build_status()` and/or the expected classification keys do not exist yet.

- [ ] **Step 3: Commit the failing test scaffold**

```bash
git add qa/windows-release/setup-status-classification-smoke.ps1
git commit -m "test: add startup setup classification smoke"
```

### Task 2: Implement Backend Setup Classification

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py:439-460`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py:2671-2806`
- Test: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\setup-status-classification-smoke.ps1`

- [ ] **Step 1: Add Claude auth parsing and setup-status helper functions**

```python
def _parse_claude_auth_status() -> dict[str, object]:
    claude_cli_available, claude_real_bin = _resolve_real_claude_bin()
    if not claude_cli_available:
        return {
            "available": False,
            "loggedIn": False,
            "authMethod": "none",
            "raw": f"Claude CLI not found: {claude_real_bin or 'claude'}",
        }
    result = _run_capture([CLAUDE_WRAPPER_PATH, "auth", "status"], cwd=CLAUDE_WORKSPACE_ROOT, timeout=10)
    raw_text = str(result.get("stdout") or result.get("stderr") or "").strip()
    try:
        payload = json.loads(raw_text) if raw_text else {}
    except Exception:
        payload = {}
    return {
        "available": True,
        "loggedIn": bool(payload.get("loggedIn")),
        "authMethod": str(payload.get("authMethod") or "none"),
        "raw": raw_text,
    }


def _has_provider_credentials(values: dict[str, str]) -> bool:
    return any(
        str(values.get(key) or "").strip()
        for key in ("CODING_COMPATIBLE_API_KEY", "ANTHROPIC_THINKING_API_KEY")
    )


def _setup_status_payload(*, values: dict[str, str], auth_status: dict[str, object], library: dict[str, object]) -> dict[str, object]:
    route_options = _route_options()
    has_provider = _has_provider_credentials(values)
    has_routes = bool(route_options)
    claude_logged_in = bool(auth_status.get("loggedIn"))
    library_counts = library.get("counts") if isinstance(library, dict) else {}
    has_library = any(int((library_counts or {}).get(key) or 0) > 0 for key in ("skills", "agents", "mcps"))
    custom_ready = has_provider and has_routes
    official_ready = bool(auth_status.get("available")) and claude_logged_in
    is_ready = custom_ready or official_ready
    recommended_path = "custom-provider" if custom_ready else "official-claude" if official_ready else "settings"
    return {
        "isReady": is_ready,
        "shouldPromptSettings": not is_ready,
        "recommendedPath": recommended_path,
        "customProviderReady": custom_ready,
        "officialClaudeReady": official_ready,
        "hasExistingLibrary": has_library,
        "hasProviderCredentials": has_provider,
        "hasRouteOptions": has_routes,
        "defaultRoute": str(values.get("EASY_CLAUDECODE_DEFAULT_ROUTE") or "").strip(),
        "claudeAuth": auth_status,
    }
```

- [ ] **Step 2: Wire `setupStatus` into `_build_status()` and settings responses**

```python
def _build_status(force_refresh: bool = False) -> dict:
    ...
    current_settings = _load_editable_settings()
    library_payload = _build_library()
    auth_status = _parse_claude_auth_status()
    payload = {
        ...,
        "claude": {
            ...,
            "loggedIn": bool(auth_status.get("loggedIn")),
            "authMethod": str(auth_status.get("authMethod") or "none"),
        },
        "setupStatus": _setup_status_payload(
            values=current_settings,
            auth_status=auth_status,
            library=library_payload,
        ),
        ...
    }
```

And include the same `setupStatus` in `GET /claude-console/settings` and `POST /claude-console/settings`:

```python
return jsonify(
    {
        "ok": True,
        "envFile": EASY_CLAUDECODE_ENV_FILE,
        "values": _load_editable_settings(),
        "providers": _provider_settings_payload(),
        "routeOptions": _route_options(),
        "modelCatalog": _model_catalog(),
        "setupStatus": _build_status(force_refresh=True).get("setupStatus", {}),
        "installers": {...},
    }
)
```

- [ ] **Step 3: Run the backend smoke test and Python compile checks**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\setup-status-classification-smoke.ps1
python -m py_compile .\services\backend\app.py .\services\backend\claude_console_utils.py
```

Expected:

- `setup status classification ok`
- no `py_compile` output and exit code `0`

- [ ] **Step 4: Commit the backend implementation**

```bash
git add services/backend/app.py qa/windows-release/setup-status-classification-smoke.ps1
git commit -m "feat: classify startup setup readiness"
```

### Task 3: Add Frontend Startup-Setup Surface Tests

**Files:**
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\startup-setup-surface.test.cjs`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html`

- [ ] **Step 1: Write the failing frontend surface test**

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const htmlPath = path.join(__dirname, '..', '..', 'apps', 'web', 'claude-console.html');
const html = fs.readFileSync(htmlPath, 'utf8');

test('startup setup flow detects bootstrap setup status and can auto-open settings once', () => {
  assert.match(html, /STARTUP_SETUP_DISMISSED_KEY/, 'frontend should persist one-time startup setup prompt state');
  assert.match(html, /function shouldAutoOpenStartupSetup\(/, 'frontend should decide whether startup setup should auto-open');
  assert.match(html, /setupStatus/, 'frontend should consume backend setup status');
  assert.match(html, /settings-connection-summary/, 'settings dialog should render connection strategy summary');
});
```

- [ ] **Step 2: Run the new surface test to verify it fails**

Run:

```powershell
node --test .\qa\windows-release\startup-setup-surface.test.cjs
```

Expected: FAIL because the new startup-setup helpers and summary node do not exist yet.

- [ ] **Step 3: Commit the failing surface test scaffold**

```bash
git add qa/windows-release/startup-setup-surface.test.cjs
git commit -m "test: add startup setup frontend surface coverage"
```

### Task 4: Implement Frontend Startup Reuse And One-Time Prompting

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html:1472-1519`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html:1526-2068`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html:2280-2288`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html:2511-2550`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html:3812-3868`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html:4440-4480`
- Test: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\startup-setup-surface.test.cjs`

- [ ] **Step 1: Add startup-setup state, storage keys, and UI placeholders**

```html
<div class="overlay-note" id="settings-dialog-message">...</div>
<div class="overlay-note tight" id="settings-connection-summary"></div>
<div class="settings-help span-2" id="settings-connection-actions"></div>
```

```javascript
const STARTUP_SETUP_DISMISSED_KEY = 'claude-console-startup-setup-dismissed-v1';

const appState = {
  ...,
  setupStatus: {},
  startupSetupAutoOpened: false,
};
```

- [ ] **Step 2: Add helper functions for readiness-based messaging**

```javascript
function setupStatus() {
  return appState.bootstrap?.setupStatus || {};
}

function startupSetupDismissed() {
  return window.localStorage.getItem(STARTUP_SETUP_DISMISSED_KEY) === '1';
}

function shouldAutoOpenStartupSetup() {
  const status = setupStatus();
  if (!status || typeof status !== 'object') return false;
  if (appState.startupSetupAutoOpened || startupSetupDismissed()) return false;
  return !!status.shouldPromptSettings;
}

function connectionSummaryText(status = setupStatus()) {
  if (status.customProviderReady) return '已检测到当前机器已有可用 API / 路由配置，可直接使用。';
  if (status.officialClaudeReady) return '已检测到当前机器已有官方 Claude 登录，可直接使用。';
  return '当前机器还没有检测到可直接使用的接入方式，请先完成一次设置。';
}
```

- [ ] **Step 3: Populate `setupStatus` from bootstrap/settings and auto-open settings once when needed**

```javascript
function applyBootstrapPayload(payload, { fromCache = false } = {}) {
  ...
  appState.setupStatus = payload.setupStatus || {};
  ...
}

async function loadBootstrap(...) {
  ...
  const payload = await apiJson(...);
  applyBootstrapPayload(payload);
  ...
  if (!background && shouldAutoOpenStartupSetup()) {
    appState.startupSetupAutoOpened = true;
    await openSettingsDialog({ reason: 'startup-setup' });
  }
}
```

- [ ] **Step 4: Make the settings dialog strategy-aware and suppress official-login nudges when custom provider is ready**

```javascript
async function openSettingsDialog({ reason = 'manual' } = {}) {
  ...
  appState.setupStatus = payload.setupStatus || appState.setupStatus || {};
  renderConnectionSummary();
  if (reason === 'startup-setup' && appState.setupStatus.shouldPromptSettings) {
    setSettingsStatus('检测到当前机器还没有可直接使用的接入方式，请先选择一种连接方案。');
  } else {
    setSettingsStatus(t('current_config_loaded'));
  }
}

function renderConnectionSummary() {
  const summary = document.getElementById('settings-connection-summary');
  if (!summary) return;
  const status = appState.setupStatus || {};
  summary.textContent = connectionSummaryText(status);
}
```

And keep official-login guidance optional:

```javascript
function officialLoginHelpText(status = appState.setupStatus || {}) {
  if (status.customProviderReady) {
    return '当前已检测到自定义 provider 可用，官方 Claude 登录不是必需项。';
  }
  if (status.officialClaudeReady) {
    return '当前机器已检测到官方 Claude 登录。';
  }
  return '如果你要走官方 Claude 路径，再去终端执行 claude 并使用 /login。';
}
```

- [ ] **Step 5: Run the frontend surface test and inline JS validation**

Run:

```powershell
node --test .\qa\windows-release\startup-setup-surface.test.cjs
python .\.github\scripts\check_inline_js.py .\apps\web\claude-console.html
```

Expected:

- `ok 1 - startup setup flow detects bootstrap setup status and can auto-open settings once`
- `inline JS ok: ...\apps\web\claude-console.html`

- [ ] **Step 6: Commit the frontend onboarding implementation**

```bash
git add apps/web/claude-console.html qa/windows-release/startup-setup-surface.test.cjs
git commit -m "feat: reuse existing machine setup on startup"
```

### Task 5: Wire New Startup Tests Into CI And Release Validation

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\ci.yml`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\release.yml`
- Test: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\setup-status-classification-smoke.ps1`
- Test: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\windows-release\startup-setup-surface.test.cjs`

- [ ] **Step 1: Add the new startup setup tests to CI and release workflows**

```yaml
- name: Static checks
  run: |
    node --test qa/router/custom-router.test.cjs qa/windows-release/frontend-install-surface.test.cjs qa/windows-release/readme-bootstrap-surface.test.cjs qa/windows-release/release-workflow.test.cjs qa/windows-release/library-collapse-surface.test.cjs qa/windows-release/startup-setup-surface.test.cjs
    .\qa\windows-release\pty-compat-notice-smoke.ps1
    .\qa\windows-release\mcp-status-parse-smoke.ps1
    .\qa\windows-release\setup-status-classification-smoke.ps1
```

- [ ] **Step 2: Re-run workflow surface coverage and local startup tests**

Run:

```powershell
node --test .\qa\windows-release\release-workflow.test.cjs
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\setup-status-classification-smoke.ps1
node --test .\qa\windows-release\startup-setup-surface.test.cjs
```

Expected:

- release workflow surface test passes
- backend setup-status smoke passes
- frontend startup-setup surface test passes

- [ ] **Step 3: Commit the workflow updates**

```bash
git add .github/workflows/ci.yml .github/workflows/release.yml
git commit -m "test: cover startup setup reuse flow in ci"
```

### Task 6: End-To-End Verification And Release

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\package.json`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\package-lock.json`

- [ ] **Step 1: Verify the self-hosted route still works while Claude auth is logged out**

Run:

```powershell
@'
import json
import urllib.request
req = urllib.request.Request(
    'http://127.0.0.1:18882/claude-console/chat',
    data=json.dumps({
        'prompt': 'reply with ok',
        'mode': 'compatible-coding,MiniMax-M2.7',
        'agentMode': 'none',
        'permissionMode': 'default',
        'sessionId': ''
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req, timeout=120) as resp:
    print(resp.status)
    print(resp.readline().decode('utf-8', errors='replace').strip())
'@ | .\.venv\Scripts\python.exe -
claude auth status
```

Expected:

- chat request returns `200` and ends with `ok`
- `claude auth status` may still report `loggedIn: false`, proving official login is not required for the custom-provider path

- [ ] **Step 2: Run the full local verification set**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\pty-compat-notice-smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\mcp-status-parse-smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\setup-status-classification-smoke.ps1
node --test .\qa\windows-release\library-collapse-surface.test.cjs .\qa\windows-release\startup-setup-surface.test.cjs .\qa\windows-release\release-workflow.test.cjs
python .\.github\scripts\check_inline_js.py .\apps\web\claude-console.html
python -m py_compile .\services\backend\app.py .\services\backend\claude_console_utils.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-release\package-release-smoke.ps1
```

Expected: all commands pass without new failures.

- [ ] **Step 3: Bump version and publish**

```bash
git add package.json package-lock.json
git commit -m "chore: release v0.1.14"
git push origin main
git tag v0.1.14
git push origin v0.1.14
```

- [ ] **Step 4: Confirm GitHub release output**

Run:

```powershell
Invoke-RestMethod 'https://api.github.com/repos/Arthurescc/easy-claudecode.app-win/releases/tags/v0.1.14' | ConvertTo-Json -Depth 6
```

Expected: release exists with `easy-claudecode.app-win-0.1.14-setup.exe`.

## Self-Review

- Spec coverage:
  - backend readiness classification is covered in Tasks 1-2
  - startup prompt behavior is covered in Tasks 3-4
  - settings strategy messaging and login suppression are covered in Task 4
  - validation and release are covered in Tasks 5-6
- Placeholder scan:
  - no `TBD`, `TODO`, or undefined “handle later” steps remain
- Type consistency:
  - the plan consistently uses `setupStatus`, `shouldPromptSettings`, `customProviderReady`, and `officialClaudeReady`
