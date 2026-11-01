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
  };

  function clamp01(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 0;
    return Math.max(0, Math.min(1, number));
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
    const input = el("input", {
      type: "range",
      min: "0",
      max: "100",
      value: String(Math.round((hotspot.default_value || 0.55) * 100)),
      "aria-label": hotspot.label,
    });
    const send = () => {
      const value = clamp01(Number(input.value) / 100);
      state.values.set(hotspot.id, value);
      executeHotspot(hotspot, { value: value, level: value });
    };
    input.addEventListener("change", send);
    input.addEventListener("pointerup", send);
    wrap.appendChild(input);
    return wrap;
  }

  function makeKnob(hotspot) {
    const node = makeButton(hotspot);
    node.classList.add("pc-console-knob");
    state.values.set(hotspot.id, hotspot.default_value || 0.5);

    const setValue = (value) => {
      const clean = clamp01(value);
      state.values.set(hotspot.id, clean);
      node.style.setProperty("--turn", ((clean * 270) - 135) + "deg");
      executeHotspot(hotspot, { value: clean, level: clean });
    };

    node.addEventListener("wheel", (event) => {
      event.preventDefault();
      setValue((state.values.get(hotspot.id) || 0.5) + (event.deltaY < 0 ? 0.05 : -0.05));
    }, { passive: false });

    let startX = 0;
    let startValue = 0.5;
    node.addEventListener("pointerdown", (event) => {
      startX = event.clientX;
      startValue = state.values.get(hotspot.id) || 0.5;
      node.setPointerCapture(event.pointerId);
    });
    node.addEventListener("pointerup", (event) => {
      if (!node.hasPointerCapture(event.pointerId)) return;
      node.releasePointerCapture(event.pointerId);
      setValue(startValue + ((event.clientX - startX) / 160));
    });
    node.style.setProperty("--turn", "0deg");
    return node;
  }

  function renderHotspot(hotspot) {
    if (hotspot.kind === "slider") return makeSlider(hotspot);
    if (hotspot.kind === "knob" || hotspot.kind === "dial") return makeKnob(hotspot);
    return makeButton(hotspot);
  }

  function validateManifest(manifest) {
    if (!manifest || !manifest.image || !manifest.image.width_px || !manifest.image.height_px) {
      throw new Error("Console manifest is missing source image dimensions.");
    }
    if (!Array.isArray(manifest.hotspots)) throw new Error("Console manifest hotspots must be an array.");
    manifest.hotspots.forEach((hotspot) => {
      ["x", "y", "w", "h"].forEach((key) => {
        const value = Number(hotspot[key]);
        if (!Number.isFinite(value) || value < 0 || value > 1) {
          throw new Error("Invalid hotspot coordinate for " + (hotspot.id || "unknown"));
        }
      });
    });
  }

  async function init() {
    const root = document.querySelector("[data-console-manifest]");
    if (!root) return;
    const manifestPath = root.getAttribute("data-console-manifest");
    state.adapter = new window.PubCastStudioConsoleHotspots.StudioConsoleHotspots();

    const response = await fetch(manifestPath);
    state.manifest = await response.json();
    validateManifest(state.manifest);

    const frame = el("div", { className: "pc-console-frame" });
    const image = el("img", {
      className: "pc-console-image",
      src: state.manifest.image.clean_path,
      alt: state.manifest.console_id,
      width: String(state.manifest.image.width_px),
      height: String(state.manifest.image.height_px),
    });
    const layer = el("div", { className: "pc-console-layer" });
    state.manifest.hotspots.forEach((hotspot) => layer.appendChild(renderHotspot(hotspot)));
    frame.appendChild(image);
    frame.appendChild(layer);
    root.appendChild(frame);

    const meta = document.querySelector("[data-console-meta]");
    if (meta) {
      meta.textContent = state.manifest.console_id + " map " + state.manifest.image.width_px + " x " + state.manifest.image.height_px;
    }
    setStatus("Console ready.");
  }

  window.PubCastConsoleHotspotRenderer = { init: init, validateManifest: validateManifest };
  document.addEventListener("DOMContentLoaded", () => init().catch((err) => setStatus(err.message || String(err), true)));
})();
