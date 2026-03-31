const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const htmlPath = path.join(__dirname, '..', '..', 'apps', 'web', 'claude-console.html');
const html = fs.readFileSync(htmlPath, 'utf8');

test('startup setup surface exposes one-shot localStorage key and auto-open guard', () => {
  assert.match(html, /STARTUP_SETUP_DISMISSED_KEY/, 'frontend should define a startup setup dismissed key');
  assert.match(html, /startupSetupAutoOpened/, 'frontend should track whether startup setup was auto-opened');
  assert.match(html, /function shouldAutoOpenStartupSetup\(/, 'frontend should expose startup setup auto-open logic');
  assert.match(
    html,
    /window\.localStorage\.getItem\(STARTUP_SETUP_DISMISSED_KEY\)/,
    'auto-open guard should read startup setup dismissed key from localStorage',
  );
});

test('bootstrap payload stores setupStatus and startup auto-open uses startup reason', () => {
  assert.match(html, /payload\.setupStatus/, 'bootstrap payload should include setup status');
  assert.match(html, /appState\.setupStatus/, 'app state should store setup status');
  assert.match(
    html,
    /openSettingsDialog\(\{\s*reason:\s*'startup-setup'\s*\}\)/,
    'loadBootstrap should auto-open settings with startup reason',
  );
});

test('settings dialog shows a connection strategy summary for startup setup', () => {
  assert.match(
    html,
    /id="settings-connection-summary"/,
    'settings dialog should include a connection strategy summary node',
  );
  assert.match(
    html,
    /function renderSettingsConnectionSummary\(/,
    'frontend should render connection strategy summary from setup status',
  );
  assert.match(
    html,
    /Official Claude login is not required/,
    'custom provider ready copy should clarify that official login is optional',
  );
});
