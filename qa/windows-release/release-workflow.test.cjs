const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const workflowPath = path.join(__dirname, '..', '..', '.github', 'workflows', 'release.yml');
const workflow = fs.readFileSync(workflowPath, 'utf8');

test('release workflow uploads and publishes the setup exe artifact', () => {
  assert.match(
    workflow,
    /dist\/easy-claudecode\.app-win-\$\{\{ env\.RELEASE_VERSION \}\}-setup\.exe/,
    'release workflow should reference the setup exe'
  );
  assert.doesNotMatch(
    workflow,
    /files:\s*dist\/easy-claudecode\.app-win-\$\{\{ env\.RELEASE_VERSION \}\}\.zip/,
    'release workflow should not publish the legacy zip as the main release asset'
  );
});
