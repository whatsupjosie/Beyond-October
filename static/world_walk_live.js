/* PubCast world walk: the live link to the running Reach host.
 *
 * The walkable world (static/world_walk.html) draws and walks the rooms on its own. This file connects it to the same
 * backend the classic PubWorld page (static/world.html) uses, with the same protocol, so both pages are one world:
 *
 *   - presence   room_change over /pubworld/ws/{client_id}, using each room's live id (the id world.html, the room audio
 *                runtime and the backend already know). While the socket is down the room is held and sent on reconnect.
 *                It also raises the page event "pubcast:room" that static/program_audio_runtime.js listens to, so room
 *                audio rules (the dressing room only lets director announcements through) follow the walker too.
 *   - hotspots   a world hotspot that matches a backend action (typewriter, scripts, phone, wardrobe, makeup, message board,
 *                TV, sitting) calls POST /pubworld/api/hotspot exactly as world.html does, and the result is described as a
 *                title, lines and follow-up choices for the walker to show.
 *   - on air     the production state the backend pushes (welcome / production_state) is kept and announced.
 *
 * Auth follows world.html: when a Reach session exists its token is sent as the first socket message; an auth_error
 * clears the session and sends you to the login page, which returns here.
 * Nothing in this file draws anything. The walker listens for "pubcast:live-status" and calls PubCastLive.actionFor/use.
 */
