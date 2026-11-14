const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const source = readFileSync(require.resolve('../static/speech_client.js'), 'utf8');

function speechHarness() {
  const window = new EventTarget();
  const events = [];
  const revoked = [];
  const handles = [];
  let controller;
  window.PubcastProgramAudio = {
    allowed: () => true,
    ensureContext() {},
    context: {resume: async () => {}},
    externalStops: new Set(),
    async playUrl(_url, {signal}) {
      const audio = new EventTarget();
      audio.ended = false;
      const handle = {audio, stop() { handle.onStop?.(); }};
      signal.addEventListener('abort', handle.stop, {once: true});
      handles.push(handle);
      return handle;
    }
  };
  for (const name of ['start', 'end']) {
    window.addEventListener('pubcast:speech-' + name, event => events.push([name, event.detail]));
  }
  vm.runInNewContext(source, {
    window, performance, Headers, CustomEvent,
    AbortController: class extends AbortController {
      constructor() { super(); controller = this; }
    },
    fetch: async () => ({
      ok: true, headers: new Headers({'Content-Type': 'audio/wav'}),
      blob: async () => new Blob(),
    }),
    URL: {createObjectURL: () => 'blob:test', revokeObjectURL: url => revoked.push(url)},
  });
  return {window, speech: window.PubcastSpeech, events, handles, revoked,
    get signal() { return controller.signal; }};
}

function nextStart(harness) {
  return new Promise(resolve => harness.window.addEventListener('pubcast:speech-start', resolve, {once: true}));
}

for (const outcome of ['ended', 'canceled', 'error']) {
  test('pairs speech start and end exactly once after ' + outcome, async () => {
    const h = speechHarness();
    const started = nextStart(h);
    const work = h.speech.speak('A line.', {character_id: 'pete'});
    await started;
    const signal = h.signal;
    const [handle] = h.handles;
    if (outcome === 'error') {
      handle.audio.dispatchEvent(new Event('error'));
      await assert.rejects(work, /Speech playback failed/);
    } else {
      if (outcome === 'ended') {
        handle.audio.ended = true;
        handle.stop();
      } else h.speech.stop();
      assert.equal((await work).canceled, outcome === 'canceled');
    }
    assert.deepEqual(h.events.map(([name, detail]) => [name, detail.characterId]),
      [['start', 'pete'], ['end', 'pete']]);
    assert.equal(h.events[1][1].ended, outcome === 'ended');
    assert.deepEqual(h.revoked, ['blob:test']);
    h.speech.stop();
    assert.equal(signal.aborted, outcome === 'canceled');
  });
}
