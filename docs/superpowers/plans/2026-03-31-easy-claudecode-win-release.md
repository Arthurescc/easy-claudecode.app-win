# Windows Launcher And Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Windows-native `easy-claudecode.app-win` release that keeps route-based model selection working, shows a real desktop icon, offers optional Everything Claude Code setup, and publishes an installer `.exe`.

**Architecture:** Keep the existing backend and launcher structure, but move route tags to routing-only behavior at the router boundary and add a separate compiled setup executable for Windows release installs. Frontend changes stay inside the existing welcome/settings surfaces.

**Tech Stack:** Python/Flask, static HTML/CSS/JS, PowerShell, Node.js, C# WinForms, GitHub Actions

---

### Task 1: Lock The Route-Tag Regression

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\config\router\custom-router.js`
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\qa\router\custom-router.test.cjs`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\package.json`

- [ ] **Step 1: Write the failing router regression test**

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');

const router = require('../../config/router/custom-router.js');

test('route markers select the target route but do not remain in forwarded text', async () => {
  const req = {
    body: {
      messages: [
        {
          role: 'user',
          content: '[route:glm5]\nPlease explain the result of 2 + 2.',
        },
      ],
    },
  };

  const target = await router(req);

  assert.equal(target, 'dashscope-codingplan,glm-5');
  assert.equal(req.body.messages[0].content.includes('[route:glm5]'), false);
  assert.match(req.body.messages[0].content, /2 \+ 2/);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test qa/router/custom-router.test.cjs`
Expected: FAIL because the route marker is still present in `req.body.messages[0].content`.

- [ ] **Step 3: Implement minimal route stripping**

```javascript
function stripRouteMarkers(value) {
  return String(value || '')
    .replace(/\[route:[^\]]+\]\s*/ig, '')
    .trim();
}
```

Apply the helper when an explicit route is matched so the request object keeps the real user text but not the routing marker.

- [ ] **Step 4: Re-run the router test**

Run: `node --test qa/router/custom-router.test.cjs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/router/custom-router.js qa/router/custom-router.test.cjs package.json
git commit -m "fix: strip route markers before forwarding prompts"
```

### Task 2: Add Windows Icon And Installer Build Outputs

**Files:**
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\desktop-windows\assets\ClaudeCodeApp.ico`
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\desktop-windows\installer\Program.cs`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\build-desktop-launcher.ps1`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\package-release.ps1`

- [ ] **Step 1: Write the failing packaging smoke expectation**

```powershell
.\scripts\package-release.ps1 -Version 0.0.0-test
if (-not (Test-Path ".\dist\easy-claudecode.app-win-0.0.0-test-setup.exe")) {
    throw "setup exe was not created"
}
```

- [ ] **Step 2: Run the smoke expectation to verify it fails**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -Command "<smoke script above>"`
Expected: FAIL because only zip output exists today.

- [ ] **Step 3: Add the launcher icon and setup compiler path**

```powershell
$CompileArgs += "/win32icon:$IconPath"
```

Compile both the runtime launcher and the new setup executable, and make the setup executable embed the staged zip payload as a resource.

- [ ] **Step 4: Re-run release packaging smoke**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\package-release.ps1 -Version 0.0.0-test`
Expected: PASS and `dist\easy-claudecode.app-win-0.0.0-test-setup.exe` exists.

- [ ] **Step 5: Commit**

```bash
git add apps/desktop-windows/assets apps/desktop-windows/installer scripts/build-desktop-launcher.ps1 scripts/package-release.ps1
git commit -m "feat: add windows installer exe packaging"
```

### Task 3: Surface Optional Everything Claude Code Setup

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\services\backend\app.py`
- Create: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\scripts\install-everything-claude-code.ps1`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\web\claude-console.html`

- [ ] **Step 1: Write the failing backend/frontend expectation**

```powershell
$status = Invoke-WebRequest -Uri "http://127.0.0.1:18882/claude-console/bootstrap" -UseBasicParsing | Select-Object -ExpandProperty Content | ConvertFrom-Json
if (-not $status.installers.everythingClaudeCode) {
    throw "bootstrap missing Everything Claude Code installer metadata"
}
```

- [ ] **Step 2: Run the expectation to verify it fails**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -Command "<smoke script above>"`
Expected: FAIL because bootstrap has no installer metadata yet.

- [ ] **Step 3: Add the optional install path**

```python
"everythingClaudeCode": {
    "available": True,
    "optional": True,
    "defaultSelected": False,
}
```

Add a backend endpoint that runs the PowerShell installer helper, then expose a welcome/settings action in the frontend that lets the user opt into the install.

- [ ] **Step 4: Re-run bootstrap smoke and a frontend syntax check**

Run: `python -m py_compile services/backend/app.py`
Run: `python .github/scripts/check_inline_js.py apps/web/claude-console.html`
Expected: both PASS

- [ ] **Step 5: Commit**

```bash
git add services/backend/app.py scripts/install-everything-claude-code.ps1 apps/web/claude-console.html
git commit -m "feat: add optional everything-claude-code setup"
```

### Task 4: Refresh CI, Release, And Verification

**Files:**
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\ci.yml`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\.github\workflows\release.yml`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\README.md`
- Modify: `C:\Users\Administrator\Documents\Playground\easy-claudecode.app-win\apps\desktop-windows\README.md`

- [ ] **Step 1: Write the failing release assertion**

```powershell
if (-not (Test-Path "dist/easy-claudecode.app-win-$env:RELEASE_VERSION-setup.exe")) {
    throw "release installer exe missing"
}
```

- [ ] **Step 2: Run the local release workflow equivalent to verify it fails first**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\package-release.ps1 -Version 0.0.0-ci`
Expected: FAIL against the new assertion before workflow/docs updates are complete.

- [ ] **Step 3: Update CI/release/docs to match installer-first shipping**

```yaml
with:
  files: dist/easy-claudecode.app-win-${{ env.RELEASE_VERSION }}-setup.exe
```

Update smoke checks and README copy so the public repo clearly describes the installer `.exe`, optional ECC setup, and standalone app behavior.

- [ ] **Step 4: Run the final verification set**

Run: `node --test qa/router/custom-router.test.cjs`
Run: `python -m py_compile services/backend/app.py services/backend/claude_console_utils.py`
Run: `python .github/scripts/check_inline_js.py apps/web/claude-console.html`
Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\package-release.ps1 -Version 0.0.0-verify`
Run: `powershell -NoProfile -ExecutionPolicy Bypass -Command "$body = @{ mode = 'glm5'; agentMode = 'none'; permissionMode = 'default'; prompt = 'Please explain the result of 2 + 2 in one sentence.' } | ConvertTo-Json; Invoke-WebRequest -Uri 'http://127.0.0.1:18882/claude-console/quick-run' -Method Post -ContentType 'application/json' -Body $body -UseBasicParsing | Select-Object -ExpandProperty Content"`
Expected: all PASS, and the final quick-run output answers the math question instead of asking what `[route:glm5]` means.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows README.md apps/desktop-windows/README.md
git commit -m "chore: ship installer-first windows release"
```
