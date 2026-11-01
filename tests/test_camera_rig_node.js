// static/camera_rig.js: one pose, several ways to drive it, one recorder.
const assert = require('assert');
const test = require('node:test');
const R = require('../static/camera_rig.js');
const near = (a, b, e = 1e-6) => assert.ok(Math.abs(a - b) <= e, `${a} vs ${b}`);
const run = (rig, seconds, want, dt = 1 / 60) => { for (let t = 0; t < seconds - 1e-9; t += dt) rig.step(dt, typeof want === 'function' ? want(rig) : want); };

test('held keys move, aim and zoom at once, and a held pair settles to a steady speed without jerking', () => {
  const rig = R.create({ x: 0, z: 0, pan: 0 });
  const held = new Set(['KeyW', 'KeyD', 'ArrowRight', 'BracketRight', 'KeyE']);
  run(rig, 2, () => R.fromKeys(rig.pose, held));
  assert.ok(Math.hypot(rig.pose.x, rig.pose.z) > 3 && rig.pose.pan > 0 && rig.pose.fov < 50 * R.DEG && rig.pose.y > 1.6);   // move, aim, zoom and rise all happened together
  const steady = R.create(), push = new Set(['KeyW']);
  run(steady, 2, () => R.fromKeys(steady.pose, push)); const v1 = steady.velocity().z; run(steady, 0.2, () => R.fromKeys(steady.pose, push));
  near(v1, R.SPEED.move, 0.05); near(steady.velocity().z, v1, 0.01);                                  // a held key settles to its speed and stays there
  held.clear(); run(rig, 3, () => R.fromKeys(rig.pose, held));
  assert.ok(Math.hypot(...R.CH.map(c => rig.velocity()[c])) < 1e-3);   // letting go comes to rest
});

test('opposite keys cancel, unknown keys do nothing, and moving is relative to where the camera points', () => {
  assert.deepStrictEqual(R.fromKeys(R.newPose(), ['KeyW', 'KeyS']), { x: 0, y: 0, z: 0 });
  assert.deepStrictEqual(R.fromKeys(R.newPose(), ['KeyZ']), {});
  const w = R.fromKeys(R.newPose({ pan: Math.PI / 2 }), ['KeyW']);                                    // facing +x: forward is +x
  near(w.x, R.SPEED.move); near(w.z, 0, 1e-9);
});

test('pan turns all the way round and replays the short way across the wrap', () => {
  const rig = R.create({ pan: 350 * R.DEG });
  run(rig, 1, { pan: 40 * R.DEG });
  assert.ok(rig.pose.pan >= 0 && rig.pose.pan < 2 * Math.PI);
  assert.ok(Math.abs(R.turn(350 * R.DEG, 10 * R.DEG) - 20 * R.DEG) < 1e-9);
  const rec = { rate: 30, channels: R.CH, samples: [[0, 1.6, 0, 359 * R.DEG, 0, 0, 0.8, 5], [0, 1.6, 0, 1 * R.DEG, 0, 0, 0.8, 5]] };
  const mid = R.playback(rec, 0.5 / 30).pan;
  assert.ok(mid < 0.001 || mid > 2 * Math.PI - 0.001, 'half way between 359 and 1 degrees is 0, not 180');
});

test('limits stop a move without storing up speed: tilt, zoom and focus stay in range and recover at once', () => {
  const rig = R.create();
  run(rig, 5, { tilt: 90 * R.DEG, roll: 90 * R.DEG, fov: -90 * R.DEG, focus: -50 });
  assert.ok(rig.pose.roll <= 90 * R.DEG + 1e-9 && rig.pose.tilt <= 85 * R.DEG + 1e-9 && rig.pose.fov >= 10 * R.DEG - 1e-9 && rig.pose.focus >= 0.3 - 1e-9);
  run(rig, 0.3, { tilt: -45 * R.DEG });
  assert.ok(rig.pose.tilt < 85 * R.DEG - 0.05);
  for (const bad of [NaN, Infinity, undefined, 'x', null]) run(rig, 0.1, { pan: bad, x: bad });         // junk input is ignored, never poisons the pose
  assert.ok(R.CH.every(c => Number.isFinite(rig.pose[c])));
});

