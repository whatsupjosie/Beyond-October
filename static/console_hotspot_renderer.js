/*
 * PubCast image console renderer.
 *
 * Loads a hotspot manifest with source image dimensions, places controls over
 * the console art, and forwards actions through studio_console_hotspots.js.
 */
(function () {
  "use strict";

  const state = {
    manifest: null,
    adapter: null,
    values: new Map(),
    shift: false,
  };

  function clamp01(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 0;
    return Math.max(0, Math.min(1, number));
  }

  // A level of 0 (muted) is real; only a missing or non-numeric value falls back.
  function levelOr(value, fallback) {
    return typeof value === "number" && Number.isFinite(value) ? clamp01(value) : fallback;
  }

  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (value === undefined || value === null) return;
      if (key === "className") node.className = value;
      else if (key === "style") Object.assign(node.style, value);
      else node.setAttribute(key, value);
    });
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function actionPayload(hotspot, extra) {
    const payload = Object.assign({}, hotspot.payload || {}, extra || {});
    if (payload.action === "set_volume" && payload.level === undefined) {
      payload.level = payload.value !== undefined ? payload.value : 0.5;
    }
    return payload;
  }

  async function executeHotspot(hotspot, extra) {
    if (!hotspot || !hotspot.action_id || !state.adapter) return;
    setStatus("Sending " + hotspot.label + "...");
    try {
      const result = await state.adapter.executeConfirmed(hotspot.action_id, actionPayload(hotspot, extra), {
        spec: hotspot.safety ? { safety: hotspot.safety, label: hotspot.label } : null,
      });
      if (result && result.canceled) {
        setStatus(hotspot.label + " canceled.");
        return;
      }
      setStatus(hotspot.label + " ok.");
    } catch (err) {
      setStatus((err && err.message) || String(err), true);
    }
  }

  function setStatus(message, isError) {
    const node = document.querySelector("[data-console-status]");
    if (!node) return;
    node.textContent = message;
    node.dataset.level = isError ? "error" : "ok";
  }

  function hotspotStyle(hotspot) {
    return {
      left: (hotspot.x * 100) + "%",
      top: (hotspot.y * 100) + "%",
      width: (hotspot.w * 100) + "%",
      height: (hotspot.h * 100) + "%",
    };
  }

  function makeButton(hotspot) {
    const node = el("button", {
      className: "pc-console-hotspot pc-console-hotspot--" + hotspot.kind,
      type: "button",
      title: hotspot.label,
      "aria-label": hotspot.label,
      "data-studio-action": hotspot.action_id,
      style: hotspotStyle(hotspot),
    });
    node.addEventListener("click", async () => {
      node.classList.toggle("is-active", hotspot.kind === "button" || hotspot.kind === "fan");
      await executeHotspot(hotspot);
    });
    return node;
  }

  function makeSlider(hotspot) {
    const wrap = el("div", {
      className: "pc-console-hotspot pc-console-slider",
      title: hotspot.label,
      style: hotspotStyle(hotspot),
    });
    // A painted fader slot leans with the perspective of the desk. The map
    // gives that lean (degrees from upright, top to the right is positive) and
    // the control is turned to lie along the slot, so a finger pushing the
    // fader up its slot raises the level.
    if (Number.isFinite(hotspot.track_angle_deg)) {
      wrap.style.setProperty("--pc-track-angle", hotspot.track_angle_deg + "deg");
    }
    const input = el("input", {
      type: "range",
      min: "0",
      max: "100",
      value: String(Math.round(levelOr(hotspot.default_value, 0.55) * 100)),
      "aria-label": hotspot.label,
    });
    // "change" and "pointerup" both fire at the end of one drag; send once.
    let lastSent = null;
    const send = () => {
      const value = clamp01(Number(input.value) / 100);
      if (value === lastSent) return;
      lastSent = value;
      state.values.set(hotspot.id, value);
      executeHotspot(hotspot, { value: value, level: value });
    };
    input.addEventListener("pointerdown", () => { lastSent = null; });
    input.addEventListener("change", send);
    input.addEventListener("pointerup", send);
    wrap.appendChild(input);
    return wrap;
  }

  function makeKnob(hotspot) {
    const node = makeButton(hotspot);
    node.classList.add("pc-console-knob");
    state.values.set(hotspot.id, levelOr(hotspot.default_value, 0.5));

    const paint = (value) => {
      node.style.setProperty("--turn", ((clamp01(value) * 270) - 135) + "deg");
    };
    const setValue = (value) => {
      const clean = clamp01(value);
      state.values.set(hotspot.id, clean);
      paint(clean);
      executeHotspot(hotspot, { value: clean, level: clean });
    };

    let wheelTimer = null;
    node.addEventListener("wheel", (event) => {
      event.preventDefault();
      if (!event.deltaY) return;
      const next = clamp01(levelOr(state.values.get(hotspot.id), 0.5) + (event.deltaY < 0 ? 0.05 : -0.05));
      state.values.set(hotspot.id, next);
      paint(next);
      clearTimeout(wheelTimer);
      wheelTimer = setTimeout(() => setValue(next), 150);
    }, { passive: false });

    // Drag right or up to turn up, left or down to turn down. Works for mouse,
    // finger and pen; the knob follows the pointer while it moves and the
    // action is sent once, on release. A press that barely moves stays a tap.
    let drag = null;
    let swallowClick = false;
    node.addEventListener("pointerdown", (event) => {
      if (drag) return;
      if (event.pointerType === "mouse" && event.button !== 0) return;
      // A touch drag never produces a click, so a stale flag would eat this tap.
      swallowClick = false;
      drag = {
        id: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        start: levelOr(state.values.get(hotspot.id), 0.5),
        moved: false,
        value: levelOr(state.values.get(hotspot.id), 0.5),
      };
      try { node.setPointerCapture(event.pointerId); } catch (_err) { /* pointer already gone */ }
    });
    node.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 4) return;
      drag.moved = true;
      drag.value = clamp01(drag.start + (dx - dy) / 160);
      paint(drag.value);
    });
    const finish = (event, commit) => {
      if (!drag || event.pointerId !== drag.id) return;
      const done = drag;
      drag = null;
      if (node.hasPointerCapture(event.pointerId)) node.releasePointerCapture(event.pointerId);
      if (!done.moved) return;
      swallowClick = true;
      if (commit) setValue(done.value);
      else paint(done.start);
    };
    node.addEventListener("pointerup", (event) => finish(event, true));
    node.addEventListener("pointercancel", (event) => finish(event, false));
    // A drag must not also count as a tap, and a real tap on a level control
    // must send the level it already has: the shared button handler would send
    // the 0.5 default, so tapping a volume knob would jump the volume.
    const isLevel = (hotspot.payload || {}).action === "set_volume";
    node.addEventListener("click", (event) => {
      event.stopImmediatePropagation();
      if (swallowClick) {
        swallowClick = false;
        return;
      }
      const current = levelOr(state.values.get(hotspot.id), 0.5);
      executeHotspot(hotspot, isLevel ? { value: current, level: current } : undefined);
    }, true);
    paint(state.values.get(hotspot.id));
    return node;
  }

  // ---- Typewriter-style keys -------------------------------------------------
  // A key reacts the moment a finger, pen or mouse goes down on it (not on
  // release), several keys can be held at once on a multi-touch screen, and a
  // physical keyboard animates the same keys. Each press is announced as a
  // "pubcast:key" event so the page (or a mode, or a sound player) decides what
  // it does. Keys carry no studio action.
  const SHIFTED = {
    "1": "!", "2": "@", "3": "#", "4": "$", "5": "%", "6": "^", "7": "&", "8": "*", "9": "(", "0": ")", "-": "_",
    ";": ":", "'": "\"", ",": "<", ".": ">", "/": "?", "\u00bd": "\u00bc",
  };
  const CODE_TO_CHAR = {
    Space: "SPACE", Enter: "RETURN", NumpadEnter: "RETURN", ShiftLeft: "SHIFT", ShiftRight: "SHIFT",
    Minus: "-", Semicolon: ";", Quote: "'", Comma: ",", Period: ".", Slash: "/",
  };

  function legendForCode(code) {
    if (CODE_TO_CHAR[code]) return CODE_TO_CHAR[code];
    const letter = /^Key([A-Z])$/.exec(code);
    if (letter) return letter[1];
    const digit = /^Digit([0-9])$/.exec(code);
    if (digit) return digit[1];
    return "";
  }

  function textForKey(char, shifted) {
    if (char === "SPACE") return " ";
    if (char === "RETURN") return "\n";
    if (!char || char === "SHIFT" || char === "BLANK") return "";
    if (/^[A-Z]$/.test(char)) return shifted ? char : char.toLowerCase();
    return shifted && SHIFTED[char] ? SHIFTED[char] : char;
  }

  function setShift(frame, on) {
    state.shift = on;
    frame.classList.toggle("is-shifted", on);
  }

  // One shift lasts one key, like a typewriter's, from any device. Tapping the
  // armed Shift again cancels it. opts.text / opts.shifted come from a physical
  // keyboard, which already knows what it typed.
  function announceKey(frame, hotspot, source, opts) {
    const char = hotspot.char || "";
    const options = opts || {};
    let shifted;
    let text;
    if (char === "SHIFT") {
      setShift(frame, !state.shift);
      shifted = state.shift;
      text = "";
    } else {
      shifted = options.shifted !== undefined ? options.shifted : state.shift;
      text = options.text !== undefined ? options.text : textForKey(char, shifted);
      // Only a key that types something uses up the armed Shift.
      if (state.shift && (text !== "" || char === "BACKSPACE")) setShift(frame, false);
    }
    frame.dispatchEvent(new CustomEvent("pubcast:key", {
      bubbles: true,
      detail: { id: hotspot.id, char: char, text: text, source: source, shift: shifted },
    }));
  }

  function makeKey(hotspot, frame) {
    const node = el("button", {
      className: "pc-console-hotspot pc-console-hotspot--key",
      type: "button",
      title: hotspot.label,
      "aria-label": hotspot.label,
      "data-key-char": hotspot.char || "",
      style: hotspotStyle(hotspot),
    });
    const held = new Set();
    node.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "mouse" && event.button !== 0) return;
      event.preventDefault();
      if (held.has(event.pointerId)) return;
      held.add(event.pointerId);
      try { node.setPointerCapture(event.pointerId); } catch (_err) { /* pointer already gone */ }
      node.classList.add("is-pressed");
      announceKey(frame, hotspot, "pointer");
    });
    const release = (event) => {
      if (!held.delete(event.pointerId)) return;
      if (!held.size) node.classList.remove("is-pressed");
    };
    node.addEventListener("pointerup", release);
    node.addEventListener("pointercancel", release);
    node.addEventListener("lostpointercapture", release);
    // Pointer clicks were handled on pointerdown. A click with no pointer behind
    // it (a screen reader, switch control, or Enter/Space on a focused key) is
    // still a key press and must type.
    node.addEventListener("click", (event) => {
      event.preventDefault();
      const fromPointer = typeof event.pointerType === "string" ? event.pointerType !== "" : event.detail !== 0;
      if (fromPointer) return;
      node.classList.add("is-pressed");
      announceKey(frame, hotspot, "pointer");
      setTimeout(() => node.classList.remove("is-pressed"), 90);
    });
    return node;
  }

  function isTypingTarget(target) {
    if (!target || target === document.body) return false;
    return Boolean(target.isContentEditable) || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName || "");
  }

  function mirrorHardwareKeyboard(frame, manifest) {
    const byChar = new Map();
    frame.querySelectorAll("[data-key-char]").forEach((node) => {
      const char = node.getAttribute("data-key-char");
      if (!byChar.has(char)) byChar.set(char, []);
      byChar.get(char).push(node);
    });
    const hotspotFor = (char) => manifest.hotspots.find((item) => item.char === char);
    const clearPressed = () => frame.querySelectorAll(".is-pressed").forEach((node) => node.classList.remove("is-pressed"));
    window.addEventListener("keydown", (event) => {
      // Never take keys from a text box or an IME, and leave shortcuts alone.
      if (isTypingTarget(event.target) || event.isComposing) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === "Backspace") {
        event.preventDefault();
        frame.dispatchEvent(new CustomEvent("pubcast:key", {
          bubbles: true,
          detail: { id: "hardware.backspace", char: "BACKSPACE", text: "", source: "keyboard", shift: false },
        }));
        return;
      }
      const char = legendForCode(event.code);
      (byChar.get(char) || []).forEach((node) => node.classList.add("is-pressed"));
      const hotspot = hotspotFor(char);
      if (!hotspot || char === "SHIFT") return;
      event.preventDefault();
      // The keyboard already knows what it types (Shift, Caps Lock, any
      // layout), so its answer is used as is. Only a Shift armed by touch is
      // added on top. Dead keys and other non-characters type nothing.
      let text;
      if (char === "RETURN") text = "\n";
      else if (char === "SPACE") text = " ";
      else if (event.key && event.key.length === 1) text = event.key;
      else return;
      const touchShift = state.shift && !event.shiftKey && char !== "RETURN" && char !== "SPACE";
      if (touchShift) text = /^[a-z]$/.test(text) ? text.toUpperCase() : (SHIFTED[text] || text);
      announceKey(frame, hotspot, "keyboard", { text: text, shifted: event.shiftKey || touchShift });
    });
    window.addEventListener("keyup", (event) => {
      (byChar.get(legendForCode(event.code)) || []).forEach((node) => node.classList.remove("is-pressed"));
    });
    // A key released while the window is away never sends keyup.
    window.addEventListener("blur", clearPressed);
  }

  function renderHotspot(hotspot, frame) {
    if (hotspot.kind === "key" || hotspot.char) return makeKey(hotspot, frame);
    if (hotspot.kind === "slider") return makeSlider(hotspot);
    if (hotspot.kind === "knob" || hotspot.kind === "dial") return makeKnob(hotspot);
    return makeButton(hotspot);
  }

  function validateManifest(manifest) {
    if (!manifest || !manifest.image || !manifest.image.width_px || !manifest.image.height_px) {
      throw new Error("Console manifest is missing source image dimensions.");
    }
    if (!Array.isArray(manifest.hotspots)) throw new Error("Console manifest hotspots must be an array.");
    const view = manifest.view;
    if (view !== undefined) {
      const x = Number(view.x || 0);
      const w = Number(view.w);
      if (!Number.isFinite(w) || w <= 0 || w > 1 || !Number.isFinite(x) || x < 0 || x + w > 1.0001) {
        throw new Error("Console manifest view must stay inside the image.");
      }
    }
    manifest.hotspots.forEach((hotspot) => {
      if (hotspot.kind === "key" && !hotspot.char) throw new Error("Key hotspot " + (hotspot.id || "unknown") + " has no char.");
      if (hotspot.track_angle_deg !== undefined) {
        const angle = Number(hotspot.track_angle_deg);
        if (!Number.isFinite(angle) || Math.abs(angle) > 89) {
          throw new Error("Slider " + (hotspot.id || "unknown") + " has an invalid track angle.");
        }
      }
      ["x", "y", "w", "h"].forEach((key) => {
        const value = Number(hotspot[key]);
        if (!Number.isFinite(value) || value < 0 || value > 1) {
          throw new Error("Invalid hotspot coordinate for " + (hotspot.id || "unknown"));
        }
      });
    });
  }

  // Touch screens get a larger invisible target around small controls, but never
  // more than half the gap to the nearest neighbour, so a tap near the edge of
  // one control cannot land on the next. Overlapping neighbours get none.
  function applyTouchPads(frame) {
    // Measured from what is really on screen: CSS may already have made a small
    // control bigger than its map box.
    const nodes = Array.from(frame.querySelectorAll(".pc-console-layer > .pc-console-hotspot"));
    nodes.forEach((node) => node.style.setProperty("--pc-touch-pad", "0px"));
    const boxes = nodes.map((node) => node.getBoundingClientRect());
    if (!boxes.length || !boxes[0].width) return;
    boxes.forEach((a, i) => {
      let gap = Infinity;
      boxes.forEach((b, j) => {
        if (i === j) return;
        gap = Math.min(gap, Math.max(b.left - a.right, a.left - b.right, b.top - a.bottom, a.top - b.bottom));
      });
      const pad = Math.max(0, Math.min(8, Math.floor(gap / 2)));
      nodes[i].style.setProperty("--pc-touch-pad", pad + "px");
    });
  }

  function layoutViewport(root, viewport, frame, manifest) {
    const view = manifest.view;
    const aspect = manifest.image.width_px / manifest.image.height_px;
    const topbar = document.querySelector(".pc-console-topbar");
    const statusbar = document.querySelector(".pc-console-statusbar");
    const pad = 24;
    const availW = Math.max(200, root.clientWidth - pad);
    // Not visualViewport: it gets smaller while the person pinch-zooms, which
    // would shrink the whole machine.
    const screenH = window.innerHeight;
    const availH = Math.max(160, screenH - (topbar ? topbar.offsetHeight : 0) - (statusbar ? statusbar.offsetHeight : 0) - pad);
    const full = Math.min(availW / view.w, availH * aspect);
    viewport.style.width = (full * view.w) + "px";
    viewport.style.height = (full / aspect) + "px";
    frame.style.width = full + "px";
    frame.style.marginLeft = (-(view.x || 0) * full) + "px";
    applyTouchPads(frame);
  }

  async function init() {
    const root = document.querySelector("[data-console-manifest]");
    if (!root) return;
    const manifestPath = root.getAttribute("data-console-manifest");
    state.adapter = new window.PubCastStudioConsoleHotspots.StudioConsoleHotspots();

    const response = await fetch(manifestPath);
    if (!response.ok) throw new Error("Could not load the console map (" + response.status + ").");
    state.manifest = await response.json();
    validateManifest(state.manifest);

    const frame = el("div", { className: "pc-console-frame" });
    // Optional crop to the part of the art that matters. The picture is sized
    // to fit the screen in both directions, so the paper and the keys are
    // always visible together and no scrolling is needed while typing.
    const view = state.manifest.view;
    let viewport = null;
    if (view && view.w > 0 && view.w <= 1) {
      viewport = el("div", { className: "pc-console-viewport" });
    }
    const image = el("img", {
      className: "pc-console-image",
      src: state.manifest.image.clean_path,
      alt: state.manifest.console_id,
      width: String(state.manifest.image.width_px),
      height: String(state.manifest.image.height_px),
    });
    image.addEventListener("error", () => setStatus("Could not load the console picture.", true));
    const layer = el("div", { className: "pc-console-layer" });
    state.manifest.hotspots.forEach((hotspot) => layer.appendChild(renderHotspot(hotspot, frame)));
    frame.appendChild(image);
    frame.appendChild(layer);
    if (viewport) {
      viewport.appendChild(frame);
      root.appendChild(viewport);
      const fit = () => layoutViewport(root, viewport, frame, state.manifest);
      fit();
      window.addEventListener("resize", fit);
      window.addEventListener("orientationchange", fit);
    } else {
      root.appendChild(frame);
      applyTouchPads(frame);
      window.addEventListener("resize", () => applyTouchPads(frame));
    }
    // No long-press menu or text-selection callout over the machine.
    frame.addEventListener("contextmenu", (event) => event.preventDefault());
    if (state.manifest.keyboard_mirror) mirrorHardwareKeyboard(frame, state.manifest);
    document.dispatchEvent(new CustomEvent("pubcast:console-ready", { detail: { frame: frame, manifest: state.manifest } }));

    const meta = document.querySelector("[data-console-meta]");
    if (meta) {
      meta.textContent = state.manifest.console_id + " map " + state.manifest.image.width_px + " x " + state.manifest.image.height_px;
    }
    setStatus("Console ready.");
  }

  window.PubCastConsoleHotspotRenderer = { init: init, validateManifest: validateManifest, textForKey: textForKey };
  document.addEventListener("DOMContentLoaded", () => init().catch((err) => setStatus(err.message || String(err), true)));
})();
