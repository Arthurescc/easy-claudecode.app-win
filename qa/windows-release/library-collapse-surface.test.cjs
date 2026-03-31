const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const htmlPath = path.join(__dirname, '..', '..', 'apps', 'web', 'claude-console.html');
const html = fs.readFileSync(htmlPath, 'utf8');

test('skills sidebar supports collapsing agents, skills, and MCP groups', () => {
  assert.match(html, /LIBRARY_COLLAPSE_KEY/, 'frontend should persist library collapse state');
  assert.match(html, /function toggleLibrarySectionCollapsed\(/, 'frontend should toggle library section collapse');
  assert.match(html, /data-library-toggle=/, 'frontend should render collapse toggles for library groups');
});