test('projection puts a subject where the geometry says, and behind the camera is not in frame', () => {
  const p = R.newPose({ x: 0, y: 1.6, z: 0, pan: 0, tilt: 0, fov: 60 * R.DEG });
  let q = R.project(p, [0, 1.6, 10]); near(q.sx, 0); near(q.sy, 0); near(q.dist, 10); assert.ok(q.ok);
  q = R.project(p, [10 * Math.tan(30 * R.DEG) * 16 / 9, 1.6, 10]); near(q.sx, 1, 1e-9);                  // the right-hand edge of a 60 degree lens
  q = R.project(p, [0, 1.6, -5]); assert.strictEqual(q.ok, false);
  const a = R.aimAt(p, [5, 1.6, 5]); near(a.pan, Math.PI / 4); near(a.tilt, 0);
  const aimed = Object.assign({}, p, a); q = R.project(aimed, [5, 1.6, 5]); near(q.sx, 0, 1e-9);
});

test('lock-on keeps a moving subject framed and in focus while the operator only moves and zooms', () => {
  const rig = R.create({ x: -4, z: -8, pan: 0, focus: 5 });
  let worst = 0, focusWorst = 0;
  for (let t = 0; t < 12; t += 1 / 60) {
    const subject = [1.2 * t - 6, 1.7, 3];
    rig.step(1 / 60, R.fromLock(rig.pose, t < 2 ? new Set(['KeyW']) : new Set(), subject));      // a push in for two seconds, then it holds
    if (t > 2) { const q = R.project(rig.pose, subject); worst = Math.max(worst, Math.hypot(q.sx, q.sy)); focusWorst = Math.max(focusWorst, Math.abs(rig.pose.focus - q.dist) / q.dist); }
  }
  assert.ok(worst < 0.35, 'framing error ' + worst);
  assert.ok(focusWorst < 0.15, 'focus error ' + focusWorst);
});

test('a scripted shot (what an AI operator writes) eases between keyframes and ends exactly on the last', () => {
  const keys = [{ t: 0, pose: R.newPose({ x: 0, z: 0 }) }, { t: 4, pose: R.newPose({ x: 8, z: 4, pan: 90 * R.DEG }) }];
  near(R.shotPose(keys, 0).x, 0); near(R.shotPose(keys, 4).x, 8); near(R.shotPose(keys, 99).z, 4);
  near(R.shotPose(keys, 2).x, 4);                                                                       // symmetric ease: half way at half time
  assert.ok(R.shotPose(keys, 1).x < 2 && R.shotPose(keys, 3).x > 6);                                    // slow in, slow out
  assert.strictEqual(R.shotPose([], 1), null);
});

test('a recorded move replays exactly: same samples, same pose, and the pose that results is what is stored', () => {
  const rig = R.create({ x: 1, z: 2, pan: 0.3 });
  const held = new Set(['KeyW', 'ArrowRight', 'BracketRight']);
  rig.startRecording(30); run(rig, 3, () => R.fromKeys(rig.pose, held)); const rec = rig.stopRecording();
  assert.strictEqual(rec.version, 1); assert.deepStrictEqual(rec.channels, R.CH);
  assert.ok(rec.samples.length >= 90 && rec.samples.length <= 92, 'samples ' + rec.samples.length);
  near(rec.start.x, 1); near(rec.start.pan, 0.3);
  const last = R.playback(rec, 99); near(last.z, rig.pose.z, 1e-3); near(last.x, rig.pose.x, 1e-3);
  const a = JSON.stringify(R.playback(rec, 1.234)), b = JSON.stringify(R.playback(JSON.parse(JSON.stringify(rec)), 1.234));
  assert.strictEqual(a, b, 'a saved and reloaded move plays back identically');
  assert.strictEqual(rig.isRecording(), false);
});

