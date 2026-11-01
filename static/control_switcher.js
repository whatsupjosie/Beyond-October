/* The Vision Mixer on the Control page: sources, Preview, Cut, Fade, Program.
 *
 * Before this script the Cut and Fade buttons and the source list had nothing behind them (only a few keyboard shortcuts in
 * switcher.js worked). Everything goes through the switcher service (/api/switcher/*). The keys come from the key map
 * (static/control_keys.js), so what the page tells you and what the keys do are always the same thing.
 */
(function (global) {
  "use strict";
  const doc = global.document, CK = global.PubCastControlKeys;
  if (!doc) return;
  const $ = id => doc.getElementById(id);
  const cutBtn = $("vm-cut"), fadeBtn = $("vm-take"), mix = $("vm-mix"), list = $("cam-list");
  if (!cutBtn && !fadeBtn && !list) return;                          // this page has no vision mixer

  let state = { program: null, preview: null, sources: [] }, busy = false;
  function feedback(message, failed = false) {
    if (!cutBtn && !fadeBtn) return;
    let out = $("switcher-feedback");
    if (!out) {
      out = doc.createElement("output"); out.id = "switcher-feedback"; out.setAttribute("role","status");
      out.style.cssText = "display:block;margin:8px 0;font-size:12px;max-width:100%";
      (fadeBtn || cutBtn).insertAdjacentElement("afterend",out);
    }
    out.textContent = message;
    out.style.color = failed ? "#ff7777" : "#8eddac";
  }
  const post = async (path, body) => {
    const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    if (!response.ok) throw Error(path+" HTTP "+response.status);
    const data = await response.json();
    if (!data || !("program" in data) || !("preview" in data)) throw Error("Switcher confirmation invalid");
    return data;
  };
  async function refresh() {
    try {
      const r = await fetch("/api/switcher/state", { cache: "no-store" });
      if (!r.ok) throw Error("HTTP "+r.status);
      const j = await r.json();
      if (!Array.isArray(j.sources)) throw Error("Invalid source list");
      state = { program: j.program || null, preview: j.preview || null, sources: j.sources };
      render();
    } catch (e) { feedback("Shared switcher unavailable: "+e.message, true); }
  }
  async function act(fn) {
    if (busy) return; busy = true;
    try {
      const result = await fn();
      if (!result) throw Error("No preview camera selected");
      feedback("Program "+(result.program||"—")+" / Preview "+(result.preview||"—"));
      await refresh();
    } catch (e) { feedback("Switch failed: "+e.message, true); }
    finally { busy = false; }
  }
  const setPreview = id => act(() => post("/api/switcher/preview/" + encodeURIComponent(id)));
  const setProgram = id => act(() => post("/api/switcher/cut/" + encodeURIComponent(id)));
  const doCut = () => act(() => post("/api/switcher/cut"));
  const doFade = () => act(() => {
    if (!state.preview) return null;                                  // nothing to fade to
    const ms = Math.max(100, Math.min(4000, parseInt(mix && mix.value, 10) || 400));
    return post("/api/switcher/transition", { camera_id: state.preview, type: "dissolve", duration_ms: ms });
  });

  function render() {
    if (list) {
      list.textContent = "";
      state.sources.forEach((s, i) => {
        const b = doc.createElement("button");
        b.type = "button"; b.className = "ghost"; b.dataset.source = s.id;
        const n = i + 1;
        b.textContent = (n <= 9 ? n + "  " : "") + (s.name || s.id) + (s.id === state.program ? "   PGM" : s.id === state.preview ? "   PVW" : "");
        b.style.cssText = "text-align:left;padding:10px;" + (s.id === state.program ? "outline:2px solid #e33;" : s.id === state.preview ? "outline:2px solid #3b3;" : "");
        if (n <= 9) { b.dataset.keyStation = "switcher"; b.dataset.keyAction = "preview_" + n; }
        b.addEventListener("click", () => setPreview(s.id));
        list.appendChild(b);
      });
    }
    hint();
  }
  /* the line under the buttons says what the keys really are right now */
  function hint() {
    if (!CK) return;
    const el = [...doc.querySelectorAll(".muted.small")].find(e => /^Keys:/.test(e.textContent.trim()) || e.dataset.keyHint);
    if (!el) return;
    const b = CK.km.bindings("switcher"), k = CK.label;
    el.dataset.keyHint = "1";
    el.textContent = `Keys: ${k(b.preview_1)}–${k(b.preview_9)} Preview, ${k(b.cut)} Cut, ${k(b.fade)} Fade, ${k(b.program_1)}–${k(b.program_9)} Program`;
  }

  if (cutBtn) { cutBtn.dataset.keyStation = "switcher"; cutBtn.dataset.keyAction = "cut"; cutBtn.addEventListener("click", doCut); }
  if (fadeBtn) { fadeBtn.dataset.keyStation = "switcher"; fadeBtn.dataset.keyAction = "fade"; fadeBtn.addEventListener("click", doFade); }
  if (CK) {
    CK.onAction("switcher", "cut", doCut); CK.onAction("switcher", "fade", doFade);
    for (let n = 1; n <= 9; n++) {
      CK.onAction("switcher", "preview_" + n, () => { const s = state.sources[n - 1]; if (s) setPreview(s.id); });
      CK.onAction("switcher", "program_" + n, () => { const s = state.sources[n - 1]; if (s) setProgram(s.id); });
    }
    CK.km.onChange(hint);
  }
  refresh(); setInterval(() => { if (!doc.hidden) refresh(); }, 3000);
  global.PubCastSwitcher = { refresh, cut: doCut, fade: doFade, preview: setPreview, program: setProgram, state: () => state };
})(window);
