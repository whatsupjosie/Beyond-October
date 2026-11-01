// Keyboard camera shortcuts (static/switcher.js) against the real /api/cameras shape.
// Regression: the route returns {cameras:[...], program, preview}; switcher.js treated
// that object as the list, so 1-9 found no camera and sent nothing.
const assert = require('assert');
const test = require('node:test');
const path = require('path');

function harness(apiResponse) {
  const listeners = {};
  const calls = [];
  global.document = {
    activeElement: { tagName: 'BODY' },
    addEventListener: (type, fn) => { (listeners[type] = listeners[type] || []).push(fn); },
    getElementById: () => null,
  };
  global.window = {};
  global.fetch = async (url, options = {}) => {
    calls.push(`${options.method || 'GET'} ${url}`);
    return { json: async () => apiResponse };
  };
  delete require.cache[require.resolve('../static/switcher.js')];
  require(path.join('..', 'static', 'switcher.js'));
  const fire = async (type, event = {}) => {
    for (const fn of listeners[type] || []) await fn({ preventDefault() {}, shiftKey: false, ...event });
    await new Promise((r) => setImmediate(r));
  };
  return { calls, fire };
}

const CAMERAS = {
  cameras: [{ source_id: 'wide_shot', name: 'Wide' }, { source_id: 'medium_shot', name: 'Medium' }],
  program: 'wide_shot', preview: 'medium_shot',
};

test('number keys pick preview, shift+number takes program, space cuts', async () => {
  const { calls, fire } = harness(CAMERAS);
  await fire('DOMContentLoaded');
  await fire('keydown', { key: '2' });
  await fire('keydown', { key: '1', shiftKey: true });
  await fire('keydown', { key: ' ' });
  assert.deepStrictEqual(calls, [
    'GET /api/cameras',
    'POST /api/cameras/preview/medium_shot',
    'POST /api/cameras/program/wide_shot',
    'POST /api/cameras/cut',
  ]);
});

test('a plain array response still works', async () => {
  const { calls, fire } = harness(CAMERAS.cameras);
  await fire('DOMContentLoaded');
  await fire('keydown', { key: '1' });
  assert.ok(calls.includes('POST /api/cameras/preview/wide_shot'), calls.join(', '));
});

test('a key with no camera sends nothing, and typing in a field is ignored', async () => {
  const { calls, fire } = harness(CAMERAS);
  await fire('DOMContentLoaded');
  await fire('keydown', { key: '9' });
  global.document.activeElement = { tagName: 'INPUT' };
  await fire('keydown', { key: '1' });
  assert.deepStrictEqual(calls, ['GET /api/cameras']);
});
