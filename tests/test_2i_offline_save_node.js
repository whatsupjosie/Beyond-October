const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {test} = require('node:test');
const {createContext, runInContext} = require('node:vm');

const page = readFileSync(join(__dirname, '../2i/writers-room-v22.html'), 'utf8');
const reach = readFileSync(join(__dirname, '../2i/2i-assets/reach.js'), 'utf8');
const extract = (source, start, end) => {
  const first = source.indexOf(start);
  const last = source.indexOf(end, first);
  assert.ok(first >= 0 && last > first);
  return source.slice(first, last);
};
const io = extract(page, 'async function writeManuscriptFile(', 'async function saveStandaloneManuscript(');
const standalone = extract(page, 'async function saveStandaloneManuscript(', 'async function openDocument(');
const offline = extract(reach, 'function showUnsavedFileStatus(', 'async function preserveBeforeSwitch(');

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
}

function fixture() {
  const writes = [], recoveries = [], notices = [], downloads = [];
  const indicator = {textContent:''};
  const context = createContext({
    Blob, Event, URL, setTimeout: () => {},
    document: {
      dispatchEvent() {},
      createElement: () => ({click() { downloads.push(this.download); }})
    },
    window: {}, initializing: false, networked: false, recoverySafe: true,
    documentId: 'first', mutation: 1, documentDirty: true, documentHandle: null,
    standaloneDocumentId: 1, standaloneSaveInProgress: false, fileSavingId: null,
    content: 'First line',
    safeName: () => 'Story',
    docPayload: () => ({state:{committed:[context.content]}}),
    writeRecovery: () => recoveries.push({id:context.documentId, dirty:context.documentDirty, text:context.content}),
    setSaveStatus: text => { indicator.textContent = text; },
    addChat: (_, text) => notices.push(text),
    $: () => indicator
  });
  runInContext(io + standalone + offline, context);
  function handle(name, {closing, fail} = {}) {
    return {
      name,
      async createWritable() {
        let pending;
        return {
          async write(bytes) { pending = JSON.parse(bytes).state.committed[0]; },
          async close() {
            if (closing) await closing.promise;
            if (fail) throw Error('Disk write failed');
            writes.push([name, pending]);
          },
          async abort() { context.aborted = true; }
        };
      }
    };
  }
  return {context, writes, recoveries, notices, downloads, indicator, handle};
}

test('disk Save reports edits made during a write as unsaved and the next Save writes them', async () => {
  const {context, writes, recoveries, indicator, handle} = fixture();
  const closing = deferred();
  context.documentHandle = handle('old.2i', {closing});
  const first = context.saveNow();
  context.content = 'Second line';
  context.mutation++;
  // Repeated clicks cannot start a competing write to the same file.
  assert.equal(await context.saveNow(), false);
  closing.resolve();
  assert.equal(await first, false);
  assert.deepEqual(writes, [['old.2i', 'First line']]);
  assert.equal(context.documentDirty, true);
  assert.deepEqual(recoveries.at(-1), {id:'first', dirty:true, text:'Second line'});
  assert.match(indicator.textContent, /Save to update old\.2i/);
  assert.equal(await context.saveNow(), true);
  assert.deepEqual(writes.at(-1), ['old.2i', 'Second line']);
  assert.equal(context.documentDirty, false);
});

test('a completed disk write cannot change the state of the next manuscript', async () => {
  const {context, writes, recoveries, indicator, handle} = fixture();
  const closing = deferred();
  context.documentHandle = handle('old.2i', {closing});
  const oldSave = context.saveNow();
  const newHandle = handle('new.2i');
  context.documentId = 'second';
  context.content = 'New manuscript';
  context.documentHandle = newHandle;
  context.mutation++;
  context.setSaveStatus('New manuscript status');
  closing.resolve();
  assert.equal(await oldSave, false);
  assert.equal(context.documentHandle, newHandle);
  assert.equal(context.documentDirty, true);
  assert.equal(indicator.textContent, 'New manuscript status');
  assert.deepEqual(recoveries, [{id:'first', dirty:true, text:'First line'}]);
  assert.deepEqual(writes, [['old.2i', 'First line']]);
  assert.equal(await context.saveNow(), true);
  assert.deepEqual(writes.at(-1), ['new.2i', 'New manuscript']);
});

test('a picker that returns after a manuscript switch does not write to the selected file', async () => {
  const {context, writes, handle} = fixture();
  const picker = deferred();
  context.window.showSaveFilePicker = () => picker.promise;
  const save = context.saveNow();
  context.documentId = 'second';
  picker.resolve(handle('old.2i'));
  assert.equal(await save, false);
  assert.deepEqual(writes, []);
  assert.equal(context.documentHandle, null);
  assert.equal(context.documentDirty, true);
});

test('cancelling a picker leaves the manuscript dirty and does not download a copy', async () => {
  const {context, downloads, indicator} = fixture();
  context.window.showSaveFilePicker = async () => { throw Object.assign(Error('Cancelled'), {name:'AbortError'}); };
  assert.equal(await context.saveNow(), false);
  assert.deepEqual(downloads, []);
  assert.equal(context.documentDirty, true);
  assert.match(indicator.textContent, /Not saved to a file/);
});

test('a disk failure leaves recovery dirty and allows a retry', async () => {
  const {context, writes, recoveries, notices, indicator, handle} = fixture();
  context.window.showSaveFilePicker = async () => handle('failed.2i', {fail:true});
  assert.equal(await context.saveNow(), false);
  assert.equal(context.aborted, true);
  assert.deepEqual(writes, []);
  assert.equal(recoveries.at(-1).dirty, true);
  assert.match(indicator.textContent, /File save failed/);
  assert.deepEqual(notices, ['Disk write failed']);
  context.window.showSaveFilePicker = async () => handle('retry.2i');
  assert.equal(await context.saveNow(), true);
  assert.deepEqual(writes, [['retry.2i', 'First line']]);
});

test('without a picker, explicit disk Save downloads the captured manuscript', async () => {
  const {context, downloads, indicator} = fixture();
  assert.equal(await context.saveNow(), true);
  assert.deepEqual(downloads, ['Story.2i']);
  assert.equal(indicator.textContent, 'Copy downloaded · Story.2i');
});

test('the bare HTML editor also leaves a late edit unsaved', async () => {
  const {context, writes, indicator, handle} = fixture();
  const closing = deferred();
  context.documentHandle = handle('standalone.2i', {closing});
  const save = context.saveStandaloneManuscript(context.documentHandle);
  context.content = 'Second line';
  closing.resolve();
  assert.equal(await save, false);
  assert.deepEqual(writes, [['standalone.2i', 'First line']]);
  assert.equal(context.documentDirty, true);
  assert.equal(indicator.textContent, 'unsaved');
});
