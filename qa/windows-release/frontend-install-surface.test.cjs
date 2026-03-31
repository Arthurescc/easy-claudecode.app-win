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