test('a move with clamped limits records what happened, so it repeats the shot that was got, not the keys that were pressed', () => {
  const rig = R.create(); rig.startRecording(30); run(rig, 3, { tilt: 90 * R.DEG }); const rec = rig.stopRecording();
  assert.ok(Math.max(...rec.samples.map(s => s[R.CH.indexOf('tilt')])) <= 85 * R.DEG + 1e-6);
});

test('mouse aim is analogue: a small slow drag turns a little, a fast one turns a lot, and the wheel zooms (shift pulls focus)', () => {
  const slow = R.fromMouse(R.newPose(), new Set(), { dx: 1, dy: 0 }, 1 / 60), fast = R.fromMouse(R.newPose(), new Set(), { dx: 20, dy: 0 }, 1 / 60);
  assert.ok(fast.pan > slow.pan * 19 && slow.pan > 0);
  assert.ok(R.fromMouse(R.newPose(), new Set(), { dx: 0, dy: 5 }, 1 / 60).tilt < 0);
  assert.ok(R.fromMouse(R.newPose(), new Set(), { wheel: 1 }, 1 / 60).fov > 0);
  const f = R.fromMouse(R.newPose(), new Set(), { wheel: 1, shift: true }, 1 / 60); assert.ok(f.focus > 0 && f.fov === undefined);
  assert.strictEqual(R.fromMouse(R.newPose(), new Set(['ArrowLeft']), {}, 1 / 60).pan, 0);                 // arrows are not aim in this mode
});


test('roll tilts the horizon: a point to the right of centre swings up or down the picture, and no roll changes nothing', () => {
  const p = R.newPose({ fov: 60 * R.DEG }), pt = [3, 1.6, 10];
  const flat = R.project(p, pt), rolled = R.project(Object.assign({}, p, { roll: 30 * R.DEG }), pt);
  assert.ok(Math.abs(rolled.sy - flat.sy) > 0.1 && Math.hypot(rolled.sx * 16 / 9, rolled.sy) - Math.hypot(flat.sx * 16 / 9, flat.sy) < 1e-9);   // moved around the centre, not away from it
  near(R.project(Object.assign({}, p, { roll: 0 }), pt).sx, flat.sx);
  const rig = R.create(); run(rig, 1, R.fromKeys(rig.pose, ['Period'])); assert.ok(rig.pose.roll > 0);
});

test('the result does not depend on the frame rate, and a slow frame rate still records a smooth move', () => {
  const at = fps => { const rig = R.create(); rig.startRecording(30); const held = new Set(['KeyW', 'BracketRight']); for (let t = 0; t < 3 - 1e-9; t += 1 / fps) rig.step(1 / fps, R.fromKeys(rig.pose, held)); return { pose: Object.assign({}, rig.pose), rec: rig.stopRecording() }; };
  const fast = at(144), slow = at(12);
  near(fast.pose.z, slow.pose.z, 0.02); near(fast.pose.fov, slow.pose.fov, 0.002);       // (steering while moving does differ a little: the heading is read once a frame)
  const zs = slow.rec.samples.map(s => s[R.CH.indexOf('z')]);
  const steps = zs.slice(1).map((v, i) => v - zs[i]);
  assert.ok(steps.every(d => d >= 0) && Math.max(...steps) < 0.2, 'the 12 fps recording is not stair-stepped');
  assert.ok(new Set(zs).size > zs.length * 0.95, 'nearly every recorded sample is a new position, not a repeat');
});

test('setPose ignores junk and respects limits, and junk dt and rates cannot break stepping or recording', () => {
  const rig = R.create({ x: 1 });
  rig.setPose({ x: NaN, y: Infinity, tilt: 9, pan: -1, fov: undefined, z: 'a' });
  assert.ok(R.CH.every(c => Number.isFinite(rig.pose[c]))); near(rig.pose.x, 1); near(rig.pose.tilt, 85 * R.DEG); assert.ok(rig.pose.pan >= 0);
  for (const dt of [NaN, -1, Infinity, undefined, 'x', 0]) rig.step(dt, { x: 1 });
  assert.ok(R.CH.every(c => Number.isFinite(rig.pose[c])));
  rig.startRecording(NaN); assert.strictEqual(rig.stopRecording().rate, 30);
  rig.startRecording(1e9); assert.strictEqual(rig.stopRecording().rate, 240);
});

