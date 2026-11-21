/**
 * Hosted 2i Save Now contracts.
 *
 * Tests the real saveDocument implementation extracted from Reach, with only
 * the HTTP transport, recovery store and status indicator replaced by fakes.
 * No server, local files, credentials or browser required.
 *
 * Run: node --test tests/test_2i_hosted_save_races_node.js
 */
'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../2i/2i-assets/reach.js'), 'utf8');
const begin = source.indexOf('async function saveDocument()');
const end = source.indexOf('async function saveToFile()', begin);
assert.ok(begin >= 0 && end > begin, 'Hosted Save Now implementation must be discoverable');
const saveSource = source.slice(begin, end);

function createFixture({holdFirst = false, failStatus = null} = {}) {
  const requests = [], recoveries = [], statuses = [];
  const waiting = [];
  const state = {
    // Reach's default saver gained a guard that returns early in Foresight file
    // mode (2i/2i-assets/reach.js, saveDocument). These seven cases all exercise
    // the hosted path, so the sandbox must define it as false; without it the
    // sliced function throws ReferenceError before any assertion runs.
    reachFileMode: false,
    initializing: false, savePromise: null, saveConflict: false,
    networked: true, serverReady: true, recoverySafe: true,
    documentDirty: true, documentHandle: null, fileSavingId: null,
    documentId: 'manuscript-a', content: 'First paragraph.',
    mutation: 1, savedMutation: 0, revision: 0,
    Event: class { constructor(type) { this.type = type; } },
    document: { dispatchEvent() {} },
    writeRecovery() {
      recoveries.push({id: state.documentId, dirty: state.documentDirty, text: state.content});
    },
    setSaveStatus(text) { statuses.push(text); },
    docPayload() { return {state: {committed: [state.content]}}; },
    async api(url, options) {
      const payload = JSON.parse(options.body);
      requests.push({url, method: options.method, payload});
      if (failStatus !== null) {
        const error = new Error('Host refused save');
        error.status = failStatus;
        throw error;
      }
      if (holdFirst && requests.length === 1)
        await new Promise(resolve => waiting.push(resolve));
      return {revision: state.revision + 1};
    }
  };
  vm.createContext(state);
  vm.runInContext(saveSource, state, {filename: 'reach-save-extract.js'});
  return {state, requests, recoveries, statuses, release: () => {
    assert.equal(waiting.length, 1, 'Expected one paused server write');
    waiting.shift()();
  }};
}

test('hosted Save Now persists the current manuscript and marks its revision clean', async () => {
  const f = createFixture();
  assert.equal(await f.state.saveDocument(), true);
  assert.equal(f.requests.length, 1);
  assert.equal(f.requests[0].method, 'PUT');
  assert.equal(f.requests[0].url, '/api/writers-room/documents/manuscript-a');
  assert.deepEqual(f.requests[0].payload.state.committed, ['First paragraph.']);
  assert.equal(f.state.revision, 1);
  assert.equal(f.state.documentDirty, false);
  assert.match(f.statuses.at(-1), /Saved to Reach/);
});

test('late edits are included in a second server revision before reporting Saved', async () => {
  const f = createFixture({holdFirst: true});
  const saving = f.state.saveDocument();
  f.state.content = 'New paragraph added during network save.';
  f.state.mutation += 1;
  f.release();
  assert.equal(await saving, true);
  assert.equal(f.requests.length, 2);
  assert.deepEqual(f.requests[0].payload.state.committed, ['First paragraph.']);
  assert.deepEqual(f.requests[1].payload.state.committed, ['New paragraph added during network save.']);
  assert.equal(f.requests[1].payload.expected_revision, 1);
  assert.equal(f.state.revision, 2);
  assert.equal(f.state.documentDirty, false);
});

test('two Save Now clicks share an in-flight hosted save instead of racing', async () => {
  const f = createFixture({holdFirst: true});
  const first = f.state.saveDocument();
  const second = f.state.saveDocument();
  f.release();
  assert.equal(await first, true);
  assert.equal(await second, true);
  assert.equal(f.requests.length, 1);
});

test('HTTP conflict never claims a successful save', async () => {
  const f = createFixture({failStatus: 409});
  assert.equal(await f.state.saveDocument(), false);
  assert.equal(f.state.saveConflict, true);
  assert.equal(f.state.documentDirty, true);
  assert.match(f.statuses.at(-1), /Changed elsewhere/);
  assert.equal(f.recoveries[0].dirty, true);
});

test('host error preserves unsaved state and recovery instead of inventing success', async () => {
  const f = createFixture({failStatus: 503});
  assert.equal(await f.state.saveDocument(), false);
  assert.equal(f.state.documentDirty, true);
  assert.equal(f.state.revision, 0);
  assert.match(f.statuses.at(-1), /Saved in browser/);
  assert.doesNotMatch(f.statuses.at(-1), /Saved to Reach/);
  assert.equal(f.recoveries.at(-1).dirty, true);
});

test('offline autosave records browser recovery but never claims a server write', async () => {
  const f = createFixture();
  f.state.networked = false;
  assert.equal(await f.state.saveDocument(), false);
  assert.equal(f.requests.length, 0);
  assert.equal(f.state.documentDirty, true);
  assert.match(f.statuses.at(-1), /Kept in this browser/);
  assert.equal(f.recoveries.at(-1).text, 'First paragraph.');
});

test('late hosted response must not mark a newly selected manuscript saved', async () => {
  const f = createFixture({holdFirst: true});
  const oldSave = f.state.saveDocument();
  f.state.documentId = 'manuscript-b';
  f.state.content = 'Second manuscript';
  f.state.mutation += 1;
  f.release();
  assert.equal(await oldSave, false);
  assert.equal(f.requests.length, 1);
  assert.equal(f.requests[0].url, '/api/writers-room/documents/manuscript-a');
  assert.equal(f.state.documentId, 'manuscript-b');
  assert.equal(f.state.documentDirty, true);
  assert.equal(f.state.revision, 0);
});
