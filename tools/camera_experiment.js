#!/usr/bin/env node
/* Compare ways of driving the camera on one fixed job, with a simple simulated operator.
 *
 * The job: a subject walks across the set; the camera pushes in four metres over the first six seconds and holds, and must
 * keep the subject inside the middle of the frame and in focus for twelve seconds. The operator sees the picture a quarter
 * second late and decides ten times a second, like a person would, with a little noise (seeded, so every run is the same).
 *
 * This is a MODEL of an operator, not a person. It says which modes ask for less at once and which come out smoother; it
 * cannot say which one feels best. For that, try them: static/camera_try.html.
 */
"use strict";
const R = require("../static/camera_rig.js");
const DT = 1 / 60, SECONDS = 12, DELAY = 0.25, THINK = 0.1;
const subjectAt = t => [1.2 * t - 6, 1.7, 3];
const START = { x: -4, y: 1.6, z: -8, pan: 0, tilt: 0, fov: 50 * R.DEG, focus: 5 };
const pushZ = t => -8 + 4 * Math.min(1, t / 6);
function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
const sign = v => (v > 0 ? 1 : v < 0 ? -1 : 0);

/* one operator policy per mode: given what they saw (delayed), return what they hold or do */
const OPERATORS = {
  keys(seen, rnd) {
    const held = new Set(), db = 0.12 + rnd() * 0.04;
    if (seen.sx > db) held.add("ArrowRight"); else if (seen.sx < -db) held.add("ArrowLeft");
    if (seen.sy > db) held.add("ArrowUp"); else if (seen.sy < -db) held.add("ArrowDown");
    if (seen.focusErr > 0.06) held.add("Semicolon"); else if (seen.focusErr < -0.06) held.add("Quote");   // focus set too far: pull it in
    if (seen.z < pushZ(seen.t) - 0.15) held.add("KeyW");
    return { held };
  },
  mouse(seen, rnd) {
    const held = new Set(), g = 0.8 + rnd() * 0.3;
    if (seen.z < pushZ(seen.t) - 0.15) held.add("KeyW");
    return { held, mouse: { dx: clampPx(seen.sx * 30 * g), dy: clampPx(-seen.sy * 30 * g), wheel: 0 }, focusWheel: Math.abs(seen.focusErr) > 0.06 ? sign(-seen.focusErr) : 0 };
  },
  lock(seen) {
    const held = new Set(); if (seen.z < pushZ(seen.t) - 0.15) held.add("KeyW"); return { held };
  },
};
const clampPx = v => Math.max(-40, Math.min(40, Math.round(v)));

function activeChannels(mode, op) {          // how many separate things the operator is working at this moment
  const h = op.held || new Set(); let n = 0;
  if (h.has("KeyW") || h.has("KeyS")) n++;
  if (mode === "keys") { if (h.has("ArrowLeft") || h.has("ArrowRight")) n++; if (h.has("ArrowUp") || h.has("ArrowDown")) n++; if (h.has("Quote") || h.has("Semicolon")) n++; }
  if (mode === "mouse") { if (op.mouse && (op.mouse.dx || op.mouse.dy)) n++; if (op.focusWheel) n++; }
  return n;
}

function runMode(mode, seed) {
  const rig = R.create(START), rnd = rng(seed), hist = [];
  let op = { held: new Set() }, nextThink = 0, shot = null;
  if (mode === "shot") {                      // an AI operator that knows the plan: a pose every second, eased between
    shot = [];
    for (let k = 0; k <= SECONDS; k++) {
      const z = pushZ(k), p = R.newPose({ x: -4, y: 1.6, z, fov: 50 * R.DEG }), a = R.aimAt(p, subjectAt(k));
      shot.push({ t: k, pose: Object.assign(p, a, { focus: R.project(Object.assign({}, p, a), subjectAt(k)).dist }) });
    }
    rig.setPose(shot[0].pose);
  }
  const frames = [];
  for (let t = 0; t < SECONDS; t += DT) {
    const sub = subjectAt(t), q = R.project(rig.pose, sub);
    frames.push({ t, sx: q.sx, sy: q.sy, ok: q.ok, focusErr: (rig.pose.focus - q.dist) / q.dist, z: rig.pose.z, pan: rig.pose.pan, tilt: rig.pose.tilt });
    const past = frames[Math.max(0, frames.length - 1 - Math.round(DELAY / DT))];
    if (mode === "shot") { rig.setPose(R.shotPose(shot, t + DT)); hist.push(activeChannels(mode, { held: new Set() })); continue; }
    if (t >= nextThink) { op = OPERATORS[mode](past, rnd); nextThink = t + THINK; hist.push(activeChannels(mode, op)); op.mouseLeft = true; }
    let want;
    if (mode === "keys") want = R.fromKeys(rig.pose, op.held);
    else if (mode === "mouse") {
      const m = op.mouse ? { dx: op.mouse.dx * (DT / THINK), dy: op.mouse.dy * (DT / THINK), wheel: op.focusWheel, shift: true } : {};
      want = R.fromMouse(rig.pose, op.held, m, DT);
    } else want = R.fromLock(rig.pose, op.held, sub);
    rig.step(DT, want);
  }
  const from = frames.filter(f => f.t > 1);
  const err = f => (f.ok ? Math.hypot(f.sx, f.sy) : 2);
  const acc = []; for (let i = 2; i < frames.length; i++) { const a = R.turn(frames[i - 1].pan, frames[i].pan) - R.turn(frames[i - 2].pan, frames[i - 1].pan); acc.push(a / (DT * DT)); }
  const rms = a => Math.sqrt(a.reduce((s, v) => s + v * v, 0) / a.length);
  return {
    framing: from.reduce((s, f) => s + err(f), 0) / from.length,
    inFrame: 100 * from.filter(f => err(f) < 0.4).length / from.length,
    focusPct: 100 * from.reduce((s, f) => s + Math.abs(f.focusErr), 0) / from.length,
    shake: rms(acc) * DT,                                   // pan jerkiness: change in pan speed per frame, rad/s
    channels: hist.length ? hist.reduce((s, v) => s + v, 0) / hist.length : 0,
  };
}

function summarize(mode, seeds) {
  const rows = seeds.map(s => runMode(mode, s)), avg = k => rows.reduce((s, r) => s + r[k], 0) / rows.length;
  return { mode, framing: avg("framing"), inFrame: avg("inFrame"), focusPct: avg("focusPct"), shake: avg("shake"), channels: avg("channels") };
}

if (require.main === module) {
  const seeds = Array.from({ length: 20 }, (_, i) => 1000 + i), names = { keys: "A. keys only", mouse: "B. mouse aim + keys", lock: "C. lock on subject", shot: "D. scripted shot (AI)" };
  console.log("Job: push in 4 m over 6 s, keep a walking subject framed and in focus for 12 s. 20 simulated runs each.\n");
  console.log("mode                    framing   in frame   focus off   pan shake   things worked at once");
  for (const m of ["keys", "mouse", "lock", "shot"]) {
    const r = summarize(m, seeds);
    console.log(`${names[m].padEnd(24)}${r.framing.toFixed(2).padStart(6)}   ${r.inFrame.toFixed(0).padStart(6)}%   ${r.focusPct.toFixed(1).padStart(7)}%   ${r.shake.toFixed(3).padStart(8)}   ${r.channels.toFixed(1).padStart(10)}`);
  }
}
module.exports = { runMode, summarize };
