// static/keymap.js: the key assignment map, tested without a browser.
const assert = require('assert');
const test = require('node:test');
const KM = require('../static/keymap.js');

const spec = () => ({
  switcher: {
    cut: { label: 'Cut', key: 'Space' }, fade_out: { label: 'Fade out', key: 'KeyF' }, fade_in: { label: 'Fade in', key: 'KeyG' },
    program: { label: 'Program level', kind: 'fader', key: 'KeyP', min: 0, max: 10, step: 2, value: 4 },
  },
  audio: { mute: { label: 'Mute', key: 'Space' }, volume: { label: 'Volume', kind: 'fader', key: 'KeyV', min: 0, max: 100, step: 1, value: 50 } },
});
const rig = () => { const km = KM.create(spec()); const calls = []; km.onButton((s, a) => calls.push(`${s}.${a}`)); km.onFader((s, a, v) => calls.push(`${s}.${a}=${v}`)); return { km, calls }; };

test('defaults act only at the open station, and the same key can mean different things at different stations', () => {
  const { km, calls } = rig();
  assert.deepStrictEqual(km.press('switcher', 'Space'), { handled: true, action: 'cut' });
  assert.deepStrictEqual(km.press('audio', 'Space'), { handled: true, action: 'mute' });
  assert.deepStrictEqual(calls, ['switcher.cut', 'audio.mute']);
  assert.strictEqual(km.press('switcher', 'KeyZ').handled, false);
  assert.strictEqual(km.press('nowhere', 'Space').handled, false);
});

test('assign refuses reserved, modifier and invalid keys, and reports a conflict instead of taking the key', () => {
  const { km } = rig();
  for (const [code, why] of [['Escape', 'reserved'], ['F5', 'reserved'], ['F12', 'reserved'], ['Tab', 'reserved'], ['ArrowUp', 'reserved'], ['ArrowDown', 'reserved'],
                             ['ShiftLeft', 'modifier'], ['ControlRight', 'modifier'], ['MetaLeft', 'modifier'], ['', 'invalid'], [null, 'invalid'], ['Key A', 'invalid'], [5, 'invalid']])
    assert.deepStrictEqual(km.assign('switcher', 'cut', code), { ok: false, reason: why }, String(code));
  assert.deepStrictEqual(km.assign('switcher', 'cut', 'KeyF'), { ok: false, reason: 'conflict', with: 'fade_out' });
  assert.strictEqual(km.bindings('switcher').cut, 'Space');
  assert.deepStrictEqual(km.assign('switcher', 'cut', 'KeyF', { replace: true }), { ok: true, displaced: 'fade_out' });
  assert.strictEqual(km.bindings('switcher').fade_out, null);
  assert.deepStrictEqual(km.assign('switcher', 'nope', 'KeyQ'), { ok: false, reason: 'unknown' });
  assert.deepStrictEqual(km.assign('switcher', 'cut', 'Space'), { ok: true });          // its own key again is fine
});

test('asking where a button goes: the next key answers, Esc cancels, a taken key needs the same key twice', () => {
  const { km } = rig();
  assert.strictEqual(km.ask('switcher', 'cut'), 'Where would you like the Cut button?');
  assert.strictEqual(km.ask('switcher', 'program'), 'Where would you like the Program level fader?');
  assert.strictEqual(km.ask('switcher', 'bogus'), null);
  km.ask('switcher', 'cut');
  let r = km.press('switcher', 'Escape');
  assert.deepStrictEqual(r, { handled: true, learn: { ok: false, reason: 'cancelled' } }); assert.strictEqual(km.pending(), null);
  km.ask('switcher', 'cut');
  r = km.press('switcher', 'KeyQ');
  assert.deepStrictEqual(r, { handled: true, learn: { action: 'cut', code: 'KeyQ', ok: true } });
  assert.strictEqual(km.bindings('switcher').cut, 'KeyQ'); assert.strictEqual(km.pending(), null);
  km.ask('switcher', 'cut');
  r = km.press('switcher', 'KeyF');
  assert.deepStrictEqual(r.learn, { ok: false, reason: 'conflict', with: 'fade_out' });
  assert.strictEqual(km.pending().confirming, 'KeyF'); assert.strictEqual(km.bindings('switcher').cut, 'KeyQ');
  r = km.press('switcher', 'KeyF');                                                      // again: take it over
  assert.strictEqual(r.learn.ok, true); assert.strictEqual(r.learn.displaced, 'fade_out');
  assert.strictEqual(km.bindings('switcher').cut, 'KeyF'); assert.strictEqual(km.bindings('switcher').fade_out, null);
  km.ask('switcher', 'cut'); assert.strictEqual(km.press('switcher', 'ArrowUp').learn.reason, 'reserved');   // a refused key keeps the question open
  assert.notStrictEqual(km.pending(), null);
});

