/* The key assignments for the Control page, in one place.
 *
 * Builds the shared key map (static/keymap.js) with the video switcher's controls and the camera station's, attaches it to the
 * page, keeps the person's choices on the host (/api/keymap), and adds "Assign keys": click it, then click any switcher control
 * (or a camera control's "Set key") and it asks "Where would you like the Cut button?"; the next key pressed is the answer, shown
 * on the transparent keyboard. The controls themselves are fixed; only their keys change.
 *
 * Other scripts use window.PubCastControlKeys:  onAction(station, action, fn),  label(code),  km,  open(station).
 * Where this script is not loaded, switcher.js and control_stations.js keep their own built-in keys.
 */
(function (global) {
  "use strict";
  const KM = global.PubCastKeymap, R = global.PubCastCameraRig;
  if (!KM || !global.document) return;
  const doc = global.document;

  const spec = { switcher: { cut: { label: "Cut", key: "Space" }, fade: { label: "Fade", key: "KeyF" } }, camera: R ? R.keymapSpec() : {} };
  for (let n = 1; n <= 9; n++) {
    spec.switcher["preview_" + n] = { label: "Preview camera " + n, key: "Digit" + n };
    spec.switcher["program_" + n] = { label: "Program camera " + n, key: "Numpad" + n };
  }
  if (!R) delete spec.camera;
  const km = KM.create(spec); km.attach(doc); km.open("switcher");

  const handlers = {};
  km.onButton((st, ac) => { const f = handlers[st + "." + ac]; if (f) f(); });
  const onAction = (st, ac, fn) => { handlers[st + "." + ac] = fn; };
  const NAMES = { Space: "Space", Enter: "Enter", Backquote: "`", Minus: "-", Equal: "=", BracketLeft: "[", BracketRight: "]", Semicolon: ";", Quote: "'", Comma: ",", Period: ".", Slash: "/", Backslash: "\\",
                  ArrowLeft: "←", ArrowRight: "→", ArrowUp: "↑", ArrowDown: "↓" };
  const label = code => !code ? "none" : NAMES[code] || code.replace(/^Key/, "").replace(/^Digit/, "").replace(/^Numpad/, "Num ");

  /* ---- keep the person's choices on the host ---- */
  let saved = JSON.stringify(km.toJSON()), timer = 0;
  async function load() {
    try {
      const r = await fetch("/api/keymap", { cache: "no-store" });
      if (!r.ok || !/json/i.test(r.headers.get("content-type") || "")) return;
      const j = await r.json();
      if (j.keymap) { km.load(j.keymap); saved = JSON.stringify(km.toJSON()); }
    } catch (e) { /* no host behind this page: the defaults stand */ }
  }
  async function save() {
    const body = JSON.stringify(km.toJSON());
    try {
      const r = await fetch("/api/keymap", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ keymap: JSON.parse(body) }) });
      if (r.ok) saved = body;
    } catch (e) { /* tried again at the next change */ }
  }
  km.onChange(() => { if (JSON.stringify(km.toJSON()) !== saved) { clearTimeout(timer); timer = setTimeout(save, 800); } });

  /* ---- assign keys ---- */
  let assigning = false;
  const btn = doc.createElement("button");
  btn.id = "ck-assign"; btn.type = "button"; btn.className = "ghost"; btn.textContent = "Assign keys";
  btn.style.cssText = "position:fixed;right:12px;bottom:56px;z-index:1001";            // above the page's bottom bar
  function setAssign(on) {
    assigning = !!on; btn.textContent = assigning ? "Done assigning" : "Assign keys"; km.cancelAsk();
    doc.body.classList.toggle("ck-assigning", assigning);
    refreshOverlay();
  }
  btn.addEventListener("click", () => setAssign(!assigning));
  doc.addEventListener("click", e => {
    if (!assigning || btn.contains(e.target)) return;
    const el = e.target.closest && e.target.closest("[data-key-station][data-key-action]");
    if (!el) return;
    e.preventDefault(); e.stopImmediatePropagation();
    const st = el.dataset.keyStation, ac = el.dataset.keyAction;
    if (km.activeStation() !== st) km.open(st);
    km.ask(st, ac);
  }, true);
  doc.addEventListener("keydown", e => { if (assigning && e.code === "Escape") setAssign(false); }, true);          // the map already took Esc if a question was open

  let overlayHandle = null;
  function refreshOverlay() { if (overlayHandle) overlayHandle.render(); }
  function start() {
    doc.body.appendChild(btn);
    overlayHandle = KM.overlay(doc.body, km, { fixed: true, show: () => assigning || !!km.pending() || km.activeStation() === "camera" });
    load();
  }
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", start); else start();

  global.PubCastControlKeys = { km, onAction, label, open: st => km.open(st), isAssigning: () => assigning, setAssign };
})(window);
