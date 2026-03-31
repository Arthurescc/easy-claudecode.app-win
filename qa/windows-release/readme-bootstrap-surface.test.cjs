const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const readmePath = path.join(__dirname, '..', '..', 'README.md');
const readme = fs.readFileSync(readmePath, 'utf8');

test('README exposes feature overview and one-line Windows install command', () => {
  assert.match(readme, /##\s+Features/i, 'README should have a Features section');
  assert.match(readme, /One-Line Install|Install In One Command/i, 'README should advertise one-line install');
  assert.match(readme, /raw\.githubusercontent\.com\/Arthurescc\/easy-claudecode\.app-win\/main\/scripts\/install-from-github\.ps1/i, 'README should include the public bootstrap script URL');
  assert.match(readme, /compatible provider/i, 'README should explain provider-based model access');
});
