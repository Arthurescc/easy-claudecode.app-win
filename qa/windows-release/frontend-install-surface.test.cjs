const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const htmlPath = path.join(__dirname, '..', '..', 'apps', 'web', 'claude-console.html');
const html = fs.readFileSync(htmlPath, 'utf8');

test('welcome and settings surfaces expose the optional Everything Claude Code install entry', () => {
  assert.match(html, /id="welcome-ecc-card"/, 'welcome surface should include an ECC card');
  assert.match(html, /id="settings-ecc-card"/, 'settings dialog should include an ECC card');
  assert.match(html, /id="settings-ecc-install"/, 'settings dialog should include an ECC install button');
  assert.match(html, /id="settings-default-route"/, 'settings dialog should expose model route selection');
  assert.match(html, /function renderEverythingClaudeCodeSurface\(/, 'frontend should render installer status');
  assert.match(html, /async function installEverythingClaudeCode\(/, 'frontend should support the install action');
});

test('frontend uses provider-generic settings and a registry-driven model surface', () => {
  assert.doesNotMatch(html, /DashScope/i, 'frontend should not expose stale DashScope branding');
  assert.match(html, /function renderProviderSettingsFields\(/, 'frontend should render provider settings dynamically');
  assert.match(html, /appState\.providerSettings/, 'frontend should track provider settings metadata');
  assert.match(html, /appState\.modelCatalog/, 'frontend should track a registry-driven model catalog');
  assert.match(html, /id="model-route-status"/, 'frontend should expose a model availability status surface');
  assert.match(html, /function refreshModelRouteStatus\(/, 'frontend should probe model availability when selection changes');
});