(function (global) {
  "use strict";

  const PING_MS = 25000, RECONNECT_MS = 4000, CONNECT_DELAY_MS = 600;
  const LOGIN_RETURN = "/walk";

  /* World hotspot id -> backend action (modules/pubworld_hotspots.py ACTION_HANDLERS). Ids not listed here, and close-up
     views, stay local to the walker. Sitting is matched by name so every couch, booth and stool spot is covered. */
  const ACTION_BY_ID = {
    "typewriter": "typewriter",
    "scripts": "scripts",
    "phone": "phone",
    "wardrobe": "wardrobe",
    "makeup-station": "makeup",
    "message-board": "message_board",
    "tv": "tv",
  };
  const SIT_RE = /(^|-)(sit|couch)(-|$)/;

  function actionFor(hotspot) {
    if (!hotspot || typeof hotspot.id !== "string") return null;
    if (Object.prototype.hasOwnProperty.call(ACTION_BY_ID, hotspot.id)) return ACTION_BY_ID[hotspot.id];
    const a = hotspot.action || {};
    if (a.type === "view") return null;                       // "sit down" at the typewriter is a change of picture
    return SIT_RE.test(hotspot.id) ? "sit" : null;
  }

  const clientId = "pw_" + Math.random().toString(36).slice(2, 10);
  const state = {
    clientId, host: null, online: false, ready: false, onAir: null,
    room: "", worldRoom: "", view: "", lastResult: null, lastError: "",
  };
  let ws = null, reconnectTimer = null, pingTimer = null, stopped = false;

  function auth() { return global.ReachAuth || null; }
  function token() { try { const a = auth(); return (a && a.getToken && a.getToken()) || ""; } catch (e) { return ""; } }
  function actorId() {
    try {
      const a = auth(), info = (a && a.getUser && a.getUser()) || {};
      return String(info.user_id || info.username || clientId);
    } catch (e) { return clientId; }
  }
  function announce() {
    global.dispatchEvent(new CustomEvent("pubcast:live-status", { detail: Object.assign({}, state) }));
  }
  function setOnline(on) {
    if (state.online === on && state.ready === on) return;
    state.online = on; state.ready = on; announce();
  }

  function send(obj) {
    if (state.ready && ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send(JSON.stringify(obj)); return true; } catch (e) { return false; }
    }
    return false;
  }

  function post(path, body) {
    return fetch(path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ client_id: actorId() }, body)),
    });
  }

  function markReady() {
    if (state.ready) return;
    setOnline(true);
    if (state.room) send({ type: "room_change", room: state.room, view: state.view, world_room: state.worldRoom });
  }

  function onMessage(msg) {
    if (!msg || typeof msg !== "object") return;
    switch (msg.type) {
      case "auth_ok": markReady(); break;
      case "auth_error": {
        setOnline(false); stopped = true;
        const a = auth();
        try { if (a && a.clearSession) a.clearSession(); } catch (e) { /* nothing to clear */ }
        try { if (a && a.redirectToLogin) a.redirectToLogin(LOGIN_RETURN); } catch (e) { /* stay on the page, offline */ }
        break;
      }
      case "welcome":
        markReady();
        if (msg.payload && msg.payload.production_state) applyProduction(msg.payload.production_state);
        break;
      case "production_state": if (msg.payload) applyProduction(msg.payload); break;
      // The host acting on this person (modules/host_control.py): a notice and control of the avatar (possession), where to
      // walk while it is in control, the disciplinary waiting room (timeout), and the end of each. The walker listens for
      // "pubcast:host" and decides what to show; this file only passes them on.
      case "host_notice": case "host_drive": case "host_release": case "host_teleport": case "host_timeout_end":
        global.dispatchEvent(new CustomEvent("pubcast:host", { detail: msg })); break;
      // Removed by the host (boot or ban): do not reconnect; the walker shows the reason the host gave.
      case "banned": stopped = true; clearTimeout(reconnectTimer); setOnline(false); global.dispatchEvent(new CustomEvent("pubcast:host", { detail: msg })); break;
      // The host measures the round trip to this page by sending an id and timing the answer (shown on the host's roster).
      case "rtt_ping": send({ type: "rtt_pong", id: msg.id }); break;
      default: break;                                         // pong, room_ack, hotspot_result: nothing to do
    }
  }

  function applyProduction(p) {
    if (p && typeof p.on_air === "boolean" && p.on_air !== state.onAir) { state.onAir = p.on_air; announce(); }
  }

  function connect() {
    clearTimeout(reconnectTimer);
    if (stopped || typeof WebSocket === "undefined") return;
    const proto = global.location.protocol === "https:" ? "wss:" : "ws:";
    try { ws = new WebSocket(`${proto}//${global.location.host}/pubworld/ws/${clientId}`); }
    catch (e) { schedule(); return; }
    ws.onopen = () => {
      state.ready = false;
      const t = token();
      if (t) ws.send(JSON.stringify({ type: "auth", token: t }));
      else markReady();
    };
    ws.onmessage = ev => { try { onMessage(JSON.parse(ev.data)); } catch (e) { /* not JSON: ignore */ } };
    ws.onclose = () => { setOnline(false); schedule(); };
    ws.onerror = () => { state.lastError = "socket error"; };
  }
  function schedule() { if (!stopped) reconnectTimer = setTimeout(connect, RECONNECT_MS); }

  /* The walker calls this after every change of picture. `liveId` is the id the rest of PubCast uses for that room. */
  function enterView(detail) {
    const room = String((detail && (detail.liveId || detail.layoutId || detail.room)) || "");
    const changedRoom = room !== state.room;
    state.room = room; state.worldRoom = String(detail.room || ""); state.view = String(detail.view || "");
    if (changedRoom) global.dispatchEvent(new CustomEvent("pubcast:room", { detail: { room } }));
    if (!room) return;
    // Room changes exist only as a socket message (there is no REST route for them). While the socket is down the room
    // is kept in `state` and sent the moment the socket is ready again (markReady).
    send({ type: "room_change", room, view: state.view, world_room: state.worldRoom });
    announce();
  }

  function session() {
    let user = {};
    try { user = JSON.parse(global.sessionStorage.getItem("pubcast_user") || "null") || {}; } catch (e) { user = {}; }
    let sessionId = "default", projectId = "default";
    try { sessionId = global.sessionStorage.getItem("pubcastSessionId") || "default"; } catch (e) { /* default */ }
    try { projectId = global.localStorage.getItem("pubcastProjectId") || "default"; } catch (e) { /* default */ }
    return { session_id: sessionId, project_id: projectId, display_name: user.display_name || user.name || actorId() };
  }

  /* Run a backend action for a hotspot (or by name, for follow-up choices). Resolves to {status, result} like world.html. */
  async function call(action, data) {
    if (state.host === false) return OFFLINE;
    const body = { room: state.room, action, data: Object.assign({}, data || {}) };
    send(Object.assign({ type: "hotspot" }, body));
    try {
      const res = await post("/pubworld/api/hotspot", body);
      // a page served without the host (a plain file server) answers 404 or HTML, not the hotspot API
      if (res.status === 404 || res.status === 405 || !/json/i.test(res.headers.get("content-type") || "")) {
        state.lastResult = { action, out: OFFLINE }; return OFFLINE;
      }
      const out = await res.json().catch(() => ({ status: "error", message: "The host sent back something that is not JSON" }));
      if (!res.ok && out.status === undefined) out.status = "error";
      state.lastResult = { action, out }; return out;
    } catch (e) {
      state.lastError = String((e && e.message) || e);
      return OFFLINE;
    }
  }
  function use(hotspot, extra) {
    const action = actionFor(hotspot);
    if (!action) return Promise.resolve({ status: "local" });
    const data = Object.assign({}, extra || {});
    if (action === "sit") data.location = data.location || String(hotspot.label || "seat").replace(/^sit\s*\(?|\)?$/gi, "").trim() || "seat";
    if (action === "phone") Object.assign(data, session());
    return call(action, data);
  }

  const OFFLINE = { status: "offline", message: "The PubCast host is not running behind this page, so this can't be used here. Walking still works." };
  const pretty = s => String(s || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  const TV = { off: "Off", stage_feed: "Stage feed", crew_chatter: "Crew chatter", uploaded_dailies: "Uploaded dailies", previs: "Previs",
               teaser_trailer: "Teaser trailer", pitch_presentation: "Pitch presentation", director_inspiration: "Director inspiration",
               my_media: "My media", my_music: "My music", pubcast_ai_channel: "PubCast AI channel" };

  /* Turn a backend reply into what the walker shows: {title, lines, choices:[{label, action, data}]}. */
  function describe(action, out) {
    if (!out || out.status === "offline") return { title: "Not connected", lines: [(out && out.message) || "PubCast is not reachable from this page right now."], choices: [] };
    if (out.status && out.status !== "ok") return { title: "That did not work", lines: [out.message || ("The host answered: " + out.status)], choices: [] };
    const r = out.result || {};
    switch (action) {
      case "typewriter": return { title: "Typewriter", lines: ["Script draft " + (r.draft_id || "new") + ", " + (r.line_count || 0) + " lines so far."],
                                  choices: [{ label: "My scripts", action: "scripts" }] };
      case "scripts": return { title: "Scripts", lines: (r.scripts && r.scripts.length) ? r.scripts : ["No scripts yet."], choices: [] };
      case "phone": {
        const lines = ["Session " + (r.session_token || "-") + (r.call_handle ? ", your handle " + r.call_handle : "") + "."];
        for (const c of (r.contacts || [])) lines.push((c.credit_name || c.display_name || "Contact") + ": " + (((c.session_role || []).join(", ")) || "session contact") + ", " + (c.availability || "available"));
        if (!(r.contacts || []).length) lines.push("No connected dressing rooms yet.");
        return { title: "Phone", lines, choices: [] };
      }
      case "wardrobe": return { title: "Wardrobe", lines: ["Wearing: " + pretty(r.current || "default_outfit") + "."],
                                choices: (r.wardrobe_items || []).map(i => ({ label: pretty(i), action: "wardrobe", data: { current: i } })) };
      case "makeup": return { title: "Hair and makeup", lines: ["Current look: " + pretty(r.current || "natural") + "."],
                              choices: (r.styles || []).map(s => ({ label: pretty(s), action: "makeup", data: { current: s } })) };
      case "message_board": return { title: "Message board", lines: (r.messages && r.messages.length) ? r.messages.map(m => (m.from || "Someone") + ": " + (m.text || "")) : ["No messages."], choices: [] };
      case "tv": return { title: "TV", lines: ["Channel: " + (TV[r.channel] || pretty(r.channel || "off")) + "."], choices: [{ label: "Flip channel", action: "tv" }] };
      case "sit": return { title: "Take a seat", lines: ["You settle into the " + (r.location || "seat") + "."], choices: [] };
      default: return { title: pretty(action), lines: [JSON.stringify(r)], choices: [] };
    }
  }

  /* Is the PubCast host behind this page? /walk and /world-walk exist only on the host. Anywhere else (the page opened
     from a plain file server) ask /health once. Without a host nothing live is started: no socket, no room-audio polling,
     so the page stays quiet and walking works as before. */
  async function detectHost() {
    if (/^\/(walk|world-walk)\/?$/.test(global.location.pathname)) return true;
    try {
      const r = await fetch("/health", { cache: "no-store" });
      if (!r.ok || !/json/i.test(r.headers.get("content-type") || "")) return false;
      const j = await r.json();
      return !!j && j.status === "ok";
    } catch (e) { return false; }
  }
  /* The room audio runtime is the host's: load it only with a host, then tell it where the walker already is. */
  function loadAudioRuntime() {
    if (global.PubcastProgramAudio || global.document.querySelector('script[data-walk-audio]')) return;
    const sc = global.document.createElement("script");
    sc.src = "/static/program_audio_runtime.js"; sc.dataset.walkAudio = "1";
    sc.onload = () => { if (state.room) global.dispatchEvent(new CustomEvent("pubcast:room", { detail: { room: state.room } })); };
    global.document.head.appendChild(sc);
  }
  /* What the host's roster shows about this walker: where it is, who it walks as, how smoothly the page runs, and how heavy
     its avatar is. The page hands in a function that returns that snapshot; it is sent every PRESENCE_MS while the socket is
     ready (the host forgets a walker that is silent for 15 s, so a closed page leaves the roster by itself). */
  const PRESENCE_MS = 2000;
  let presenceFn = null, presenceTimer = null;
  function setPresence(fn) { presenceFn = typeof fn === "function" ? fn : null; sendPresence(); }
  function sendPresence() {
    if (!presenceFn || !state.ready) return false;
    let p = null;
    try { p = presenceFn(); } catch (e) { p = null; }
    return p && typeof p === "object" ? send(Object.assign({}, p, { type: "presence" })) : false;
  }

  let starting = null;
  /* Resolves to whether the host is there; starts the live link once (safe to call any number of times). */
  function start() {
    if (!starting) starting = (async () => {
      state.host = await detectHost();
      announce();
      if (!state.host) return false;
      loadAudioRuntime();
      setTimeout(connect, CONNECT_DELAY_MS);
      pingTimer = setInterval(() => send({ type: "ping" }), PING_MS);
      presenceTimer = setInterval(sendPresence, PRESENCE_MS);
      return true;
    })();
    return starting;
  }
  function stop() { stopped = true; clearInterval(pingTimer); pingTimer = null; clearInterval(presenceTimer); presenceTimer = null; clearTimeout(reconnectTimer); try { if (ws) ws.close(); } catch (e) { /* closed */ } setOnline(false); }

  /* ---- Bella Faux Pas progress on the host (modules/studio_progress.py): one record per signed-in owner ---- */
  const PROGRESS_URL = "/api/studio/progress";
  const saving = { pending: null, timer: null, lastSent: "", inflight: null };
  state.progressRevision = 0; state.progressSavedAt = null;
  async function loadProgress() {
    if (!(await start())) return null;
    try {
      const r = await fetch(PROGRESS_URL, { cache: "no-store" });
      if (!r.ok || !/json/i.test(r.headers.get("content-type") || "")) return null;
      const j = await r.json();
      state.progressRevision = j.revision || 0; state.progressSavedAt = j.saved_at || null;
      saving.lastSent = JSON.stringify(j.progress || null);
      return j.progress || null;
    } catch (e) { return null; }
  }
  async function flushProgress(keepalive) {
    const p = saving.pending; if (!p || state.host !== true) return false;
    saving.pending = null; clearTimeout(saving.timer);
    const body = JSON.stringify(p);
    try {
      const r = await fetch(PROGRESS_URL, { method: "PUT", headers: { "Content-Type": "application/json" },
                                            body: JSON.stringify({ progress: p }), keepalive: !!keepalive });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const j = await r.json();
      saving.lastSent = body; state.progressRevision = j.revision; state.progressSavedAt = j.saved_at; announce();
      return true;
    } catch (e) {
      state.lastError = "Could not save studio progress (" + ((e && e.message) || e) + "); it will try again";
      if (!saving.pending) { saving.pending = p; saving.timer = setTimeout(() => flushProgress(false), 5000); }
      announce();
      return false;
    }
  }
  /* Ask for `p` (the walker's whole progress snapshot) to be kept. Unchanged snapshots cost nothing; changes are
     grouped and sent a moment later, or straight away with now=true (used when the page is closing). */
  function saveProgress(p, now) {
    if (state.host !== true || !p) return;
    const body = JSON.stringify(p);
    if (body === saving.lastSent && !saving.pending) return;
    saving.pending = p; clearTimeout(saving.timer);
    if (now) flushProgress(true);
    else saving.timer = setTimeout(() => flushProgress(false), 900);
  }
  /* Your avatars in the avatar library (modules/avatar_imports.py), each already at its canonical height. */
  async function avatarLibrary() {
    if (!(await start())) return [];
    try {
      const r = await fetch("/api/avatars/imports", { cache: "no-store" });
      if (!r.ok) return [];
      const j = await r.json();
      return Array.isArray(j.avatars) ? j.avatars.filter(a => a && a.id && a.url) : [];
    } catch (e) { return []; }
  }

  global.PubCastLive = { state, actionFor, use, call, describe, enterView, start, stop, ACTION_BY_ID,
                         loadProgress, saveProgress, flushProgress, avatarLibrary, setPresence, sendPresence };
  start();
})(window);
