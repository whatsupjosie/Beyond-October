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
const io = extract(page, 'const manuscriptFileSnapshots', 'async function saveStandaloneManuscript(');
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
    Blob, Event, TextEncoder, URL, setTimeout: () => {},
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
  function handle(name, {closing, fail, writing} = {}) {
    const file = {
      name,
      disk: '',
      async getFile() { return new Blob([this.disk]); },
      async createWritable(options) {
        assert.equal(options.mode, 'exclusive');
        let pending;
        return {
          async write(bytes) {
            pending = new TextDecoder().decode(bytes);
            if (writing) await writing.promise;
          },
          async close() {
            if (closing) await closing.promise;
            if (fail) throw Error('Disk write failed');
            file.disk = pending;
            writes.push([name, JSON.parse(pending).state.committed[0]]);
          },
          async abort() { context.aborted = true; }
        };
      }
    };
    runInContext('manuscriptFileSnapshots', context).set(file, new TextEncoder().encode(file.disk));
    return file;
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

test('an externally changed file is preserved and Save keeps the recovery dirty', async () => {
  const {context, writes, recoveries, indicator, handle} = fixture();
  const file = handle('changed.2i');
  file.disk = 'original';
  await context.readManuscriptFile(file);
  file.disk = 'external'; // same byte count as the original
  context.documentHandle = file;
  context.window.showSaveFilePicker = () => assert.fail('A conflict cannot send Save into a picker');
  assert.equal(await context.saveNow(), false);
  assert.equal(file.disk, 'external');
  assert.equal(context.aborted, true);
  assert.deepEqual(writes, []);
  assert.equal(recoveries.at(-1).dirty, true);
  assert.match(indicator.textContent, /File changed.*Save a copy/);
});

test('an external change made while bytes are staged aborts the pending write', async () => {
  const {context, writes, handle} = fixture();
  const writing = deferred();
  const file = handle('changed-during-write.2i', {writing});
  context.documentHandle = file;
  const save = context.saveNow();
  await new Promise(resolve => setImmediate(resolve));
  file.disk = 'external';
  writing.resolve();
  assert.equal(await save, false);
  assert.equal(file.disk, 'external');
  assert.deepEqual(writes, []);
  assert.equal(context.documentDirty, true);
});

test('offline manuscript shelf lists browser recovery without asking Reach', async () => {
  const shelfSource = extract(reach, 'async function showShelf()', '// Install visible actions');
  const clicks = [];
  const node = () => ({dataset:{}, children:[], append(...items) { this.children.push(...items); }, setAttribute() {}});
  const shelf = node();
  shelf.replaceChildren = () => { shelf.children = []; };
  const context = createContext({
    networked:false, $:() => shelf, document:{createElement:node},
    writeRecovery:() => clicks.push('write'),
    browserManuscripts:() => [{id:'draft', title:'My recovered draft', dirty:true, ts:0}],
    openModal:() => clicks.push('open'),
    api:() => assert.fail('Disk recovery does not use Reach'),
    saveDocument:() => assert.fail('Disk shelf must not await a server save')
  });
  await runInContext(shelfSource + '\nshowShelf()', context);
  assert.deepEqual(clicks, ['write', 'open']);
  assert.equal(shelf.children[0].children[0].textContent, 'My recovered draft');
  assert.equal(shelf.children[0].dataset.source, 'browser');
});

test('disk recovery records the document and writer on the current history entry', () => {
  const pin = extract(reach, 'function pinEditorDocument()', 'function rememberWorkspace()');
  const identity = extract(reach, 'const priorOfflineDocumentId=', 'let revision =');
  const history = {
    state:{other:7},
    replaceState(state, title, ...url) {
      assert.deepEqual(url, []);
      this.state = state;
    }
  };
  const context = createContext({
    history, location:{protocol:'file:'}, networked:false, reachFileMode:false,
    editorWriter:'prior-writer', documentId:'prior-manuscript'
  });
  runInContext(pin + '\npinEditorDocument()', context);
  assert.equal(history.state.other, 7);
  assert.equal(history.state.twoiWriter, 'prior-writer');
  assert.equal(history.state.twoiOfflineDocument, 'prior-manuscript');
  const reload = createContext({
    history, location:{protocol:'file:', search:''},
    URLSearchParams, WORKSPACE_KEY:'workspace', uuid:() => 'generated',
    stored:() => ({documentId:'other-tab'})
  });
  assert.equal(runInContext(identity + '\ndocumentId', reload), 'prior-manuscript');
});