test('a fader: its key selects it, Up and Down step it within its range, Esc lets go, then Esc leaves the station', () => {
  const { km, calls } = rig();
  assert.strictEqual(km.press('switcher', 'ArrowUp').handled, false);                    // nothing selected: arrows are not ours
  assert.deepStrictEqual(km.press('switcher', 'KeyP'), { handled: true, action: 'program', selected: true });
  assert.deepStrictEqual(km.selected(), { station: 'switcher', action: 'program' });
  assert.strictEqual(km.press('switcher', 'ArrowUp').value, 6);
  assert.strictEqual(km.press('switcher', 'ArrowUp').value, 8);
  assert.strictEqual(km.press('switcher', 'ArrowUp').value, 10);
  assert.strictEqual(km.press('switcher', 'ArrowUp').value, 10);                         // clamped at the top
  for (let i = 0; i < 9; i++) km.press('switcher', 'ArrowDown');
  assert.strictEqual(km.value('switcher', 'program'), 0);                                // clamped at the bottom
  assert.ok(calls.includes('switcher.program=6'));
  assert.deepStrictEqual(km.press('switcher', 'Escape'), { handled: true, deselected: true });
  assert.strictEqual(km.selected(), null);
  assert.strictEqual(km.press('switcher', 'Escape').handled, false);                     // second Esc: the station closes
  km.press('switcher', 'KeyP'); km.press('switcher', 'KeyF');                            // another control's key does not move the fader
  assert.strictEqual(km.value('switcher', 'program'), 0);
  assert.strictEqual(km.setValue('switcher', 'program', NaN), null);
  assert.strictEqual(km.setValue('switcher', 'cut', 3), null);
});

test('save and load: cleared defaults stay cleared; bad, doubled, reserved and unknown entries are dropped', () => {
  const a = rig().km;
  a.assign('switcher', 'cut', 'KeyQ'); a.clear('switcher', 'fade_in');
  const saved = JSON.parse(JSON.stringify(a.toJSON()));
  assert.strictEqual(saved.switcher.fade_in, null);
  const b = rig().km; assert.deepStrictEqual(b.load(saved), { dropped: [] });
  assert.deepStrictEqual(b.bindings('switcher'), a.bindings('switcher'));
  const c = rig().km;
  const r = c.load({ switcher: { cut: 'Escape', fade_out: 'KeyQ', fade_in: 'KeyQ', program: 'KeyG' }, audio: { mute: 'ShiftLeft', volume: 5 }, ghost: {}, bad: 7 });
  assert.ok(r.dropped.some(d => d.includes('switcher.cut: Escape')));
  assert.ok(r.dropped.some(d => d.includes('switcher.fade_in: KeyQ (doubled)')));
  assert.ok(r.dropped.some(d => d.includes('ghost: unknown station')));
  assert.strictEqual(c.bindings('switcher').cut, 'Space');                               // dropped: default stays
  assert.strictEqual(c.bindings('switcher').fade_out, 'KeyQ');
  const seen = new Set(Object.values(c.bindings('switcher')).filter(Boolean));
  assert.strictEqual(seen.size, Object.values(c.bindings('switcher')).filter(Boolean).length);   // never two actions on one key
  assert.deepStrictEqual(c.load('nope'), { dropped: ['not an object'] });
});

test('a spec with a bad default or a doubled default is refused at creation', () => {
  assert.throws(() => KM.create({ s: { a: { key: 'Escape' } } }), /reserved/);
  assert.throws(() => KM.create({ s: { a: { key: 'KeyA' }, b: { key: 'KeyA' } } }), /twice/);
  assert.throws(() => KM.create({ 'Bad Id': {} }), /bad station id/);
});

function fakeDoc() {
  const fns = {}, wins = {};
  const doc = { addEventListener: (ty, f, cap) => { assert.strictEqual(cap, true); fns[ty] = f; }, defaultView: { addEventListener: (ty, f) => { wins[ty] = f; } } };
  const mk = e => Object.assign({ code: 'Space', target: { tagName: 'BODY' }, prevented: false, stopped: false,
    preventDefault() { this.prevented = true; }, stopImmediatePropagation() { this.stopped = true; } }, e);
  const press = e => { const ev = mk(e); fns.keydown(ev); return ev; };
  const release = e => { const ev = mk(e); fns.keyup(ev); return ev; };
  const blur = () => wins.blur();
  return { doc, press, release, blur };
}

