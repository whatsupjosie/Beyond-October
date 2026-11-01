/* PubCast key assignment map.
 *
 * One place that decides what a keyboard key does at each station (video switcher, audio mixer, editor, playback ...), so
 * two screens can no longer both claim Space. A station is "open" while you sit at it; only then do its keys act, and
 * while one is open the walker does not move (see world_walk.html).
 *
 *   - A control on the station is a BUTTON (press its key) or a FADER (press its key to select it, then Up / Down change it).
 *   - Keys are KeyboardEvent.code values (the physical key), so a layout works on any keyboard. No modifiers.
 *   - The station's own on-screen controls are fixed. Only the keys are assigned. Ask "where would you like the Cut button?"
 *     with ask(station, action); the next key pressed (or clicked on the overlay) is the answer.
 *   - Esc, F5, F11, F12 and Tab can never be assigned (Esc leaves, the browser needs the others). Up and Down are also kept at any station with a fader, where they step it.
 *   - A key already in use at that station is reported, not taken: press it again (or call assign with replace) to take it over.
 *
 * Works in a browser (window.PubCastKeymap) and in Node (module.exports), so the logic is tested without a browser.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PubCastKeymap = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const RESERVED = new Set(["Escape", "F5", "F11", "F12", "Tab"]);
  const FADER_KEYS = new Set(["ArrowUp", "ArrowDown"]);        // reserved only at a station that has a fader, where they step the selected one
  const MODIFIER = /^(Shift|Control|Alt|Meta|OS)(Left|Right)?$|^(CapsLock|NumLock|ScrollLock|ContextMenu|Fn)$/;
  const CODE = /^[A-Za-z][A-Za-z0-9]{0,23}$/;
  const ID = /^[a-z][a-z0-9_]{0,39}$/;

  const instances = [];            // every keymap made on this page, so "is anyone sitting at a station?" has one answer

  /* spec: { station: { action: { label, kind: "button" | "hold" | "fader", key: "Space" | null, min, max, step, value } } }
     button: acts when pressed. hold: acts for as long as the key is held (camera axes: any number at once). fader: key selects, Up / Down step. */
  function create(spec) {
    const defs = {}, bind = {}, values = {}, listeners = [], handlers = { button: null, fader: null, hold: null }, down = new Map();   // "station.action" -> the key that is holding it, for every hold control now held
    for (const [st, actions] of Object.entries(spec || {})) {
      if (!ID.test(st)) throw new Error("bad station id: " + st);
      defs[st] = {}; bind[st] = {}; values[st] = {};
      for (const [ac, d] of Object.entries(actions)) {
        if (!ID.test(ac)) throw new Error("bad action id: " + ac);
        const kind = d.kind === "fader" ? "fader" : d.kind === "hold" ? "hold" : "button";
        defs[st][ac] = { label: String(d.label || ac), kind, key: d.key || null,
                         min: kind === "fader" ? (d.min ?? 0) : 0, max: kind === "fader" ? (d.max ?? 100) : 0, step: kind === "fader" ? (d.step ?? 1) : 0 };
        values[st][ac] = kind === "fader" ? Math.min(defs[st][ac].max, Math.max(defs[st][ac].min, d.value ?? defs[st][ac].min)) : 0;
      }
      // defaults must themselves be valid and not collide, or the spec is wrong
      for (const [ac, d] of Object.entries(defs[st])) {
        if (d.key) {
          const bad = refusal(d.key, st);
          if (bad) throw new Error(`default key ${d.key} for ${st}.${ac} is ${bad}`);
          const clash = Object.keys(bind[st]).find(o => bind[st][o] === d.key);
          if (clash) throw new Error(`default key ${d.key} used twice at ${st}: ${clash} and ${ac}`);
        }
        bind[st][ac] = d.key || null;
      }
    }
    let active = null, selected = null, pending = null;

    function hasFader(st) { return !!(defs[st] && Object.values(defs[st]).some(d => d.kind === "fader")); }
    function refusal(code, st) {
      if (typeof code !== "string" || !CODE.test(code)) return "invalid";
      if (RESERVED.has(code) || (FADER_KEYS.has(code) && hasFader(st))) return "reserved";
      if (MODIFIER.test(code)) return "modifier";
      return null;
    }
    const changed = () => { for (const fn of listeners) { try { fn(); } catch (e) { /* a listener must not break key handling */ } } };
    const known = (st, ac) => !!(defs[st] && defs[st][ac]);
    const owner = (st, code) => Object.keys(bind[st]).find(a => bind[st][a] === code) || null;

    function assign(st, ac, code, opts) {
      if (!known(st, ac)) return { ok: false, reason: "unknown" };
      const bad = refusal(code, st);
      if (bad) return { ok: false, reason: bad };
      const other = owner(st, code);
      if (other && other !== ac) {
        if (!(opts && opts.replace)) return { ok: false, reason: "conflict", with: other };
        bind[st][other] = null;
        bind[st][ac] = code; changed();
        return { ok: true, displaced: other };
      }
      bind[st][ac] = code; changed();
      return { ok: true };
    }
    function clear(st, ac) { if (!known(st, ac)) return false; bind[st][ac] = null; if (selected && selected.st === st && selected.ac === ac) selected = null; changed(); return true; }
    function resetStation(st) { if (!defs[st]) return false; for (const ac of Object.keys(defs[st])) bind[st][ac] = defs[st][ac].key || null; changed(); return true; }

    function open(st) { if (!defs[st]) return false; releaseAll(); active = st; selected = null; pending = null; announce(); changed(); return true; }
    function close() { releaseAll(); active = null; selected = null; pending = null; announce(); changed(); }
    function releaseAll() { for (const k of [...down.keys()]) { down.delete(k); if (handlers.hold) { const [st, ac] = k.split("."); handlers.hold(st, ac, false); } } }
    function announce() {
      if (typeof document !== "undefined" && document.dispatchEvent && typeof CustomEvent === "function")
        document.dispatchEvent(new CustomEvent("pubcast:station", { detail: { station: active } }));
    }

    function ask(st, ac) {
      if (!known(st, ac)) return null;
      pending = { st, ac, confirm: null }; changed();
      return `Where would you like the ${defs[st][ac].label} ${defs[st][ac].kind === "fader" ? "fader" : "button"}?`;      // a held control is still asked about as a button
    }
    function cancelAsk() { const had = !!pending; pending = null; if (had) changed(); return had; }

    function setValue(st, ac, v) {
      const d = defs[st] && defs[st][ac]; if (!d || d.kind !== "fader" || !Number.isFinite(v)) return null;
      values[st][ac] = Math.min(d.max, Math.max(d.min, v)); changed();
      if (handlers.fader) handlers.fader(st, ac, values[st][ac]);
      return values[st][ac];
    }

    /* A key went down at station `st`. Returns {handled, ...}. handled=false means the station should deal with it (Esc leaves). */
    function press(st, code) {
      if (!defs[st]) return { handled: false };
      if (pending && pending.st === st) {
        if (code === "Escape") { pending = null; changed(); return { handled: true, learn: { ok: false, reason: "cancelled" } }; }
        const replace = pending.confirm === code;                          // the same key a second time confirms taking it over
        const r = assign(st, pending.ac, code, { replace });
        if (r.ok) { const ac = pending.ac; pending = null; changed(); return { handled: true, learn: Object.assign({ action: ac, code }, r) }; }
        if (r.reason === "conflict") { pending.confirm = code; changed(); }
        return { handled: true, learn: r };
      }
      if (code === "Escape") {
        if (selected) { selected = null; changed(); return { handled: true, deselected: true }; }
        return { handled: false };
      }
      if ((code === "ArrowUp" || code === "ArrowDown") && selected && selected.st === st) {
        const d = defs[st][selected.ac], v = setValue(st, selected.ac, values[st][selected.ac] + (code === "ArrowUp" ? d.step : -d.step));
        return { handled: true, action: selected.ac, value: v };
      }
      const ac = owner(st, code);
      if (!ac) return { handled: false };
      if (defs[st][ac].kind === "fader") { selected = { st, ac }; changed(); return { handled: true, action: ac, selected: true }; }
      if (defs[st][ac].kind === "hold") {
        const key = st + "." + ac;
        if (!down.has(key)) { down.set(key, code); if (handlers.hold) handlers.hold(st, ac, true); changed(); }     // key repeat does not press it again
        return { handled: true, action: ac, hold: true };
      }
      if (handlers.button) handlers.button(st, ac);
      return { handled: true, action: ac };
    }

    /* Listen for keys. Runs before other handlers (capture) and stops them when it uses a key, so an old hard-coded
       handler cannot also act while a station is open. Keys with Ctrl, Alt or Meta, and typing in a field, are left alone. */
    function attach(doc) {
      doc.addEventListener("keydown", e => {
        if (!active || e.ctrlKey || e.altKey || e.metaKey) return;
        const tag = (e.target && e.target.tagName || "").toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        const r = press(active, e.code);
        if (r.handled) { e.preventDefault(); if (e.stopImmediatePropagation) e.stopImmediatePropagation(); }
      }, true);
      // letting go of a held key (even after the station closed or the key was reassigned while held), and losing focus, release them
      doc.addEventListener("keyup", e => {
        if (!down.size) return;
        for (const [k, code] of [...down]) {
          if (code !== e.code) continue;                                                  // the key that was pressed, even if it has been reassigned since
          const [st, ac] = k.split("."); down.delete(k); if (handlers.hold) handlers.hold(st, ac, false); changed();
        }
      }, true);
      const win = doc.defaultView; if (win && win.addEventListener) win.addEventListener("blur", () => { releaseAll(); changed(); });
    }

    function toJSON() {
      const out = {};
      for (const st of Object.keys(bind)) out[st] = Object.assign({}, bind[st]);      // null = cleared on purpose, so the default does not come back
      return out;
    }
    /* Apply saved bindings. Anything unknown, invalid, reserved or doubled is dropped (the default stays); returns what was dropped. */
    function load(saved) {
      const dropped = [];
      if (!saved || typeof saved !== "object") return { dropped: ["not an object"] };
      for (const st of Object.keys(defs)) {
        const mine = saved[st]; if (!mine || typeof mine !== "object") continue;
        const taken = new Set();
        const next = {};
        for (const ac of Object.keys(defs[st])) {
          if (!(ac in mine)) continue;
          const v = mine[ac];
          if (v === null) { next[ac] = null; continue; }
          if (refusal(v, st)) { dropped.push(`${st}.${ac}: ${v}`); continue; }
          if (taken.has(v)) { dropped.push(`${st}.${ac}: ${v} (doubled)`); continue; }
          taken.add(v); next[ac] = v;
        }
        // a saved key may not collide with a default that was kept
        for (const [ac, v] of Object.entries(next)) if (v !== null) {
          const clash = Object.keys(defs[st]).find(o => o !== ac && !(o in next) && bind[st][o] === v);
          if (clash) { dropped.push(`${st}.${ac}: ${v} (used by ${clash})`); delete next[ac]; }
        }
        Object.assign(bind[st], next);
      }
      for (const st of Object.keys(saved)) if (!defs[st]) dropped.push(`${st}: unknown station`);
      changed();
      return { dropped };
    }

    const api = {
      assign, clear, resetStation, open, close, ask, cancelAsk, press, attach, setValue, toJSON, load,
      onChange: fn => { listeners.push(fn); },
      onButton: fn => { handlers.button = fn; }, onFader: fn => { handlers.fader = fn; }, onHold: fn => { handlers.hold = fn; },
      held: st => [...down.keys()].filter(k => k.startsWith(st + ".")).map(k => k.slice(st.length + 1)),
      activeStation: () => active, isOpen: () => active !== null,
      pending: () => pending && { station: pending.st, action: pending.ac, confirming: pending.confirm },
      selected: () => selected && { station: selected.st, action: selected.ac },
      bindings: st => Object.assign({}, bind[st] || {}),
      value: (st, ac) => (values[st] ? values[st][ac] : undefined),
      def: (st, ac) => (known(st, ac) ? Object.assign({}, defs[st][ac]) : null),
      stations: () => Object.keys(defs),
      refusal,
    };
    instances.push(api);
    return api;
  }

  /* ---- the transparent keyboard laid over a station ---- */
  const ROWS = [
    [["Backquote", "`"], ["Digit1", "1"], ["Digit2", "2"], ["Digit3", "3"], ["Digit4", "4"], ["Digit5", "5"], ["Digit6", "6"], ["Digit7", "7"], ["Digit8", "8"], ["Digit9", "9"], ["Digit0", "0"], ["Minus", "-"], ["Equal", "="], ["Backspace", "Bksp", 2]],
    [["Tab", "Tab", 1.5], ["KeyQ", "Q"], ["KeyW", "W"], ["KeyE", "E"], ["KeyR", "R"], ["KeyT", "T"], ["KeyY", "Y"], ["KeyU", "U"], ["KeyI", "I"], ["KeyO", "O"], ["KeyP", "P"], ["BracketLeft", "["], ["BracketRight", "]"], ["Backslash", "\\", 1.5]],
    [["CapsLock", "Caps", 1.8], ["KeyA", "A"], ["KeyS", "S"], ["KeyD", "D"], ["KeyF", "F"], ["KeyG", "G"], ["KeyH", "H"], ["KeyJ", "J"], ["KeyK", "K"], ["KeyL", "L"], ["Semicolon", ";"], ["Quote", "'"], ["Enter", "Enter", 2.2]],
    [["ShiftLeft", "Shift", 2.3], ["KeyZ", "Z"], ["KeyX", "X"], ["KeyC", "C"], ["KeyV", "V"], ["KeyB", "B"], ["KeyN", "N"], ["KeyM", "M"], ["Comma", ","], ["Period", "."], ["Slash", "/"], ["ShiftRight", "Shift", 2.7]],
    [["Space", "Space", 8]],
  ];

  /* Draw the keyboard into `container` for `km`. Assigned keys are lit with the control's name, the selected fader is
     marked, and while a question is pending the keys can be clicked as well as pressed. Returns {render, destroy}. */
  function overlay(container, km, opts) {
    opts = opts || {};
    const doc = container.ownerDocument;
    const wrap = doc.createElement("div"); wrap.className = "pck-overlay";
    wrap.style.cssText = (opts.fixed ? "position:fixed;z-index:1000;inset:auto 0 56px 0;" : "position:absolute;inset:auto 0 0 0;") + "margin:auto;max-width:880px;padding:10px;background:rgba(10,12,20,.45);border-radius:14px;pointer-events:none;font:12px system-ui,sans-serif;color:#fff;text-align:center";
    const prompt = doc.createElement("div"); prompt.className = "pck-prompt"; prompt.style.cssText = "min-height:20px;margin-bottom:6px;font-size:14px";
    wrap.appendChild(prompt);
    const keys = new Map();
    for (const row of ROWS) {
      const r = doc.createElement("div"); r.style.cssText = "display:flex;justify-content:center;gap:3px;margin-bottom:3px";
      for (const [code, label, w] of row) {
        const k = doc.createElement("div"); k.className = "pck-key"; k.dataset.code = code;
        k.style.cssText = `width:${(w || 1) * 44}px;height:40px;border:1px solid rgba(255,255,255,.35);border-radius:6px;background:rgba(255,255,255,.08);box-sizing:border-box;padding:2px;overflow:hidden;line-height:1.1`;
        const cap = doc.createElement("div"); cap.textContent = label; cap.style.opacity = ".7"; k.appendChild(cap);
        const name = doc.createElement("div"); name.className = "pck-name"; name.style.cssText = "font-size:10px;color:#ffd36b"; k.appendChild(name);
        k.addEventListener("click", () => { if (km.pending() && km.activeStation()) km.press(km.activeStation(), code); });
        keys.set(code, { k, name }); r.appendChild(k);
      }
      wrap.appendChild(r);
    }
    container.appendChild(wrap);

    function render() {
      const st = km.activeStation(), b = st ? km.bindings(st) : {}, pend = km.pending(), sel = km.selected();
      wrap.style.display = st && (!opts.show || opts.show()) ? "block" : "none";
      wrap.style.pointerEvents = pend ? "auto" : "none";
      const byCode = {};
      for (const [ac, code] of Object.entries(b)) if (code) byCode[code] = ac;
      for (const [code, { k, name }] of keys) {
        const ac = byCode[code], d = ac ? km.def(st, ac) : null;
        name.textContent = d ? d.label : "";
        const chosen = !!(sel && ac && sel.action === ac);
        k.style.background = chosen ? "rgba(255,211,107,.55)" : d ? "rgba(255,211,107,.22)" : "rgba(255,255,255,.08)";
        k.style.borderColor = RESERVED.has(code) ? "rgba(255,255,255,.12)" : "rgba(255,255,255,.35)";
        k.style.cursor = pend ? "pointer" : "default";
        k.dataset.on = d ? "1" : "0"; k.dataset.sel = chosen ? "1" : "0";
      }
      if (pend) {
        const d = km.def(pend.station, pend.action);
        prompt.textContent = pend.confirming
          ? `${pend.confirming.replace(/^Key|^Digit/, "")} already does something here. Press it again to give it to ${d.label}, or pick another key.`
          : `Where would you like the ${d.label} ${d.kind === "fader" ? "fader" : "button"}?`;
      } else prompt.textContent = sel ? `${km.def(sel.station, sel.action).label}: ${km.value(sel.station, sel.action)}  (Up / Down to change, Esc to let go)` : "";
    }
    km.onChange(render); render();
    return { render, destroy: () => wrap.remove() };
  }

  /* True while any keymap on the page has a station open. The walker asks this before it moves. */
  const isOpen = () => instances.some(k => k.isOpen());
  const activeStation = () => { const k = instances.find(i => i.isOpen()); return k ? k.activeStation() : null; };
  return { create, overlay, isOpen, activeStation, RESERVED, ROWS };
});