test('lock-on with a dead zone leaves the camera still while the subject stays inside it, and brings it back when it leaves', () => {
  const rig = R.create({ pan: 0 }), still = () => R.fromLock(rig.pose, new Set(), [0.3, 1.6, 10], null, { w: 0.4, h: 0.4 });
  run(rig, 1, still); near(rig.pose.pan, 0, 1e-6);                                                   // 0.3 m at 10 m is well inside: no turn
  const out = R.fromLock(rig.pose, new Set(), [8, 1.6, 10], null, { w: 0.4, h: 0.4 });
  assert.ok(out.pan > 0.5);                                                                          // far outside: turns to catch it
  assert.ok(R.fromLock(rig.pose, new Set(), [0.3, 1.6, 10]).pan > 0);                                // with no zone it always nudges
});

test('orbit keeps its distance and circles the subject while looking at it; a rack focus ends on the new distance', () => {
  const rig = R.create({ x: 4, z: 0, y: 1.7, pan: 0, focus: 4 }), c = [0, 1.7, 0];
  const a0 = Math.atan2(rig.pose.z, rig.pose.x);
  run(rig, 6, () => R.fromOrbit(rig.pose, c, 4, 0.5));
  near(Math.hypot(rig.pose.x, rig.pose.z), 4, 0.1);
  const turned = Math.abs(R.turn(a0, Math.atan2(rig.pose.z, rig.pose.x)));
  assert.ok(turned > 2 && turned < 3.1, 'orbited ' + turned);
  const q = R.project(rig.pose, c); assert.ok(Math.hypot(q.sx, q.sy) < 0.1);
  const r2 = R.create({ focus: 2 }); run(r2, 4, () => R.pullFocus(r2.pose, 9, 3)); near(r2.pose.focus, 9, 0.05);
});

test('lens terms: millimetres and field of view convert both ways, and blur grows with a wider aperture and with distance from focus', () => {
  near(R.fovToFocal(R.focalToFov(50)), 50, 1e-9); assert.ok(R.focalToFov(24) > R.focalToFov(85));
  assert.deepStrictEqual(R.LENSES, [14, 24, 35, 50, 85, 135]);
  assert.strictEqual(R.blurPx(50, 2.8, 5, 5, 1080), 0);                                              // in focus: sharp
  const wide = R.blurPx(50, 1.8, 5, 9, 1080), narrow = R.blurPx(50, 8, 5, 9, 1080);
  assert.ok(wide > narrow && narrow > 0);
  assert.ok(R.blurPx(50, 2.8, 5, 12, 1080) > R.blurPx(50, 2.8, 5, 7, 1080));
  assert.ok(R.blurPx(85, 2.8, 5, 9, 1080) > R.blurPx(35, 2.8, 5, 9, 1080));                           // a longer lens is shallower
  for (const bad of [[0, 2.8, 5, 5], [50, 0, 5, 5], [50, 2.8, -1, 5], [50, 2.8, 5, NaN]]) assert.strictEqual(R.blurPx(...bad, 1080), 0);
});


test('the camera station is described once: every action has a label and a default key, they never collide, and held actions drive the same speeds as held keys', () => {
  const spec = R.keymapSpec(); assert.strictEqual(Object.keys(spec).length, R.ACTIONS.length);
  const KM = require('../static/keymap.js'); const km = KM.create({ camera: spec });             // throws if a default is reserved or doubled
  assert.strictEqual(km.bindings('camera').pan_left, 'ArrowLeft'); assert.strictEqual(km.def('camera', 'zoom_in').kind, 'hold');
  const p = R.newPose({ pan: 0.4 });
  assert.deepStrictEqual(R.fromActions(p, ['move_forward', 'pan_right', 'zoom_in']), R.fromKeys(p, ['KeyW', 'ArrowRight', 'BracketRight']));
  assert.deepStrictEqual(R.fromActions(p, ['nope']), {}); assert.deepStrictEqual(R.fromActions(p, ['move_left', 'move_right']), { x: 0, y: 0, z: 0 });
});
