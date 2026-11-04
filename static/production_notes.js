/* PubCast AI — production_notes.js
 * Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
 * Rearview Foresight LLC — All Rights Reserved
 * Feic Mo Chroí — See My Heart
 *
 * Production notes in Bella Faux Pas Studio (the walker, static/world_walk.html).
 *
 * In the rooms: each unread note is a small sticky note laid flat on a surface (the makeup mirror always, plus any spot
 * its sender chose), in that surface's perspective, so its edges aim at the same point on the horizon line as the
 * surface's own. At most three per spot. A gold foil star on each note's top right corner catches a glint every few
 * seconds (not with reduced motion). Notes are painted into the room picture, so an avatar in front covers them. In a
 * close-up a note can be clicked; in a wide shot it is only seen, and the hotspot's bubble offers to read it.
 * The dressing room corkboard has a sticky note of its own that opens the notes menu, notes or not.
 *
 * The menu: the room blurs; a column of notes, newest on top, grouped by date or by project; Inbox, Saved, Sent.
 * A note opens as one big sticky note laid out like an email, scrolling inside. Reply, Reply all, Save, Trash,
 * New sticky note. Writing one: To / CC / BCC (people, everyone in the production, or yourself), subject (what is
 * written on the sticky note), project, message, where to stick it, attachments, and an optional copy addressed in
 * your own email program.
 *
 * Hooks the walker calls: drawScene(ctx, viewKey, pictureScale), click(viewKey, point), hotspotNotes(viewKey, id),
 * onView(viewKey), open(), refresh(). Data: /api/notes, /api/production/people, /api/notes/spots,
 * /static/world/note_spots.json. Everything a person wrote is set as text, never as markup.
 */
