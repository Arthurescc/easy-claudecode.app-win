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
  assert.match(html, /function cycleModelSelection\(/, 'top model pill should be a real selector');
  assert.match(html, /function cyclePermissionSelection\(/, 'top permission pill should be a real selector');
  assert.match(html, /function cycleReasoningSelection\(/, 'top reasoning pill should be a real selector');
  assert.match(html, /shellSelections/, 'frontend should submit structured shell selections');
  assert.match(html, /prompt,\s*\n\s*shellSelections,/, 'frontend should send raw prompt alongside shell selections');
  assert.doesNotMatch(html, /prompt:\s*preparedPrompt/, 'frontend should not rewrite the main prompt client-side');
});
