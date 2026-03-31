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