(function () {
  "use strict";

  const HAND = '"PN Caveat", cursive', SERIF = '"PN Garamond", Georgia, serif';
  const POLL_MS = 20000, GRID = 5, MAX_PER_SPOT = 3;
  const reduceMotion = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };

  /* ---------------------------------------------------------------- style */
  const css = `
@font-face { font-family: "PN Caveat"; src: url("/static/fonts/caveat-latin-700-normal.woff2") format("woff2"); font-weight: 700; font-display: block; }
@font-face { font-family: "PN Garamond"; src: url("/static/fonts/eb-garamond-latin-400-normal.woff2") format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "PN Garamond"; src: url("/static/fonts/eb-garamond-latin-600-normal.woff2") format("woff2"); font-weight: 600; font-display: swap; }
#pnLayer { position: absolute; inset: 0; z-index: 15; display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(9px) brightness(.55) saturate(.8); -webkit-backdrop-filter: blur(9px) brightness(.55) saturate(.8);
  background: rgba(12,9,6,.18); font: 400 17px/1.4 ${SERIF}; color: #35291a; }
#pnLayer[hidden] { display: none; }
#pnLayer button { font: 600 16px/1 ${SERIF}; min-height: 36px; border-radius: 4px; cursor: pointer; }
.pn-bar { position: absolute; top: 14px; right: 16px; display: flex; gap: 8px; }
.pn-brass { color: #f6e9c8; padding: 9px 18px; background: linear-gradient(180deg, #4a3a22 0%, #2a2014 100%);
  border: 1px solid #b8924a; box-shadow: inset 0 1px 0 rgba(230,201,138,.35), 0 3px 8px rgba(0,0,0,.5); }
.pn-brass.primary { background: linear-gradient(180deg, #d9b56c 0%, #a9823d 100%); color: #21180c; border-color: #f0d79e; }
.pn-brass:hover { filter: brightness(1.12); }
.pn-brass:focus-visible, .pn-card:focus-visible, .pn-tab:focus-visible { outline: 2px solid #f0d79e; outline-offset: 3px; }
.pn-menu { display: flex; flex-direction: column; align-items: center; max-height: 100%; width: min(420px, 92%); padding: 64px 0 18px; }
.pn-tabs { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; justify-content: center; }
.pn-tab { color: #f6e9c8; background: transparent; border: 1px solid rgba(240,215,158,.35); padding: 7px 12px; font: 400 15px/1 ${SERIF} !important; }
.pn-tab[aria-pressed="true"] { border-color: #f0d79e; background: rgba(217,181,108,.22); }
.pn-col { overflow-y: auto; overflow-x: hidden; width: 100%; padding: 6px 14px 30px; display: flex; flex-direction: column; gap: 14px; scrollbar-width: thin; }
.pn-group { color: rgba(246,233,200,.85); font: 600 15px/1.2 ${SERIF}; margin: 6px 4px -6px; }
.pn-card { position: relative; isolation: isolate; text-align: left; border: 0; background: none; padding: 16px 22px 12px 22px;
  color: #35291a; min-height: 92px; width: 100%; }
.pn-card:nth-of-type(odd) { transform: rotate(-1.1deg); } .pn-card:nth-of-type(even) { transform: rotate(.8deg) translateX(8px); }
.pn-card h3 { margin: 0; font: 700 30px/1.05 ${HAND}; overflow-wrap: anywhere; }
.pn-card .pn-meta { margin-top: 5px; font: 400 15px/1.3 ${SERIF}; color: #6b5638; }
.pn-card.unread::after { content: ""; position: absolute; top: 15px; right: 18px; width: 10px; height: 10px; border-radius: 50%;
  background: #9c3b2a; box-shadow: 0 0 0 2px rgba(255,240,200,.6); }
.pn-paper { position: absolute; z-index: -1; pointer-events: none; }
.pn-empty { color: rgba(246,233,200,.85); text-align: center; padding: 30px 10px; }
.pn-sheet { position: relative; isolation: isolate; width: min(640px, 94%); height: min(640px, calc(100% - 140px));
  padding: 44px 44px 0 48px; display: flex; flex-direction: column; transform: rotate(-.6deg); }
.pn-scroll { position: relative; flex: 1; overflow-y: auto; padding: 0 14px 40px 0; scrollbar-width: thin; scrollbar-color: rgba(90,70,40,.5) transparent; }
.pn-scroll:focus { outline: none; } .pn-scroll:focus-visible { outline: 2px solid rgba(169,130,61,.55); outline-offset: 6px; }
.pn-scroll::-webkit-scrollbar { width: 6px; } .pn-scroll::-webkit-scrollbar-thumb { background: rgba(90,70,40,.45); border-radius: 3px; }
.pn-sheet h1 { margin: 0 0 12px; font: 700 46px/1.02 ${HAND}; overflow-wrap: anywhere; }
.pn-fields { display: grid; grid-template-columns: 70px 1fr; gap: 3px 10px; font-size: 17px; padding-bottom: 12px; border-bottom: 1px solid rgba(90,70,40,.3); margin: 0; }
.pn-fields dt { color: #6b5638; } .pn-fields dd { margin: 0; overflow-wrap: anywhere; }
.pn-body { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 20px; line-height: 1.45; padding-top: 14px; }
.pn-files { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 14px; }
.pn-chip { font: 400 15px/1 ${SERIF} !important; padding: 8px 11px; border: 1px solid rgba(90,70,40,.45); background: rgba(255,250,230,.35); color: #35291a; }
.pn-actions { position: absolute; left: 50%; bottom: 14px; transform: translateX(-50%); display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; width: 96%; }
.pn-form label { display: block; margin: 0 0 10px; font-size: 15px; color: #6b5638; }
.pn-form input[type=text], .pn-form textarea { display: block; width: 100%; margin-top: 3px; font: 400 18px/1.35 ${SERIF}; color: #35291a;
  background: rgba(255,252,238,.45); border: 0; border-bottom: 1px solid rgba(90,70,40,.4); padding: 5px 4px; }
.pn-form input.pn-subject { font: 700 34px/1.1 ${HAND}; }
.pn-form textarea { min-height: 150px; resize: vertical; }
.pn-form input:focus-visible, .pn-form textarea:focus-visible { outline: 2px solid #a9823d; outline-offset: 1px; }
.pn-picks { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.pn-pick { font: 400 15px/1 ${SERIF} !important; padding: 6px 10px; min-height: 30px !important; border: 1px solid rgba(90,70,40,.45); background: rgba(255,250,230,.3); color: #35291a; }
.pn-pick[aria-pressed="true"] { background: #35291a; color: #f6e9c8; border-color: #35291a; }
.pn-pick:disabled { opacity: 1; cursor: default; }
.pn-row { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; font-size: 15px; color: #6b5638; margin-bottom: 10px; }
.pn-msg { min-height: 1.3em; color: #8a2b1c; font-size: 15px; }
.pn-msg.ok { color: #2f5a2a; }
.pn-mail { display: inline-block; margin-top: 6px; color: #35291a; font-weight: 600; }
@media (max-width: 640px) { .pn-sheet { padding: 34px 24px 0 26px; } .pn-sheet h1 { font-size: 38px; } .pn-fields { grid-template-columns: 54px 1fr; } }
`;
  const style = document.createElement("style"); style.textContent = css; document.head.appendChild(style);

  /* ---------------------------------------------------------------- state */
  const N = {
    enabled: false, notes: [], unread: 0, file: null, people: null, me: null, spotCatalog: null,
    box: "inbox", group: "date", hits: [], openId: null, view: "", fontsReady: false, bitmaps: new Map(),
  };

  async function api(path, opts) {
    opts = opts || {};
    let res;
    try {
      res = await fetch(path, Object.assign({ cache: "no-store" }, opts));
    } catch (e) { return { ok: false, status: 0, text: "The PubCast host could not be reached." }; }
    let data = null; try { data = await res.json(); } catch (e) { data = null; }
    if (res.ok) return { ok: true, status: res.status, data };
    const d = data && data.detail;
    return { ok: false, status: res.status, text: typeof d === "string" ? d : "The host answered " + res.status + "." };
  }
  const json = body => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  async function loadSpotFile() {
    if (N.file) return N.file;
    try { const r = await fetch("/static/world/note_spots.json", { cache: "no-cache" }); N.file = await r.json(); }
    catch (e) { N.file = { spots: {} }; }
    return N.file;
  }

  async function refresh() {
    await loadSpotFile();
    const r = await api("/api/notes?box=inbox");
    if (!r.ok) { N.enabled = r.status !== 401 && r.status !== 403 ? N.enabled : false; return false; }
    N.enabled = true; N.notes = r.data.notes; N.unread = r.data.unread;
    const keep = new Set(N.notes.map(n => n.id));
    for (const k of N.bitmaps.keys()) if (!keep.has(k.split("|")[0]) && !k.startsWith("menu|")) N.bitmaps.delete(k);
    return true;
  }

  /* ---------------------------------------------------------------- geometry */
  function solve(A, b) {
    const n = b.length;
    for (let i = 0; i < n; i++) {
      let m = i; for (let k = i + 1; k < n; k++) if (Math.abs(A[k][i]) > Math.abs(A[m][i])) m = k;
      [A[i], A[m]] = [A[m], A[i]]; [b[i], b[m]] = [b[m], b[i]];
      for (let k = i + 1; k < n; k++) { const f = A[k][i] / A[i][i]; for (let j = i; j < n; j++) A[k][j] -= f * A[i][j]; b[k] -= f * b[i]; }
    }
    const x = Array(n).fill(0);
    for (let i = n - 1; i >= 0; i--) { let s = b[i]; for (let j = i + 1; j < n; j++) s -= A[i][j] * x[j]; x[i] = s / A[i][i]; }
    return x;
  }
  function homography(src, dst) {
    const A = [], b = [];
    src.forEach(([x, y], i) => { const [u, v] = dst[i];
      A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u); A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v); });
    const h = solve(A, b); return [[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1]];
  }
  const apply = (H, [x, y]) => { const w = H[2][0] * x + H[2][1] * y + H[2][2];
    return [(H[0][0] * x + H[0][1] * y + H[0][2]) / w, (H[1][0] * x + H[1][1] * y + H[1][2]) / w]; };
  const len = (p, q) => Math.hypot(q[0] - p[0], q[1] - p[1]);
  /* Corners in the picture of a square note on `surface` at slot [u, v, tilt]: the tilt happens in the surface's own
     plane (measured in its real proportions), then everything goes through the surface's perspective. */
  function noteQuad(surface, slot, noteW) {
    const Q = surface.quad, Hs = homography([[0, 0], [1, 0], [1, 1], [0, 1]], Q);
    const sw = (len(Q[0], Q[1]) + len(Q[3], Q[2])) / 2, sh = (len(Q[0], Q[3]) + len(Q[1], Q[2])) / 2;
    const su = noteW, sv = noteW * sw / sh, [u, v, tilt] = slot, a = (tilt || 0) * Math.PI / 180;
    const cx = u + su / 2, cy = v + sv / 2;
    return [[-.5, -.5], [.5, -.5], [.5, .5], [-.5, .5]].map(([du, dv]) => {
      const x = du * su * sw, y = dv * sv * sh;
      return apply(Hs, [cx + (x * Math.cos(a) - y * Math.sin(a)) / sw, cy + (x * Math.sin(a) + y * Math.cos(a)) / sh]);
    });
  }
  function inQuad(p, q) {
    let inside = false;
    for (let i = 0, j = q.length - 1; i < q.length; j = i++) {
      const [xi, yi] = q[i], [xj, yj] = q[j];
      if ((yi > p[1]) !== (yj > p[1]) && p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }

  /* ---------------------------------------------------------------- paper */
  function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  const seedOf = s => { let h = 2166136261; for (const ch of String(s)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
  /* The sheet, modelled on Josie's reference: torn edges all round (rougher right and bottom), the bottom right corner
     rolled up off the page showing its darker underside, a faint sticky strip along the top, light from the upper left. */
  function paperPaths(w, h, seed, rough, curl) {
    const r = rng(seed), step = Math.max(2, Math.min(w, h) / 55), j = k => (r() - 0.5) * 2 * rough * k;
    let d = `M0,${j(0.6)}`;
    for (let x = step; x < w; x += step) d += `L${x},${j(0.6)}`;
    for (let y = 0; y < h - curl; y += step) d += `L${w + j(1)},${y}`;
    d += `L${w},${h - curl}Q${w - curl * .42},${h - curl * .42} ${w - curl},${h}`;
    for (let x = w - curl - step; x > 0; x -= step) d += `L${x},${h + j(1)}`;
    for (let y = h; y > 0; y -= step) d += `L${j(0.7)},${y}`;
    d += "Z";
    const c = curl, curlD = `M${w},${h - c}Q${w - c * .42},${h - c * .42} ${w - c},${h}Q${w - c * .34},${h - c * .2} ${w - c * .24},${h - c * .24}Q${w - c * .2},${h - c * .34} ${w},${h - c}Z`;
    return { outline: new Path2D(d), curl: new Path2D(curlD), fold: new Path2D(`M${w},${h - c}Q${w - c * .42},${h - c * .42} ${w - c},${h}`) };
  }
  let grainPattern = null;
  function grain(g) {
    if (grainPattern) return grainPattern;
    const n = document.createElement("canvas"); n.width = n.height = 96; const x = n.getContext("2d"), im = x.createImageData(96, 96), r = rng(99);
    for (let i = 0; i < im.data.length; i += 4) { const v = r(); im.data[i] = 110; im.data[i + 1] = 92; im.data[i + 2] = 52; im.data[i + 3] = v * 22; }
    x.putImageData(im, 0, 0); grainPattern = g.createPattern(n, "repeat"); return grainPattern;
  }
  /* Draw a sheet of size w x h at (0,0) of g. shadow is how far it sits off the surface. */
  function drawPaper(g, w, h, seed, opts) {
    const rough = opts.rough != null ? opts.rough : Math.max(.4, w / 110), curl = opts.curl != null ? opts.curl : w * .2;
    const P = paperPaths(w, h, seed, rough, curl), sh = opts.shadow != null ? opts.shadow : w / 30;
    g.save();
    g.shadowColor = "rgba(25,14,4,.45)"; g.shadowBlur = sh * 1.6; g.shadowOffsetX = sh * .55; g.shadowOffsetY = sh * 1.1;
    g.fillStyle = "#e6ddb2"; g.fill(P.outline);
    g.restore();
    const rad = g.createRadialGradient(w * .22, h * .14, 0, w * .22, h * .14, Math.hypot(w, h) * 1.02);
    rad.addColorStop(0, "#f1ebc9"); rad.addColorStop(.55, "#e6ddb2"); rad.addColorStop(1, "#d8cc98");
    g.fillStyle = rad; g.fill(P.outline);
    g.save(); g.clip(P.outline);
    g.fillStyle = grain(g); g.fillRect(0, 0, w, h);
    g.fillStyle = "rgba(105,96,70,.10)"; g.fillRect(0, 0, w, h * (opts.strip || .13));
    g.restore();
    g.save();                                                        // the curl's own shadow, on the surface below it
    g.shadowColor = "rgba(25,14,4,.5)"; g.shadowBlur = sh * 1.2; g.shadowOffsetX = sh * .8; g.shadowOffsetY = sh * 1.2;
    const cg = g.createLinearGradient(w - curl, h - curl, w, h);
    cg.addColorStop(0, "#f2e8bd"); cg.addColorStop(.45, "#ddca86"); cg.addColorStop(1, "#b79d50");
    g.fillStyle = cg; g.fill(P.curl);
    g.restore();
    g.strokeStyle = "rgba(90,70,30,.35)"; g.lineWidth = Math.max(.4, rough * .35); g.stroke(P.fold);
  }
  /* A small gold foil star, as if stuck on: points, a bevel of light from the upper left. */
  function starPath(cx, cy, R) {
    const p = new Path2D();
    for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? R * .45 : R; p[i ? "lineTo" : "moveTo"](cx + rr * Math.cos(a), cy + rr * Math.sin(a)); }
    p.closePath(); return p;
  }
  function drawStar(g, cx, cy, R) {
    const p = starPath(cx, cy, R);
    g.save();
    g.shadowColor = "rgba(40,24,4,.45)"; g.shadowBlur = R * .3; g.shadowOffsetX = R * .08; g.shadowOffsetY = R * .14;
    const gr = g.createLinearGradient(cx - R, cy - R, cx + R, cy + R);
    gr.addColorStop(0, "#fff1b8"); gr.addColorStop(.3, "#e6bf55"); gr.addColorStop(.55, "#b8862a"); gr.addColorStop(.8, "#e9c766"); gr.addColorStop(1, "#8f6418");
    g.fillStyle = gr; g.fill(p);
    g.restore();
    g.strokeStyle = "rgba(110,72,12,.6)"; g.lineWidth = Math.max(.5, R * .07); g.stroke(p);
  }
  function wrapLines(g, text, maxW, maxLines) {
    const words = String(text).split(/\s+/).filter(Boolean), lines = [];
    let line = "";
    for (const w of words) {
      const t = line ? line + " " + w : w;
      if (g.measureText(t).width <= maxW || !line) line = t; else { lines.push(line); line = w; }
      if (lines.length === maxLines) break;
    }
    if (lines.length < maxLines && line) lines.push(line);
    if (lines.length === maxLines && words.join(" ") !== lines.join(" ")) {
      let last = lines[maxLines - 1]; while (last && g.measureText(last + "…").width > maxW) last = last.slice(0, -1);
      lines[maxLines - 1] = last + "…";
    }
    return lines;
  }
  /* The bitmap of an in-room note: sheet, star, the subject in handwriting. M is the margin kept for the shadow. */
  const SIZE = 220, M = 24;
  function noteBitmap(key, subject, seed, withStar, sub) {
    const cached = N.bitmaps.get(key); if (cached) return cached;
    const cv = document.createElement("canvas"); cv.width = cv.height = SIZE + 2 * M;
    const g = cv.getContext("2d"); g.translate(M, M);
    drawPaper(g, SIZE, SIZE, seed, { rough: 2, curl: SIZE * .2, shadow: 5 });
    if (withStar) drawStar(g, SIZE * .86, SIZE * .15, SIZE * .085);
    g.fillStyle = "#35291a"; g.textAlign = "center"; g.textBaseline = "middle";
    let size = 54, lines;
    do { g.font = `700 ${size}px ${HAND}`; lines = wrapLines(g, subject, SIZE * .82, 3); size -= 3; }
    while (size > 30 && lines.some(l => g.measureText(l).width > SIZE * .82));
    const lh = size * 1.02, top = SIZE * .54 - (lines.length - 1) * lh / 2 - (sub ? lh * .35 : 0);
    lines.forEach((l, i) => g.fillText(l, SIZE / 2, top + i * lh));
    if (sub) { g.font = `700 ${Math.round(size * .78)}px ${HAND}`; g.fillStyle = "#7a2a1c"; g.fillText(sub, SIZE / 2, top + lines.length * lh + 2); }
    const out = { canvas: cv, star: [M + SIZE * .86, M + SIZE * .15], starR: SIZE * .085 };
    if (N.fontsReady) N.bitmaps.set(key, out);          // until the handwriting font has loaded, draw but do not keep
    return out;
  }

  /* Draw `bmp` onto picture quad `q` (the note's square) through a projective map, cut into small triangles. */
  function drawWarped(c, bmp, q) {
    const img = bmp.canvas, W = img.width, s = SIZE;
    const H = homography([[M, M], [M + s, M], [M + s, M + s], [M, M + s]], q);
    const pts = [];
    for (let j = 0; j <= GRID; j++) { pts.push([]); for (let i = 0; i <= GRID; i++) { const sx = i * W / GRID, sy = j * W / GRID; pts[j].push([sx, sy, apply(H, [sx, sy])]); } }
    const tri = (a, b, d) => {
      const [x0, y0, [u0, v0]] = a, [x1, y1, [u1, v1]] = b, [x2, y2, [u2, v2]] = d;
      const den = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0); if (!den) return;
      const A = ((u1 - u0) * (y2 - y0) - (u2 - u0) * (y1 - y0)) / den, C = ((u2 - u0) * (x1 - x0) - (u1 - u0) * (x2 - x0)) / den;
      const B = ((v1 - v0) * (y2 - y0) - (v2 - v0) * (y1 - y0)) / den, D = ((v2 - v0) * (x1 - x0) - (v1 - v0) * (x2 - x0)) / den;
      const mx = (u0 + u1 + u2) / 3, my = (v0 + v1 + v2) / 3, grow = 1.04;   // overlap neighbours slightly: no hairline seams
      c.save(); c.beginPath();
      [[u0, v0], [u1, v1], [u2, v2]].forEach(([u, v], k) => c[k ? "lineTo" : "moveTo"](mx + (u - mx) * grow, my + (v - my) * grow));
      c.closePath(); c.clip();
      c.transform(A, B, C, D, u0 - A * x0 - C * y0, v0 - B * x0 - D * y0);
      c.drawImage(img, 0, 0); c.restore();
    };
    for (let j = 0; j < GRID; j++) for (let i = 0; i < GRID; i++) { const p00 = pts[j][i], p10 = pts[j][i + 1], p01 = pts[j + 1][i], p11 = pts[j + 1][i + 1]; tri(p00, p10, p11); tri(p00, p11, p01); }
    return H;
  }
  /* The glint: every few seconds a small four-point sparkle flares on the star and fades. */
  function drawGlint(c, at, size, phaseSeed, now) {
    if (reduceMotion.matches) return;
    const period = 4600 + (phaseSeed % 1400), t = ((now + phaseSeed * 37) % period) / period, win = 0.13;
    if (t > win) return;
    const k = Math.sin(Math.PI * t / win), r = size * (0.55 + 0.45 * k), [x, y] = at;
    c.save(); c.globalAlpha = 0.9 * k; c.globalCompositeOperation = "lighter";
    const glow = c.createRadialGradient(x, y, 0, x, y, r * .7);
    glow.addColorStop(0, "rgba(255,248,215,.9)"); glow.addColorStop(1, "rgba(255,220,140,0)");
    c.fillStyle = glow; c.beginPath(); c.arc(x, y, r * .7, 0, Math.PI * 2); c.fill();
    c.fillStyle = "rgba(255,252,236,1)";
    for (const [dx, dy] of [[1, 0], [0, 1]]) {
      const w = r * .09;
      c.beginPath(); c.moveTo(x - dx * r, y - dy * r); c.lineTo(x + dy * w, y + dx * w); c.lineTo(x + dx * r, y + dy * r); c.lineTo(x - dy * w, y - dx * w); c.closePath(); c.fill();
    }
    c.restore();
  }

  /* ---------------------------------------------------------------- in the rooms */
  function surfacesFor(viewKey) {
    const out = [], spots = (N.file && N.file.spots) || {};
    for (const [id, spot] of Object.entries(spots)) for (const s of spot.surfaces || []) if (s.view === viewKey) out.push({ id, spot, s });
    return out;
  }
  function notesOn(spotId) { return N.notes.filter(n => n.unread && (n.spots || []).includes(spotId)).slice(0, MAX_PER_SPOT); }

  function drawScene(c, viewKey, scale) {
    N.hits = [];
    if (!N.file) return;
    const now = performance.now();
    const btn = N.file.corkboard_button;
    if (btn && btn.view === viewKey && N.enabled) {
      const q = noteQuad(btn, btn.slot, btn.note_w), sub = N.unread ? `${N.unread} new` : "";
      const bmp = noteBitmap(`menu|${N.unread}`, btn.label, 7, N.unread > 0, sub);
      const H = drawWarped(c, bmp, q);
      if (N.unread) drawGlint(c, apply(H, bmp.star), len(q[0], q[1]) * .16, 3, now);
      N.hits.push({ quad: q, open: null });
    }
    if (!N.enabled) return;
    for (const { id, s } of surfacesFor(viewKey)) {
      const list = notesOn(id);
      for (let i = list.length - 1; i >= 0; i--) {                     // newest drawn last, on top
        const n = list[i], slot = s.slots[i] || s.slots[s.slots.length - 1], q = noteQuad(s, slot, s.note_w);
        const bmp = noteBitmap(`${n.id}|note`, n.subject, seedOf(n.id), true, "");
        const H = drawWarped(c, bmp, q);
        drawGlint(c, apply(H, bmp.star), Math.max(2.2 / scale, len(q[0], q[1]) * .2), seedOf(n.id) % 997, now);
        if (s.click) N.hits.push({ quad: q, open: n.id });
      }
    }
  }
  function click(viewKey, p) {
    for (let i = N.hits.length - 1; i >= 0; i--) {
      const h = N.hits[i];
      if (inQuad(p, h.quad)) { if (h.open) openNote(h.open, true); else openMenu(); return true; }
    }
    return false;
  }
  function hotspotNotes(viewKey, hotspotId) {
    if (!N.enabled) return [];
    const ids = surfacesFor(viewKey).filter(x => x.s.hotspot === hotspotId).map(x => x.id);
    const seen = new Set(), out = [];
    for (const id of ids) for (const n of notesOn(id)) if (!seen.has(n.id)) { seen.add(n.id); out.push(n); }
    return out;
  }
  function onView(viewKey) { N.view = viewKey; refresh(); }

  /* ---------------------------------------------------------------- the overlay */
  let layer = null, lastFocus = null;
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  function btn(text, cls, fn) { const b = el("button", cls, text); b.type = "button"; b.addEventListener("click", fn); return b; }
  function ensureLayer() {
    if (layer) return layer;
    layer = el("div"); layer.id = "pnLayer"; layer.hidden = true;
    layer.setAttribute("role", "dialog"); layer.setAttribute("aria-modal", "true"); layer.setAttribute("aria-label", "Production notes");
    // Escape steps back (note or writer to the menu, menu to the room) wherever focus is while the notes are open,
    // and keys typed into a note never reach the walker (no walking while writing).
    document.addEventListener("keydown", e => {
      if (!layer || layer.hidden) return;
      if (e.key === "Escape") { e.preventDefault(); back(); }
      e.stopPropagation();
    }, true);
    layer.addEventListener("pointerdown", e => e.stopPropagation());
    (document.getElementById("stage") || document.body).appendChild(layer);
    return layer;
  }
  function show(content, focusSel) {
    const L = ensureLayer();
    if (L.hidden) lastFocus = document.activeElement;
    L.textContent = ""; L.appendChild(content); L.hidden = false;
    requestAnimationFrame(() => { paintPapers(L); const f = L.querySelector(focusSel || "button"); if (f) f.focus({ preventScroll: true }); });
  }
  function closeAll() {
    if (!layer) return; layer.hidden = true; layer.textContent = ""; N.openId = null; N.mode = null;
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }
  function back() { if (N.mode === "note" || N.mode === "compose") openMenu(); else closeAll(); }
  /* Paper behind DOM notes: the same sheet as in the rooms, drawn to each element's size. */
  function paintPapers(root) {
    root.querySelectorAll("[data-paper]").forEach(host => {
      const old = host.querySelector(":scope > canvas.pn-paper"); if (old) old.remove();
      const w = host.offsetWidth, h = host.offsetHeight; if (!w || !h) return;
      const m = Math.round(Math.min(40, w * .06)), dpr = Math.min(2, window.devicePixelRatio || 1);
      const cv = el("canvas", "pn-paper"); cv.width = (w + 2 * m) * dpr; cv.height = (h + 2 * m) * dpr;
      cv.style.left = cv.style.top = -m + "px"; cv.style.width = (w + 2 * m) + "px"; cv.style.height = (h + 2 * m) + "px";
      const g = cv.getContext("2d"); g.scale(dpr, dpr); g.translate(m, m);
      const big = w > 300;
      drawPaper(g, w, h, seedOf(host.dataset.paper), { rough: big ? 2.6 : 1.3, curl: big ? 70 : Math.min(26, h * .28), shadow: big ? 12 : 4, strip: big ? .07 : .12 });
      host.insertBefore(cv, host.firstChild);
    });
  }

  const fmtWhen = t => {
    const d = new Date(t * 1000), now = new Date(), same = (a, b) => a.toDateString() === b.toDateString();
    const y = new Date(now); y.setDate(now.getDate() - 1);
    const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    if (same(d, now)) return "Today, " + time;
    if (same(d, y)) return "Yesterday, " + time;
    return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }) + ", " + time;
  };
  const dayLabel = t => {
    const d = new Date(t * 1000), now = new Date(), y = new Date(now); y.setDate(now.getDate() - 1);
    if (d.toDateString() === now.toDateString()) return "Today";
    if (d.toDateString() === y.toDateString()) return "Yesterday";
    return d.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
  };

  async function openMenu() {
    N.mode = "menu"; N.openId = null;
    const r = await api("/api/notes?box=" + N.box);
    if (N.box === "inbox" && r.ok) { N.notes = r.data.notes; N.unread = r.data.unread; }
    const wrap = el("div", "pn-menu");
    const tabs = el("div", "pn-tabs");
    for (const [box, label] of [["inbox", "Inbox"], ["saved", "Saved"], ["sent", "Sent"]]) {
      const t = btn(label, "pn-tab", () => { N.box = box; openMenu(); }); t.setAttribute("aria-pressed", String(N.box === box)); tabs.appendChild(t);
    }
    for (const [g, label] of [["date", "By date"], ["project", "By project"]]) {
      const t = btn(label, "pn-tab", () => { N.group = g; openMenu(); }); t.setAttribute("aria-pressed", String(N.group === g)); tabs.appendChild(t);
    }
    wrap.appendChild(tabs);
    const col = el("div", "pn-col");
    if (!r.ok) col.appendChild(el("div", "pn-empty", r.text));
    else if (!r.data.notes.length) col.appendChild(el("div", "pn-empty", N.box === "inbox" ? "No notes. New ones show up on your mirror." : "Nothing here yet."));
    else {
      const groups = new Map();
      for (const n of r.data.notes) {
        const k = N.group === "project" ? (n.project || "") : dayLabel(n.created_at);
        if (!groups.has(k)) groups.set(k, []); groups.get(k).push(n);
      }
      let keys = [...groups.keys()];
      if (N.group === "project") keys = keys.filter(Boolean).sort((a, b) => a.localeCompare(b)).concat(groups.has("") ? [""] : []);
      for (const k of keys) {
        col.appendChild(el("div", "pn-group", k || "No project"));
        for (const n of groups.get(k)) {
          const card = el("button", "pn-card" + (n.unread ? " unread" : "")); card.type = "button"; card.dataset.paper = n.id;
          card.appendChild(el("h3", null, n.subject));
          const who = N.box === "sent" ? "To your crew" : n.from.display_name;
          card.appendChild(el("div", "pn-meta", [who, fmtWhen(n.created_at), n.files ? n.files + (n.files === 1 ? " attachment" : " attachments") : ""].filter(Boolean).join(" · ")));
          card.setAttribute("aria-label", (n.unread ? "Unread: " : "") + n.subject + ", from " + who);
          card.addEventListener("click", () => openNote(n.id, false));
          col.appendChild(card);
        }
      }
    }
    wrap.appendChild(col);
    const bar = el("div", "pn-bar");
    bar.appendChild(btn("New sticky note", "pn-brass primary", () => compose({})));
    bar.appendChild(btn("Close", "pn-brass", closeAll));
    const frag = document.createDocumentFragment(); frag.appendChild(wrap); frag.appendChild(bar);
    show(frag, ".pn-card, .pn-brass");
  }

  async function people() {
    if (N.people) return N.people;
    const r = await api("/api/production/people");
    if (!r.ok) return null;
    N.me = r.data.me; N.people = r.data.people; return N.people;
  }

  async function openNote(id, fromSpot) {
    const r = await api(`/api/notes/${encodeURIComponent(id)}?mark_read=1`);
    if (!r.ok) { if (fromSpot) await refresh(); return openMenu(); }
    const n = r.data; N.mode = "note"; N.openId = id;
    refresh();                                                    // read: it leaves the mirror and every spot
    const sheet = el("div", "pn-sheet"); sheet.dataset.paper = "open-" + n.id;
    sheet.setAttribute("aria-label", "Note: " + n.subject);
    const scroll = el("div", "pn-scroll"); scroll.tabIndex = 0;
    scroll.appendChild(el("h1", null, n.subject));
    const dl = el("dl", "pn-fields");
    const field = (k, v) => { if (!v) return; dl.appendChild(el("dt", null, k)); dl.appendChild(el("dd", null, v)); };
    const names = list => list.map(p => p.display_name).join(", ");
    field("From", n.from.display_name);
    field("To", names(n.to));
    field("CC", names(n.cc));
    if (n.is_sender) field("BCC", names(n.bcc));
    else if (n.you_were_bcc) field("BCC", "You");
    field("Project", n.project);
    field("Date", new Date(n.created_at * 1000).toLocaleString([], { weekday: "long", month: "long", day: "numeric", hour: "numeric", minute: "2-digit" }));
    scroll.appendChild(dl);
    scroll.appendChild(el("div", "pn-body", n.body));
    if (n.files.length) {
      const files = el("div", "pn-files");
      for (const f of n.files) files.appendChild(btn(f.name + " (" + kb(f.size) + ")", "pn-chip", () => download(f)));
      scroll.appendChild(files);
    }
    sheet.appendChild(scroll);
    const actions = el("div", "pn-actions");
    if (!n.is_sender) actions.appendChild(btn("Reply", "pn-brass primary", () => compose({ replyTo: n, all: false })));
    actions.appendChild(btn("Reply all", "pn-brass" + (n.is_sender ? " primary" : ""), () => compose({ replyTo: n, all: true })));
    if (!n.is_sender) actions.appendChild(btn(n.saved ? "Unsave" : "Save", "pn-brass", async () => { await api(`/api/notes/${n.id}/${n.saved ? "unsave" : "save"}`, { method: "POST" }); openNote(n.id, false); }));
    actions.appendChild(btn("Trash", "pn-brass", async () => { await api(`/api/notes/${n.id}/trash`, { method: "POST" }); await refresh(); openMenu(); }));
    actions.appendChild(btn("New sticky note", "pn-brass", () => compose({})));
    const bar = el("div", "pn-bar"); bar.appendChild(btn("Close", "pn-brass", () => openMenu()));
    const frag = document.createDocumentFragment(); frag.appendChild(sheet); frag.appendChild(actions); frag.appendChild(bar);
    show(frag, ".pn-actions .pn-brass");
  }
  const kb = b => b < 1024 ? b + " bytes" : b < 1048576 ? Math.round(b / 1024) + " KB" : (b / 1048576).toFixed(1) + " MB";
  async function download(f) {
    try {
      const res = await fetch(f.url, { cache: "no-store" }); if (!res.ok) throw new Error(res.status);
      const url = URL.createObjectURL(await res.blob()), a = el("a"); a.href = url; a.download = f.name;
      document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (e) { alertInLayer("That attachment could not be downloaded."); }
  }
  function alertInLayer(text) { const m = layer && layer.querySelector(".pn-msg"); if (m) m.textContent = text; }

  async function compose(o) {
    N.mode = "compose";
    const crew = await people();
    if (!crew) { alertInLayer("Your crew list could not be loaded."); return; }
    if (!N.spotCatalog) { const r = await api("/api/notes/spots"); N.spotCatalog = r.ok ? r.data.spots : [{ id: "mirror", label: "Makeup mirror", always: true }]; }
    const sel = { to: new Set(), cc: new Set(), bcc: new Set() }, spots = new Set(["mirror"]);
    const re = o.replyTo;
    if (re) {
      if (re.from.user_id !== N.me) sel.to.add(re.from.user_id);
      if (o.all) { for (const p of re.to.concat(re.cc)) if (p.user_id !== N.me) (re.is_sender ? sel.to : sel.cc).add(p.user_id); if (re.is_sender) for (const p of re.bcc) sel.bcc.add(p.user_id); }
      if (!sel.to.size && !sel.cc.size) sel.to.add(N.me);
    }
    const sheet = el("div", "pn-sheet"); sheet.dataset.paper = "compose";
    const form = el("form", "pn-form pn-scroll"); form.noValidate = true;
    const picker = (kind, label) => {
      const lab = el("div", "pn-row"); lab.appendChild(el("span", null, label));
      const box = el("div", "pn-picks");
      const make = (id, name) => {
        const b = btn(name, "pn-pick", () => { const on = !sel[kind].has(id); if (on) { sel[kind].add(id); for (const k of ["to", "cc", "bcc"]) if (k !== kind) sel[k].delete(id); } else sel[kind].delete(id); syncPicks(); });
        b.dataset.kind = kind; b.dataset.id = id; box.appendChild(b);
      };
      make("@production", "Everyone");
      for (const p of crew) make(p.user_id, p.user_id === N.me ? "Me" : p.display_name);
      lab.appendChild(box); return lab;
    };
    const syncPicks = () => form.querySelectorAll(".pn-pick[data-kind]").forEach(b => b.setAttribute("aria-pressed", String(sel[b.dataset.kind].has(b.dataset.id))));
    form.appendChild(picker("to", "To"));
    form.appendChild(picker("cc", "CC"));
    form.appendChild(picker("bcc", "BCC"));
    const subj = el("input", "pn-subject"); subj.type = "text"; subj.maxLength = 120; subj.required = true;
    subj.value = re ? (/^re:/i.test(re.subject) ? re.subject : "Re: " + re.subject).slice(0, 120) : "";
    const lsub = el("label", null, "Subject: this is what is written on the sticky note"); lsub.appendChild(subj); form.appendChild(lsub);
    const proj = el("input"); proj.type = "text"; proj.maxLength = 60; proj.value = re ? (re.project || "") : "";
    const dl = el("datalist"); dl.id = "pnProjects"; proj.setAttribute("list", "pnProjects");
    for (const p of [...new Set(N.notes.map(n => n.project).filter(Boolean))]) { const op = el("option"); op.value = p; dl.appendChild(op); }
    const lproj = el("label", null, "Project (optional)"); lproj.appendChild(proj); lproj.appendChild(dl); form.appendChild(lproj);
    const body = el("textarea"); body.maxLength = 20000;
    if (re) body.value = "\n\n" + "On " + new Date(re.created_at * 1000).toLocaleString() + ", " + re.from.display_name + " wrote:\n" + re.body.split("\n").map(l => "> " + l).join("\n");
    const lbody = el("label", null, "Message"); lbody.appendChild(body); form.appendChild(lbody);
    const spotRow = el("div", "pn-row"); spotRow.appendChild(el("span", null, "Stick it to"));
    const spotBox = el("div", "pn-picks");
    for (const s of N.spotCatalog) {
      const b = btn(s.label, "pn-pick", () => { if (s.always) return; spots.has(s.id) ? spots.delete(s.id) : spots.add(s.id); b.setAttribute("aria-pressed", String(spots.has(s.id))); });
      b.setAttribute("aria-pressed", String(spots.has(s.id))); if (s.always) { b.disabled = true; b.title = "Every note goes on the mirror"; }
      spotBox.appendChild(b);
    }
    spotRow.appendChild(spotBox); form.appendChild(spotRow);
    const files = el("input"); files.type = "file"; files.multiple = true;
    const lfiles = el("label", null, "Attachments (up to 8, 10 MB each)"); lfiles.appendChild(files); form.appendChild(lfiles);
    const emailRow = el("label", "pn-row"); const emailBox = el("input"); emailBox.type = "checkbox";
    emailRow.appendChild(emailBox); emailRow.appendChild(el("span", null, "Also send as email from my own email program"));
    form.appendChild(emailRow);
    const msg = el("div", "pn-msg"); msg.setAttribute("role", "status"); form.appendChild(msg);
    sheet.appendChild(form);
    syncPicks();

    const actions = el("div", "pn-actions");
    const sendBtn = btn("Stick it", "pn-brass primary", async () => {
      msg.className = "pn-msg"; msg.textContent = "";
      const note = { subject: subj.value, project: proj.value, body: body.value, spots: [...spots], to: [...sel.to], cc: [...sel.cc], bcc: [...sel.bcc] };
      if (re) note.reply_to = re.id;
      if (!note.subject.trim()) { msg.textContent = "Write a subject: it is what shows on the sticky note."; subj.focus(); return; }
      if (!note.to.length && !note.cc.length && !note.bcc.length) { msg.textContent = "Choose who the note is for."; return; }
      sendBtn.disabled = true; sendBtn.textContent = "Sticking…";
      let r;
      if (files.files.length) {
        const fd = new FormData(); fd.append("note", JSON.stringify(note)); for (const f of files.files) fd.append("files", f, f.name);
        r = await api("/api/notes", { method: "POST", body: fd });
      } else r = await api("/api/notes", json(note));
      sendBtn.disabled = false; sendBtn.textContent = "Stick it";
      if (!r.ok) { msg.textContent = r.text; return; }
      await refresh();
      if (!emailBox.checked) return openMenu();
      const link = mailto(note, crew);
      msg.className = "pn-msg ok"; msg.textContent = "Stuck. " + (link.missing.length ? "No email address available to you for " + link.missing.join(", ") + ". " : "");
      if (link.href) {
        const a = el("a", "pn-mail", "Open the email copy in my email program"); a.href = link.href; msg.appendChild(el("br")); msg.appendChild(a);
        if (files.files.length) msg.appendChild(el("div", null, "Attach the files in your email program; an email link cannot carry them."));
      }
      actions.textContent = ""; actions.appendChild(btn("Back to notes", "pn-brass primary", () => openMenu()));
    });
    actions.appendChild(sendBtn);
    actions.appendChild(btn("Cancel", "pn-brass", () => (N.openId && re ? openNote(re.id, false) : openMenu())));
    const frag = document.createDocumentFragment(); frag.appendChild(sheet); frag.appendChild(actions);
    show(frag, re ? "textarea" : ".pn-pick");
    if (re) setTimeout(() => { body.focus(); body.setSelectionRange(0, 0); }, 30);
  }
  function mailto(note, crew) {
    const byId = new Map(crew.map(p => [p.user_id, p])), missing = [];
    const addr = ids => {
      const out = [];
      for (const id of ids) for (const p of (id === "@production" ? crew.filter(x => x.user_id !== N.me) : [byId.get(id)])) {
        if (!p) continue; if (p.email) out.push(p.email); else missing.push(p.display_name);
      }
      return [...new Set(out)];
    };
    const to = addr(note.to), cc = addr(note.cc), bcc = addr(note.bcc);
    if (!to.length && !cc.length && !bcc.length) return { href: "", missing };
    const q = [];
    if (cc.length) q.push("cc=" + encodeURIComponent(cc.join(",")));
    if (bcc.length) q.push("bcc=" + encodeURIComponent(bcc.join(",")));
    q.push("subject=" + encodeURIComponent(note.subject));
    if (note.body) q.push("body=" + encodeURIComponent(note.body));
    return { href: "mailto:" + to.map(encodeURIComponent).join(",") + "?" + q.join("&"), missing };
  }

  /* ---------------------------------------------------------------- start */
  function openMenuPublic() { return openMenu(); }
  document.fonts && document.fonts.load(`700 40px ${HAND}`).then(() => { N.fontsReady = true; N.bitmaps.clear(); }, () => { N.fontsReady = true; });
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, POLL_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });

  window.PubCastNotes = { drawScene, click, hotspotNotes, onView, refresh, open: openMenuPublic, openNote, state: N,
    _noteQuad: noteQuad, _homography: homography };
})();
