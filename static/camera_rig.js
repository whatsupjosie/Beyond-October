/* PubCast camera rig: one pose, several ways to drive it, one recorder.
 *
 * Pose channels: x y z (metres, y up), pan (radians, 0 looks along +z, free turn all the way round), tilt (radians),
 * fov (radians, smaller = more zoomed in), focus (metres to the sharp plane).
 *
 * However a camera is driven (held keys, mouse, lock on a subject, a scripted shot an AI wrote) the result is the same
 * thing: a target for each channel's SPEED. A smoothing stage turns that into movement, so every mode is equally smooth
 * and the pose that comes out is the one that is recorded and replayed. Works in a browser and in Node.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PubCastCameraRig = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const TAU = Math.PI * 2, DEG = Math.PI / 180;
  const CH = ["x", "y", "z", "pan", "tilt", "roll", "fov", "focus"];
  const LIMITS = { tilt: [-85 * DEG, 85 * DEG], roll: [-90 * DEG, 90 * DEG], fov: [10 * DEG, 90 * DEG], focus: [0.3, 200], x: [-100, 100], y: [0.2, 60], z: [-100, 100] };
  const TAU_S = { x: 0.25, y: 0.25, z: 0.25, pan: 0.12, tilt: 0.12, roll: 0.15, fov: 0.2, focus: 0.15 };      // seconds to settle: aim is quick, bodies are heavier
  const SPEED = { move: 2.5, pan: 70 * DEG, tilt: 45 * DEG, roll: 30 * DEG, fov: 35 * DEG, focus: 3 };
  const SUB = 1 / 120;                 // longest slice of time integrated in one go, so a slow frame rate cannot coarsen a move or its recording
const wrap = a => { a %= TAU; return a < 0 ? a + TAU : a; };
  const turn = (from, to) => { let d = (to - from) % TAU; if (d > Math.PI) d -= TAU; if (d < -Math.PI) d += TAU; return d; };   // shortest way round
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  function newPose(p) { return Object.assign({ x: 0, y: 1.6, z: 0, pan: 0, tilt: 0, roll: 0, fov: 50 * DEG, focus: 5 }, p || {}); }

  /* the directions a camera moves along, from where it points: trucking is sideways, dollying is forward on the ground */
  function axes(pose) {
    return { right: [Math.cos(pose.pan), 0, -Math.sin(pose.pan)], fwd: [Math.sin(pose.pan), 0, Math.cos(pose.pan)], up: [0, 1, 0] };
  }

  /* Where a point appears in the frame: sx, sy in -1..1 across the picture (0,0 = centre), dist in metres, ok=false if behind. */
  function project(pose, pt, aspect) {
    const v = [pt[0] - pose.x, pt[1] - pose.y, pt[2] - pose.z];
    const cp = Math.cos(pose.pan), sp = Math.sin(pose.pan), ct = Math.cos(pose.tilt), st = Math.sin(pose.tilt);
    const right = v[0] * cp - v[2] * sp, fwd0 = v[0] * sp + v[2] * cp;
    const fwd = fwd0 * ct + v[1] * st, up = v[1] * ct - fwd0 * st;
    const dist = Math.hypot(v[0], v[1], v[2]);
    if (fwd <= 1e-6) return { sx: 0, sy: 0, dist, ok: false };
    const th = Math.tan(pose.fov / 2), a = aspect || 16 / 9;
    let sx = right / (fwd * th * a), sy = up / (fwd * th);
    if (pose.roll) {                                                   // a tilted horizon (Dutch angle): turn the picture about its centre
      const r = -pose.roll, cr = Math.cos(r), sr = Math.sin(r), px = sx * (aspect || 16 / 9), py = sy;
      sx = (px * cr - py * sr) / (aspect || 16 / 9); sy = px * sr + py * cr;
    }
    return { sx, sy, dist, ok: true };
  }
  /* the pan and tilt that point the camera at a point */
  function aimAt(pose, pt) {
    const v = [pt[0] - pose.x, pt[1] - pose.y, pt[2] - pose.z];
    return { pan: Math.atan2(v[0], v[2]), tilt: Math.atan2(v[1], Math.hypot(v[0], v[2])) };
  }

  function create(initial) {
    const pose = newPose(initial), vel = {}; for (const c of CH) vel[c] = 0;
    const state = { t: 0, rec: null, lastSample: -1 };

    /* want: desired speed for any channels (units per second; radians for pan and tilt). One smoothing step of dt seconds. */
    function integrate(h, want) {
      for (const c of CH) {
        const target = want && Number.isFinite(want[c]) ? want[c] : 0;
        vel[c] += (target - vel[c]) * (1 - Math.exp(-h / TAU_S[c]));
        pose[c] += vel[c] * h;
        if (c === "pan") pose.pan = wrap(pose.pan);
        else if (LIMITS[c]) {
          const [lo, hi] = LIMITS[c];
          if (pose[c] < lo || pose[c] > hi) { pose[c] = clamp(pose[c], lo, hi); vel[c] = 0; }        // a limit stops the move, it does not store up speed
        }
      }
    }
    /* want: desired speed for any channels (units per second; radians for pan, tilt and roll). Advances dt seconds in slices
       of at most 1/120 s, so the result (and the recording) is the same at 15 frames a second as at 144. */
    function step(dt, want) {
      dt = Number.isFinite(dt) ? Math.min(Math.max(dt, 0), 0.25) : 0;
      if (dt === 0) { if (state.rec) record(); return pose; }
      const n = Math.ceil(dt / SUB - 1e-9), h = dt / n;
      for (let i = 0; i < n; i++) { integrate(h, want); state.t += h; if (state.rec) record(); }
      return pose;
    }

    /* ---- recording: the pose that resulted, sampled at a fixed rate on the camera's own clock ---- */
    function startRecording(rate) {
      state.rec = { rate: Number.isFinite(rate) && rate > 0 ? Math.min(rate, 240) : 30, start: Object.assign({}, pose), t0: state.t, samples: [] }; state.lastSample = -1; record();
    }
    function record() {
      const r = state.rec, n = Math.floor((state.t - r.t0) * r.rate + 1e-9);
      while (r.samples.length <= n) r.samples.push(CH.map(c => +pose[c].toFixed(5)));
    }
    function stopRecording() { const r = state.rec; state.rec = null; return r && { version: 1, rate: r.rate, channels: CH.slice(), start: r.start, samples: r.samples }; }
    /* put the camera somewhere; anything that is not a finite number is ignored, and limits still apply */
    function setPose(p) {
      for (const c of CH) {
        if (!p || !Number.isFinite(p[c])) continue;
        pose[c] = c === "pan" ? wrap(p[c]) : LIMITS[c] ? clamp(p[c], LIMITS[c][0], LIMITS[c][1]) : p[c];
      }
      for (const c of CH) vel[c] = 0;
    }

    return { pose, step, startRecording, stopRecording, setPose, velocity: () => Object.assign({}, vel), time: () => state.t, isRecording: () => !!state.rec };
  }

  /* ---- ways to drive it. Each turns what the operator is doing into wanted speeds. ---- */

  /* A. held keys. The camera's controls are ACTIONS, each with a label and a default key, and the key map assigns the keys;
        fromActions turns whatever is held into wanted speeds. Any number can be held at once. */
  const ACTIONS = [
    ["move_right", "Truck right", "KeyD", "move", "right", 1], ["move_left", "Truck left", "KeyA", "move", "right", -1],
    ["move_forward", "Dolly in", "KeyW", "move", "fwd", 1], ["move_back", "Dolly out", "KeyS", "move", "fwd", -1],
    ["move_up", "Pedestal up", "KeyE", "move", "up", 1], ["move_down", "Pedestal down", "KeyQ", "move", "up", -1],
    ["pan_right", "Pan right", "ArrowRight", "pan", 1], ["pan_left", "Pan left", "ArrowLeft", "pan", -1],
    ["tilt_up", "Tilt up", "ArrowUp", "tilt", 1], ["tilt_down", "Tilt down", "ArrowDown", "tilt", -1],
    ["roll_right", "Roll right", "Period", "roll", 1], ["roll_left", "Roll left", "Comma", "roll", -1],
    ["zoom_in", "Zoom in", "BracketRight", "fov", -1], ["zoom_out", "Zoom out", "BracketLeft", "fov", 1],
    ["focus_far", "Focus farther", "Quote", "focus", 1], ["focus_near", "Focus nearer", "Semicolon", "focus", -1],
  ];
  const BY_ACTION = {}; for (const a of ACTIONS) BY_ACTION[a[0]] = a;
  function fromActions(pose, actions) {
    const w = {}, ax = axes(pose);
    for (const id of actions) {
      const a = BY_ACTION[id]; if (!a) continue;
      if (a[3] === "move") { const d = ax[a[4]], s = SPEED.move * a[5]; w.x = (w.x || 0) + d[0] * s; w.y = (w.y || 0) + d[1] * s; w.z = (w.z || 0) + d[2] * s; }
      else w[a[3]] = (w[a[3]] || 0) + SPEED[a[3]] * a[4 + (a[3] === "move" ? 1 : 0)];
    }
    return w;
  }
  /* default keys by code (arrows, WASD, brackets ...), for the try page and tests; the program uses fromActions with the key map */
  const KEYS = {}; for (const a of ACTIONS) KEYS[a[2]] = a[0];
  const fromKeys = (pose, held) => fromActions(pose, [...held].map(c => KEYS[c]).filter(Boolean));
  /* what the key map needs to know about the camera station: id, label, the kind of control, default key */
  const keymapSpec = () => { const o = {}; for (const a of ACTIONS) o[a[0]] = { label: a[1], kind: "hold", key: a[2] }; return o; };

  /* B. mouse for aim: movement since the last step becomes a speed (analogue, so slow and fast both work); wheel zooms, shift-wheel pulls focus; keys still move */
  function fromMouse(pose, held, mouse, dt, sens) {
    const w = fromKeys(pose, [...held].filter(c => !KEYS[c] || /^move_/.test(KEYS[c])));
    const k = (sens || 0.0025) / Math.max(dt, 1e-3);
    w.pan = (mouse.dx || 0) * k; w.tilt = -(mouse.dy || 0) * k;
    if (mouse.wheel) { if (mouse.shift) w.focus = mouse.wheel * 4; else w.fov = mouse.wheel * 40 * DEG; }
    return w;
  }
  /* C. lock on a subject: aim follows it by itself, focus follows its distance; the operator only moves and zooms.
        offset holds it off-centre. zone = {w, h} is the DEAD ZONE (fractions of the half-frame): while the subject stays inside it
        the camera does not turn, so small movements do not make the picture twitch; just outside it a soft zone eases the aim back. */
  function fromLock(pose, held, subject, offset, zone) {
    const w = fromKeys(pose, [...held].filter(c => !KEYS[c] || /^move_|^zoom_/.test(KEYS[c])));
    const a = aimAt(pose, subject), off = offset || { pan: 0, tilt: 0 }, q = project(pose, subject);
    const soft = (v, dz) => (dz > 0 ? clamp((Math.abs(v) - dz) / 0.25, 0, 1) : 1);
    const kx = zone && q.ok ? soft(q.sx, zone.w || 0) : 1, ky = zone && q.ok ? soft(q.sy, zone.h || 0) : 1;
    w.pan = 6 * turn(pose.pan, a.pan + off.pan) * kx; w.tilt = 6 * (a.tilt + off.tilt - pose.tilt) * ky;
    w.focus = 6 * (q.dist - pose.focus);
    return w;
  }
  /* E. orbit a point at a fixed distance, looking at it (an arc shot, a turntable) */
  function fromOrbit(pose, centre, radius, rate) {
    const dx = pose.x - centre[0], dz = pose.z - centre[2], r = Math.hypot(dx, dz) || 1e-9, a = aimAt(pose, centre);
    const tx = -dz / r, tz = dx / r, rx = dx / r, rz = dz / r, v = rate * radius, fix = 4 * (radius - r);
    return { x: tx * v + rx * fix, z: tz * v + rz * fix, pan: 6 * turn(pose.pan, a.pan), tilt: 6 * (a.tilt - pose.tilt), focus: 6 * (Math.hypot(dx, pose.y - centre[1], dz) - pose.focus) };
  }
  /* F. pull focus to a distance, at a given speed (metres a second): a rack focus */
  function pullFocus(pose, target, rate) {
    const e = target - pose.focus, v = Math.min(Math.abs(e) * 6, rate || 3);
    return { focus: Math.sign(e) * v };
  }

  /* D. a scripted shot, the way an AI operator or a stored move drives it: keyframes in time, eased. Gives a pose, not a speed. */
  const ease = u => u * u * (3 - 2 * u);
  function shotPose(keys, t) {
    if (!keys.length) return null;
    if (t <= keys[0].t) return newPose(keys[0].pose);
    for (let i = 1; i < keys.length; i++) if (t <= keys[i].t) {
      const a = keys[i - 1], b = keys[i], u = ease((t - a.t) / Math.max(b.t - a.t, 1e-9)), out = {};
      for (const c of CH) out[c] = c === "pan" ? wrap(a.pose.pan + turn(a.pose.pan, b.pose.pan) * u) : a.pose[c] + (b.pose[c] - a.pose[c]) * u;
      return out;
    }
    return newPose(keys[keys.length - 1].pose);
  }
  /* replay a recording exactly: same samples, same clock, same pose. Position, fov and focus in straight lines; pan the short way round. */
  function playback(rec, t) {
    const n = rec.samples.length; if (!n) return null;
    const f = clamp(t * rec.rate, 0, n - 1), i = Math.floor(f), j = Math.min(i + 1, n - 1), u = f - i, out = {};
    rec.channels.forEach((c, k) => {
      const a = rec.samples[i][k], b = rec.samples[j][k];
      out[c] = c === "pan" ? wrap(a + turn(a, b) * u) : a + (b - a) * u;
    });
    return out;
  }

  /* ---- the lens, in the terms a cinematographer uses ---- */
  const SENSOR_H = 24;                                                        // millimetres: a full-frame 36 x 24 film back
  const LENSES = [14, 24, 35, 50, 85, 135];                                   // the usual prime lenses, in mm
  const focalToFov = (mm, sensorH) => 2 * Math.atan((sensorH || SENSOR_H) / (2 * mm));
  const fovToFocal = (fov, sensorH) => (sensorH || SENSOR_H) / (2 * Math.tan(fov / 2));
  /* How soft a subject looks: the blur circle in picture pixels, from the thin-lens formula, for focal length (mm), f-stop,
     the distance the lens is set to and the subject's distance (metres), and the picture height in pixels. 0 = sharp. */
  function blurPx(focalMm, fstop, focusM, subjectM, heightPx, sensorH) {
    const f = focalMm, N = fstop, ds = subjectM * 1000, df = focusM * 1000;
    if (!(f > 0 && N > 0 && ds > f && df > f)) return 0;
    const c = (f * f / N) * Math.abs(ds - df) / (ds * (df - f));              // blur circle on the sensor, mm
    return c / (sensorH || SENSOR_H) * heightPx;
  }

  return { create, project, aimAt, axes, fromKeys, fromActions, keymapSpec, ACTIONS, fromMouse, fromLock, fromOrbit, pullFocus, shotPose, focalToFov, fovToFocal, blurPx, LENSES, SUB, playback, newPose, turn, wrap, CH, KEYS, SPEED, LIMITS, DEG };
});
