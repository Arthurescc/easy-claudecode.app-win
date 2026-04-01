const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const htmlPath = path.join(__dirname, '..', '..', 'apps', 'web', 'claude-console.html');
const html = fs.readFileSync(htmlPath, 'utf8');

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
  assert.notEqual(bodyStart, -1, `missing body for ${name}`);
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

function evaluateFunctions(names, contextValues) {
  const sandbox = vm.createContext({ ...contextValues });
  for (const name of names) {
    const fnSource = extractFunctionSource(html, name);
    vm.runInContext(fnSource, sandbox, { filename: `${name}.js` });
  }
  return sandbox;
}

test('codex shell surface exposes selector hooks and structured shell payloads', () => {
  assert.match(html, /context-ring/, 'frontend should render a context ring surface');
  assert.match(html, /function renderContextUsageRing\(/, 'frontend should render context ring state');
  assert.match(html, /function openSlashChooser\(/, 'frontend should expose slash chooser opening');
  assert.match(html, /function renderComposerChips\(/, 'frontend should render structured composer chips');
  assert.match(html, /function toggleRunStepExpanded\(/, 'frontend should support run-step collapse and expand');
  assert.match(html, /document\.getElementById\('shell-model-pill'\)\.addEventListener\('click', \(\) => \{\s*cycleModelSelection\(1\);/);
  assert.match(html, /document\.getElementById\('shell-permission-pill'\)\.addEventListener\('click', \(\) => \{\s*cyclePermissionSelection\(1\);/);
  assert.match(html, /document\.getElementById\('shell-reasoning-pill'\)\.addEventListener\('click', \(\) => \{\s*cycleReasoningSelection\(1\);/);
  assert.match(html, /shellSelections/, 'frontend should submit structured shell selections');
  assert.match(html, /prompt,\s*\n\s*shellSelections,/, 'frontend should send raw prompt alongside shell selections');
  assert.doesNotMatch(html, /prompt:\s*preparedPrompt/, 'frontend should not rewrite the main prompt client-side');
  assert.match(html, /function buildCompletionSummaryData\(/, 'frontend should derive a completion summary');
  assert.match(html, /function renderCompletionSummary\(/, 'frontend should render a completion summary block');
  assert.match(html, /id="shell-model-pill-label"/, 'shell model label should be locale-driven');
  assert.match(html, /id="shell-reasoning-pill-label"/, 'shell reasoning label should be locale-driven');
  assert.match(html, /id="shell-permission-pill-label"/, 'shell permission label should be locale-driven');
  assert.match(html, /\['shell-model-pill-label', 'shell_model_label'\]/, 'applyLocale should map shell labels globally');
  assert.match(html, /\['btn-scroll-bottom', 'scroll_latest'\]/, 'applyLocale should map scroll button globally');
});

test('composer layout keeps primary controls in the bottom control row', () => {
  assert.match(html, /<div class="composer-bottom">[\s\S]*id="btn-attach-file"/, 'attach action should live in the bottom row');
  assert.match(html, /<div class="composer-bottom">[\s\S]*id="model-route"/, 'model selector should live in the bottom row');
  assert.match(html, /<div class="composer-bottom">[\s\S]*id="btn-send"/, 'send button should live in the bottom row');
});

test('top strip selectors synchronize actual model and permission state', () => {
  const modelSelect = { value: 'auto' };
  const permissionSelect = {
    value: 'auto',
    options: [
      { value: 'auto' },
      { value: 'default' },
      { value: 'plan' },
    ],
  };
  const context = evaluateFunctions(
    ['setModelMode', 'cycleModelSelection', 'permissionModeOptions', 'setPermissionMode', 'cyclePermissionSelection'],
    {
      appState: {
        mode: 'auto',
        permissionMode: 'auto',
        modelCatalog: [{ id: 'auto' }, { id: 'route-a' }, { id: 'route-b' }],
        availableModes: [{ id: 'auto' }, { id: 'route-a' }, { id: 'route-b' }],
        composerChips: [],
        chatShell: { permissionDefault: 'auto' },
      },
      document: {
        getElementById(id) {
          if (id === 'model-route') return modelSelect;
          if (id === 'permission-mode') return permissionSelect;
          return null;
        },
      },
      String,
      Array,
      Math,
    },
  );
  context.resolveModelCatalog = (modelCatalog) => modelCatalog;
  context.selectedModelCatalogItem = () => (
    context.appState.modelCatalog.find((item) => item.id === context.appState.mode) || context.appState.modelCatalog[0]
  );
  context.setComposerChips = (next) => {
    context.appState.composerChips = next;
  };
  context.upsertComposerChip = (sectionId, choice) => {
    context.appState.lastChip = { sectionId, choice };
  };
  context.updateTopBadges = () => {
    context.updated = (context.updated || 0) + 1;
  };
  context.refreshModelRouteStatus = () => ({ catch() {} });
  context.handleError = () => {};

  context.cycleModelSelection(1);
  assert.equal(context.appState.mode, 'route-a');
  assert.equal(modelSelect.value, 'route-a');
  assert.equal(context.appState.lastChip.sectionId, 'model');
  context.cyclePermissionSelection(1);
  assert.equal(context.appState.permissionMode, 'default');
  assert.equal(permissionSelect.value, 'default');
});

test('bootstrap default does not override a user-selected permission mode', () => {
  const permissionSelect = { value: 'auto' };
  const context = evaluateFunctions(
    ['setPermissionMode', 'maybeAdoptBootstrapPermissionMode'],
    {
      appState: {
        permissionMode: 'auto',
        permissionModeDirty: false,
        chatShell: { permissionDefault: 'auto' },
      },
      document: {
        getElementById(id) {
          if (id === 'permission-mode') return permissionSelect;
          return null;
        },
      },
      updateTopBadges() {},
      String,
    },
  );

  context.maybeAdoptBootstrapPermissionMode('default');
  assert.equal(context.appState.permissionMode, 'default');
  context.setPermissionMode('plan');
  context.maybeAdoptBootstrapPermissionMode('auto');
  assert.equal(context.appState.permissionMode, 'plan');
  assert.equal(permissionSelect.value, 'plan');
});

test('slash chip insertion preserves multiline whitespace outside the slash token', () => {
  const input = {
    value: 'first line\n\n    indented_block()\n/pla',
    focus() {},
    selectionStart: 0,
    selectionEnd: 0,
  };
  const context = evaluateFunctions(
    ['detectSlashIntent', 'selectSlashChoice'],
    {
      appState: {
        slashChooser: {
          sectionId: 'plan',
          replaceStart: 0,
          replaceEnd: 0,
        },
      },
      document: {
        getElementById(id) {
          if (id === 'composer-input') return input;
          return null;
        },
      },
      slashChoicesForSection() {
        return [{ id: 'plan-enable', label: 'Plan Mode' }];
      },
      upsertComposerChip() {},
      closeSlashChooser() {},
      Number,
      String,
    },
  );

  const intent = context.detectSlashIntent(input.value, input.value.length);
  assert.equal(intent.replaceStart, input.value.lastIndexOf('/'));
  context.appState.slashChooser = { ...context.appState.slashChooser, ...intent };
  context.selectSlashChoice('plan', 'plan-enable');
  assert.equal(input.value, 'first line\n\n    indented_block()\n');
});

test('tool snapshots merge into the active streaming tool block instead of duplicating it', () => {
  const input = {
    blocks: [{ type: 'tool_use', name: 'Shell', input: 'echo one' }],
  };
  const currentTool = input.blocks[0];
  const context = evaluateFunctions(
    ['upsertStreamingToolSnapshot'],
    {
      t() {
        return 'Tool';
      },
    },
  );

  const returnedTool = context.upsertStreamingToolSnapshot(
    input,
    { tool: { name: 'Shell', input: { command: 'echo two' } } },
    currentTool,
  );

  assert.equal(input.blocks.length, 1);
  assert.equal(returnedTool, currentTool);
  assert.deepEqual(input.blocks[0].input, { command: 'echo two' });
});

test('scroll helpers detach and reattach auto-stick around user scroll position', () => {
  const workspaceBody = { scrollHeight: 1000, scrollTop: 400, clientHeight: 300 };
  const buttonState = { visible: false };
  const scrollButton = {
    classList: {
      toggle(_name, visible) {
        buttonState.visible = Boolean(visible);
      },
    },
  };
  const context = evaluateFunctions(
    ['messageScrollContainer', 'isMessageNearBottom', 'updateScrollJumpButton', 'syncMessageScrollState', 'scrollMessagesToBottom', 'messageShouldStickToBottom'],
    {
      appState: {
        messageScrollDetached: false,
        isStreaming: true,
      },
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
    },
  );

  context.syncMessageScrollState();
  assert.equal(context.appState.messageScrollDetached, true);
  assert.equal(buttonState.visible, true);
  context.scrollMessagesToBottom({ force: true });
  assert.equal(workspaceBody.scrollTop, workspaceBody.scrollHeight);
  assert.equal(context.appState.messageScrollDetached, false);
});

test('completion summary data captures final reply and executed step count', () => {
  const context = evaluateFunctions(
    ['buildCompletionSummaryData'],
    {
      t(key, vars = {}) {
        if (key === 'completion_summary_default') return 'Completed a task';
        if (key === 'completion_summary_steps') return `${vars.count} steps`;
        return key;
      },
      String,
      Array,
      Math,
    },
  );

  const summary = context.buildCompletionSummaryData([
    { type: 'text', text: 'Fixed the layout issue.\nAlso refreshed the locale mapping.' },
    { type: 'tool_use', name: 'Shell', input: { command: 'git status' } },
    { type: 'tool_result', text: 'ok' },
  ]);

  assert.equal(summary.title, 'Fixed the layout issue.');
  assert.equal(summary.stepsLabel, '2 steps');
});
