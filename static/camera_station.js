/* The camera operator station on the Control page: aim, move, zoom and pull focus on a real camera, record the move, save it,
 * and play it back exactly.
 *
 * It adds a "Camera" tab to the stations bar. While the tab is open the key map is at the camera station (so its held keys
 * drive the rig, and nothing else), and the pose the rig produces is sent to the camera through /api/switcher/ptz. Recording
 * keeps the pose that resulted; saved moves live on the host per person (/api/camera-moves). Playback drives the camera from
 * a saved move and ignores the operator's keys until it ends or is stopped.
 */
(function (global) {
  "use strict";
  const doc = global.document, CK = global.PubCastControlKeys, R = global.PubCastCameraRig;
  if (!doc || !CK || !R) return;
  const bar = doc.getElementById("stations-bar");
  if (!bar) return;
  const D = R.DEG;

  // ---- the tab and the panel ----
  const tab = doc.createElement("button");
  tab.className = "ghost"; tab.dataset.station = "camera"; tab.textContent = "Camera"; bar.appendChild(tab);
  const panel = doc.createElement("div");
  panel.id = "station-camera"; panel.className = "hidden";
  panel.innerHTML = `<div class="panel"><h3>Camera operator</h3>
    <div class="row" style="gap:8px;align-items:center;flex-wrap:wrap">
      <label class="muted small">Camera <select id="cs-camera"></select></label>
      <label class="muted small">Aim with <select id="cs-mode"><option value="keys">Keys</option><option value="mouse">Mouse (click the grey box)</option></select></label>
      <button id="cs-record" class="ghost">Record</button>
      <input id="cs-name" placeholder="Name this move" maxlength="60" style="width:150px">
      <button id="cs-save" class="ghost">Save move</button>
      <select id="cs-moves"></select>
      <button id="cs-play" class="ghost">Play</button><button id="cs-stop" class="ghost">Stop</button><button id="cs-delete" class="ghost">Delete</button>
    </div>
    <div id="cs-mouse" tabindex="0" style="display:none;margin:8px 0;height:70px;border:1px dashed #889;border-radius:8px;background:#1a2036;color:#9fb3d8;text-align:center;line-height:70px">Click to capture the mouse: move to aim, wheel to zoom, Shift + wheel to pull focus, Esc to let go</div>
    <pre id="cs-hud" class="muted small" style="margin:8px 0"></pre>
    <div id="cs-status" class="muted small" role="status"></div>
    <h4>Keys</h4><div id="cs-keys" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:4px"></div></div>`;
  const after = doc.getElementById("station-director") || bar;
  after.parentNode.insertBefore(panel, after.nextSibling);
  const $ = id => doc.getElementById(id);

  // ---- state ----
  let rig = null, cameraId = "", active = false, raf = 0, last = 0, lastSent = null, sentAt = 0, inflight = false;
  let recording = null, playing = null, status = "";
  const mouse = { dx: 0, dy: 0, wheel: 0, shift: false };
  const say = t => { status = t; $("cs-status").textContent = t; };

  const toApi = p => ({ position: [p.x, p.y, p.z], rotation: [p.tilt / D, p.pan / D, p.roll / D], fov: p.fov / D, focus: p.focus });
  const fromApi = j => R.newPose({ x: j.position[0], y: j.position[1], z: j.position[2], tilt: j.rotation[0] * D, pan: ((j.rotation[1] * D) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI),
                                   roll: j.rotation[2] * D, fov: j.fov * D, focus: j.focus || 5 });

  async function loadCamera() {
    if (!cameraId) return;
    try {
      const r = await fetch("/api/switcher/pose/" + encodeURIComponent(cameraId), { cache: "no-store" });
      if (!r.ok) { say("Could not read that camera"); return; }
      rig = R.create(fromApi(await r.json())); lastSent = JSON.stringify(toApi(rig.pose)); say("");
    } catch (e) { say("The host is not reachable"); }
  }
  async function loadCameras() {
    try {
      const j = await (await fetch("/api/switcher/state", { cache: "no-store" })).json();
      const sel = $("cs-camera"), keep = cameraId || sel.value; sel.textContent = "";
      for (const s of j.sources || []) sel.appendChild(new Option(s.name || s.id, s.id));
      if ([...sel.options].some(o => o.value === keep)) sel.value = keep;
      cameraId = sel.value;
    } catch (e) { say("The host is not reachable"); }
  }
  async function loadMoves() {
    try {
      const j = await (await fetch("/api/camera-moves", { cache: "no-store" })).json();
      const sel = $("cs-moves"); sel.textContent = "";
      for (const m of j.moves || []) sel.appendChild(new Option(`${m.name} (${m.seconds}s)`, m.name));
    } catch (e) { /* none listed */ }
  }
  function keysTable() {
    const box = $("cs-keys"), b = CK.km.bindings("camera"); box.textContent = "";
    for (const a of R.ACTIONS) {
      const row = doc.createElement("div"), name = doc.createElement("span"), key = doc.createElement("button");
      row.style.cssText = "display:flex;justify-content:space-between;gap:6px;align-items:center"; name.textContent = a[1];
      key.type = "button"; key.className = "ghost"; key.textContent = CK.label(b[a[0]]); key.title = "Set key";
      key.dataset.keyStation = "camera"; key.dataset.keyAction = a[0];
      key.addEventListener("click", () => { CK.km.open("camera"); const q = CK.km.ask("camera", a[0]); say(q); });
      row.append(name, key); box.appendChild(row);
    }
  }

  // ---- sending the pose ----
  function send(force) {
    if (!rig || inflight || !cameraId) return;
    const body = toApi(rig.pose), text = JSON.stringify(body), now = performance.now();
    if (text === lastSent || (!force && now - sentAt < 50)) return;
    inflight = true; sentAt = now;
    fetch("/api/switcher/ptz/" + encodeURIComponent(cameraId), { method: "POST", headers: { "Content-Type": "application/json" }, body: text })
      .then(r => { if (r.ok) { lastSent = text; if (status.startsWith("Could not")) say(""); } else say(r.status === 403 ? "You need the moderator role to move a camera" : "Could not move the camera (" + r.status + ")"); })
      .catch(() => say("Could not reach the camera")).finally(() => { inflight = false; });
  }

  // ---- the loop, running only while the tab is open ----
  function frame(now) {
    if (!active) return;
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    if (rig) {
      if (playing) {
        const p = R.playback(playing.rec, playing.t); playing.t += dt;
        if (p) rig.setPose(p);
        if (rig.isRecording()) rig.step(dt, null);
        if (playing.t >= playing.rec.samples.length / playing.rec.rate) { playing = null; say("Move finished"); }
      } else {
        const held = CK.km.held("camera");
        const w = $("cs-mode").value === "mouse" && (doc.pointerLockElement || mouse.dx || mouse.dy || mouse.wheel)
          ? Object.assign(R.fromActions(rig.pose, held.filter(a => /^move_/.test(a))), R.fromMouse(rig.pose, new Set(), mouse, dt))
          : R.fromActions(rig.pose, held);
        if ($("cs-mode").value === "mouse") { const m = R.fromMouse(rig.pose, new Set(), mouse, dt); Object.assign(w, { pan: m.pan, tilt: m.tilt, fov: m.fov !== undefined ? m.fov : w.fov, focus: m.focus !== undefined ? m.focus : w.focus }); }
        mouse.dx = mouse.dy = mouse.wheel = 0; rig.step(dt, w);
      }
      send(false); hud();
    }
    raf = requestAnimationFrame(frame);
  }
  function hud() {
    const p = rig.pose, f = n => n.toFixed(2);
    $("cs-hud").textContent = `position ${f(p.x)} ${f(p.y)} ${f(p.z)}   pan ${f(p.pan / D)}  tilt ${f(p.tilt / D)}  roll ${f(p.roll / D)}   lens ${f(R.fovToFocal(p.fov))} mm   focus ${f(p.focus)} m` +
      (playing ? "\nPLAYING" : rig.isRecording() ? "\nRECORDING" : recording ? "\nunsaved move: name it and Save" : "");
  }

  function open() {
    if (active) return; active = true; CK.km.open("camera");
    loadCameras().then(loadCamera); loadMoves(); keysTable(); last = performance.now(); raf = requestAnimationFrame(frame);
  }
  function close() {
    if (!active) return; active = false; cancelAnimationFrame(raf);
    if (rig && rig.isRecording()) recording = rig.stopRecording();
    playing = null; CK.km.open("switcher"); if (doc.pointerLockElement) doc.exitPointerLock();
  }
  bar.addEventListener("click", e => {                                // control_stations.js has already switched the panels
    const b = e.target.closest("[data-station]"); if (!b) return;
    if (b.dataset.station === "camera") open(); else close();
  });
  CK.km.onChange(() => { if (active) keysTable(); });

  // ---- buttons ----
  $("cs-camera").addEventListener("change", e => { cameraId = e.target.value; playing = null; loadCamera(); });
  $("cs-mode").addEventListener("change", e => { $("cs-mouse").style.display = e.target.value === "mouse" ? "block" : "none"; });
  $("cs-mouse").addEventListener("click", () => { if ($("cs-mouse").requestPointerLock) $("cs-mouse").requestPointerLock(); });
  doc.addEventListener("mousemove", e => { if (active && doc.pointerLockElement) { mouse.dx += e.movementX; mouse.dy += e.movementY; } });
  doc.addEventListener("wheel", e => { if (active && doc.pointerLockElement) { mouse.wheel += Math.sign(-e.deltaY); mouse.shift = e.shiftKey; e.preventDefault(); } }, { passive: false });
  $("cs-record").addEventListener("click", () => {
    if (!rig) return;
    if (rig.isRecording()) { recording = rig.stopRecording(); recording.camera = cameraId; $("cs-record").textContent = "Record"; say("Recorded " + (recording.samples.length / recording.rate).toFixed(1) + " s: name it and Save"); }
    else { playing = null; recording = null; rig.startRecording(30); $("cs-record").textContent = "Stop recording"; say("Recording"); }
  });
  $("cs-save").addEventListener("click", async () => {
    const name = $("cs-name").value.trim();
    if (!recording) return say("Record a move first");
    if (!name) return say("Give the move a name");
    recording.camera = cameraId;
    try {
      const r = await fetch("/api/camera-moves/" + encodeURIComponent(name), { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(recording) });
      if (r.ok) { say("Saved " + name); recording = null; loadMoves(); } else say("Could not save: " + ((await r.json().catch(() => ({}))).detail || r.status));
    } catch (e) { say("Could not reach the host"); }
  });
  $("cs-play").addEventListener("click", async () => {
    const name = $("cs-moves").value; if (!name || !rig) return;
    try {
      const r = await fetch("/api/camera-moves/" + encodeURIComponent(name), { cache: "no-store" });
      if (!r.ok) return say("Could not load that move");
      const rec = await r.json(); rig.setPose(rec.start); playing = { rec, t: 0 }; say("Playing " + name);
    } catch (e) { say("Could not reach the host"); }
  });
  $("cs-stop").addEventListener("click", () => { playing = null; say("Stopped"); });
  $("cs-delete").addEventListener("click", async () => {
    const name = $("cs-moves").value; if (!name) return;
    try { const r = await fetch("/api/camera-moves/" + encodeURIComponent(name), { method: "DELETE" }); say(r.ok ? "Deleted " + name : "Could not delete"); loadMoves(); } catch (e) { say("Could not reach the host"); }
  });
  global.PubCastCameraStation = { open, close, rig: () => rig, state: () => ({ active, cameraId, playing: !!playing, recording: !!(rig && rig.isRecording()), unsaved: !!recording }) };
})(window);