test('the keyboard listener acts only while a station is open, stops other handlers when it uses a key, and leaves typing and shortcuts alone', () => {
  const { km, calls } = rig(); const { doc, press } = fakeDoc(); km.attach(doc);
  let ev = press({}); assert.strictEqual(ev.prevented, false); assert.deepStrictEqual(calls, []);       // no station open: the walker keeps its keys
  assert.strictEqual(km.isOpen(), false);
  km.open('switcher'); assert.strictEqual(km.isOpen(), true);
  ev = press({}); assert.ok(ev.prevented && ev.stopped); assert.deepStrictEqual(calls, ['switcher.cut']);
  ev = press({ code: 'KeyZ' }); assert.ok(!ev.prevented && !ev.stopped);
  for (const mod of ['ctrlKey', 'altKey', 'metaKey']) { ev = press({ [mod]: true }); assert.ok(!ev.prevented, mod); }
  for (const tagName of ['INPUT', 'TEXTAREA', 'SELECT']) { ev = press({ target: { tagName } }); assert.ok(!ev.prevented, tagName); }
  assert.strictEqual(calls.length, 1);
  ev = press({ code: 'Escape' }); assert.ok(!ev.prevented);                                             // Esc is for leaving: not swallowed
  km.close(); assert.strictEqual(km.activeStation(), null);
  ev = press({}); assert.ok(!ev.prevented); assert.strictEqual(calls.length, 1);
  assert.strictEqual(km.open('nowhere'), false);
});

test('the module answers "is any station open?" across keymaps, which is what the walker asks', () => {
  const a = KM.create({ one: { x: { label: 'X', key: 'KeyX' } } }), b = KM.create({ two: { y: { label: 'Y', key: 'KeyY' } } });
  assert.strictEqual(KM.isOpen(), false); assert.strictEqual(KM.activeStation(), null);
  b.open('two'); assert.strictEqual(KM.isOpen(), true); assert.strictEqual(KM.activeStation(), 'two');
  b.close(); a.open('one'); assert.strictEqual(KM.activeStation(), 'one');
  a.close(); assert.strictEqual(KM.isOpen(), false);
});


test('the arrows are kept for faders only at stations that have one, so the camera can use them for tilt and pan', () => {
  const km = KM.create({ cam: { tilt_up: { label: 'Tilt up', kind: 'hold', key: 'ArrowUp' }, tilt_down: { label: 'Tilt down', kind: 'hold', key: 'ArrowDown' } },
                         mix: { vol: { label: 'Volume', kind: 'fader', key: 'KeyV' } } });
  assert.strictEqual(km.bindings('cam').tilt_up, 'ArrowUp');
  assert.deepStrictEqual(km.assign('cam', 'tilt_up', 'ArrowLeft'), { ok: true });
  assert.deepStrictEqual(km.assign('mix', 'vol', 'ArrowUp'), { ok: false, reason: 'reserved' });
  assert.throws(() => KM.create({ mix: { a: { kind: 'fader', key: 'KeyA' }, b: { key: 'ArrowDown' } } }), /reserved/);
});

test('a held control acts for as long as its key is down: repeat does not press it again, any number at once, release on key up, blur, close and reassignment', () => {
  const km = KM.create({ cam: { pan_left: { label: 'Pan left', kind: 'hold', key: 'ArrowLeft' }, pan_right: { label: 'Pan right', kind: 'hold', key: 'ArrowRight' },
                                zoom_in: { label: 'Zoom in', kind: 'hold', key: 'BracketRight' } }, sw: { cut: { label: 'Cut', key: 'Space' } } });
  const log = []; km.onHold((s, a, d) => log.push(`${a}:${d ? 'down' : 'up'}`));
  const { doc, press, release, blur } = fakeDoc(); km.attach(doc);
  km.open('cam');
  press({ code: 'ArrowLeft' }); press({ code: 'ArrowLeft' }); press({ code: 'BracketRight' });          // a repeat, then a second control at once
  assert.deepStrictEqual(log, ['pan_left:down', 'zoom_in:down']); assert.deepStrictEqual(km.held('cam').sort(), ['pan_left', 'zoom_in']);
  release({ code: 'ArrowLeft' }); assert.deepStrictEqual(km.held('cam'), ['zoom_in']); assert.strictEqual(log.at(-1), 'pan_left:up');
  blur(); assert.deepStrictEqual(km.held('cam'), []); assert.strictEqual(log.at(-1), 'zoom_in:up');         // losing focus never leaves a key stuck down
  press({ code: 'ArrowRight' }); km.close(); assert.deepStrictEqual(km.held('cam'), []); assert.strictEqual(log.at(-1), 'pan_right:up');
  km.open('cam'); press({ code: 'ArrowRight' }); km.open('sw'); assert.strictEqual(log.at(-1), 'pan_right:up');   // moving to another station lets go too
  km.open('cam'); press({ code: 'BracketRight' }); km.assign('cam', 'zoom_in', 'KeyZ'); release({ code: 'BracketRight' });
  assert.deepStrictEqual(km.held('cam'), [], 'a key reassigned while held is still released when its old key comes up');
  assert.strictEqual(km.ask('cam', 'pan_left'), 'Where would you like the Pan left button?');
  assert.strictEqual(km.press('cam', 'KeyJ').learn.ok, true); assert.strictEqual(km.bindings('cam').pan_left, 'KeyJ');
});
