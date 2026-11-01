/**
 * switcher.js — Hardware-style camera switcher shortcuts
 * Keyboard bindings and optional T-bar UI for the control room.
 */
(function () {
  'use strict';

  // ── Keyboard shortcuts ────────────────────────────────────────────────────
  // Space / Enter   → CUT
  // 1-9             → Set preview to camera N
  // Shift+1-9       → Set program to camera N (bypasses preview)
  // T               → Toggle on-air

  let cameras = [];

  async function fetchCameras() {
    try {
      const r = await fetch('/api/cameras');
      const data = await r.json();
      // The route returns {cameras: [...], program, preview}; keep the list.
      cameras = Array.isArray(data) ? data : (Array.isArray(data.cameras) ? data.cameras : []);
    } catch (e) { /* silent */ }
  }

  async function setCameraPreview(idx) {
    const cam = cameras[idx];
    if (!cam) return;
    try {
      await fetch(`/api/cameras/preview/${encodeURIComponent(cam.source_id)}`, { method: 'POST' });
      if (window.sysChat) window.sysChat(`PVW → ${cam.name || cam.source_id}`);
    } catch (e) { /* silent */ }
  }

  async function setCameraProgram(idx) {
    const cam = cameras[idx];
    if (!cam) return;
    try {
      await fetch(`/api/cameras/program/${encodeURIComponent(cam.source_id)}`, { method: 'POST' });
      if (window.sysChat) window.sysChat(`PGM → ${cam.name || cam.source_id}`);
    } catch (e) { /* silent */ }
  }

  async function cut() {
    try {
      await fetch('/api/cameras/cut', { method: 'POST' });
      if (window.sysChat) window.sysChat('✂ CUT');
    } catch (e) { /* silent */ }
  }

  // With the shared key map (static/control_keys.js) the keys and the buttons are wired by static/control_switcher.js, and this
  // built-in set (Space/Enter = cut, 1-9 = preview, Shift+1-9 = program) is not used, so two handlers never fight over a key.
  if (!window.PubCastControlKeys) document.addEventListener('keydown', e => {
    // Never let an editing transport key switch live Program.
    if (document.getElementById('station-director')?.classList.contains('hidden')) return;
    if (e.ctrlKey || e.altKey || e.metaKey) return;
    const tag = (e.target?.tagName || document.activeElement?.tagName || '').toLowerCase();
    if (['input', 'textarea', 'select'].includes(tag)) return;

    const k = e.key;

    if (k === ' ' || k === 'Enter') { e.preventDefault(); cut(); return; }

    const digit = parseInt(k, 10);
    if (digit >= 1 && digit <= 9) {
      e.preventDefault();
      if (e.shiftKey) {
        setCameraProgram(digit - 1);
      } else {
        setCameraPreview(digit - 1);
      }
    }
  });

  // ── T-bar drag (if element #tbar exists) ─────────────────────────────────
  function initTBar() {
    const tbar = document.getElementById('tbar');
    if (!tbar) return;
    let dragging = false;

    tbar.addEventListener('mousedown', () => { dragging = true; });
    document.addEventListener('mouseup', () => {
      if (!dragging) return;
      dragging = false;
      const pct = parseInt(tbar.value, 10);
      if (pct >= 95) cut();
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    fetchCameras();
    initTBar();
    // Refresh camera list if production state changes
    document.addEventListener('production_state', fetchCameras);
  });

  window.switcherApi = { cut, setCameraPreview, setCameraProgram, fetchCameras };
})();
