$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HtmlPath = Join-Path $RepoRoot "apps\web\claude-console.html"
$NodeBin = (Get-Command node -ErrorAction Stop).Source
$env:SCROLL_SMOKE_HTML = $HtmlPath

@'
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const html = fs.readFileSync(process.env.SCROLL_SMOKE_HTML, 'utf8');

function extractFunctionSource(source, name) {
  const token = `function ${name}(`;
  const start = source.indexOf(token);
  assert.notEqual(start, -1, `missing function ${name}`);
  let signatureStarted = false;
  let parenDepth = 0;
  let bodyStart = -1;
  for (let index = start; index < source.length; index += 1) {
    const char = source[index];
    if (char === '(') {
      signatureStarted = true;
      parenDepth += 1;
      continue;
    }
    if (char === ')') {
      parenDepth -= 1;
      continue;
    }
    if (signatureStarted && parenDepth === 0 && char === '{') {
      bodyStart = index;
      break;
    }
  }
  let depth = 0;
  for (let index = bodyStart; index < source.length; index += 1) {
    const char = source[index];
    if (char === '{') depth += 1;
    if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        return source.slice(start, index + 1);
      }
    }
  }
  throw new Error(`unclosed function ${name}`);
}

const workspaceBody = { scrollHeight: 1400, scrollTop: 500, clientHeight: 420 };
const buttonState = { visible: false };
const scrollButton = {
  classList: {
    toggle(_name, visible) {
      buttonState.visible = Boolean(visible);
    },
  },
};

const sandbox = vm.createContext({
  appState: { messageScrollDetached: false, isStreaming: true },
  document: {
    getElementById(id) {
      if (id === 'workspace-body') return workspaceBody;
      if (id === 'btn-scroll-bottom') return scrollButton;
      return null;
    },
  },
  selectedMessages() {
    return [{ id: 'msg-1' }];
  },
  Boolean,
});

for (const name of ['messageScrollContainer', 'isMessageNearBottom', 'updateScrollJumpButton', 'syncMessageScrollState', 'scrollMessagesToBottom']) {
  vm.runInContext(extractFunctionSource(html, name), sandbox, { filename: `${name}.js` });
}

sandbox.syncMessageScrollState();
assert.equal(sandbox.appState.messageScrollDetached, true);
assert.equal(buttonState.visible, true);

sandbox.scrollMessagesToBottom({ force: true });
assert.equal(workspaceBody.scrollTop, workspaceBody.scrollHeight);
assert.equal(sandbox.appState.messageScrollDetached, false);
assert.equal(buttonState.visible, false);

console.log('scroll autostick smoke ok');
'@ | & $NodeBin -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
