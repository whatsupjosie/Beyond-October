/**
 * PubCast AI — editor_ui.js
 * Control room editor UI helpers: scene editor, prop inspector, surface manager.
 * Requires ws.js and app.js to be loaded first.
 */
(function() {
  'use strict';

  // ── Scene editor ───────────────────────────────────────────────────────
  async function loadScenes() {
    const el = document.getElementById('scene-list');
    if (!el) return;
    try {
      const r = await fetch('/api/pubworld/scenes');
      const d = await r.json();
      el.innerHTML = (d.scenes || []).map(s => `
        <div class="scene-item" data-id="${s.scene_id}" style="
          display:flex;align-items:center;justify-content:space-between;
          padding:6px 10px;border-bottom:1px solid rgba(255,255,255,0.05);
          cursor:pointer;font-size:12px;
        " onclick="window.editorUI.selectScene('${s.scene_id}')">
          <span style="color:#dde0ec">${s.name || s.scene_id}</span>
          <span style="color:#4a5068;font-size:10px">${new Date(s.created_at*1000).toLocaleDateString()}</span>
        </div>
      `).join('') || '<div style="padding:10px;color:#4a5068;font-size:12px">No scenes yet</div>';
    } catch(e) { window.pubConsole && window.pubConsole.error('SCENE', e.message); }
  }

  async function selectScene(sceneId) {
    document.querySelectorAll('.scene-item').forEach(el => {
      el.style.background = el.dataset.id === sceneId
        ? 'rgba(0,224,255,0.08)' : 'transparent';
    });
    window.__activeSceneId = sceneId;
    window.pubConsole && window.pubConsole.log('SCENE', `Selected: ${sceneId}`);
    // Load props for this scene
    loadProps(sceneId);
  }

  async function loadProps(sceneId) {
    const el = document.getElementById('prop-list');
    if (!el) return;
    try {
      const url = sceneId ? `/api/pubworld/props?scene_id=${sceneId}` : '/api/pubworld/props';
      const r = await fetch(url);
      const d = await r.json();
      el.innerHTML = (d.props || []).map(p => `
        <div style="padding:5px 10px;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px;">
          <div style="color:#dde0ec">${p.label}</div>
          <div style="color:#4a5068;font-size:10px">${(p.blocks||[]).length} blocks</div>
        </div>
      `).join('') || '<div style="padding:10px;color:#4a5068;font-size:12px">No props</div>';
    } catch(e) {}
  }

  // ── Surface manager ────────────────────────────────────────────────────
  async function loadSurfaces(roomId) {
    const el = document.getElementById('surface-list');
    if (!el) return;
    try {
      const url = roomId ? `/api/surfaces?room_id=${roomId}` : '/api/surfaces';
      const r = await fetch(url);
      const d = await r.json();
      el.innerHTML = (d.surfaces || []).map(s => `
        <div style="padding:6px 10px;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="color:#dde0ec">${s.label}</span>
            <span style="color:#4a5068;font-size:10px">${s.kind}</span>
          </div>
          <div style="color:#4a5068;font-size:10px">Room: ${s.room_id} • ${s.media_mode}</div>
        </div>
      `).join('') || '<div style="padding:10px;color:#4a5068;font-size:12px">No surfaces</div>';
    } catch(e) {}
  }

  // Init
  function init() {
    loadScenes();
    // Re-load on WS events
    window.addEventListener('pubcast:ws', e => {
      const ev = e.detail || {};
      if (ev.type === 'surface_created' || ev.type === 'surface_deleted') loadSurfaces();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.editorUI = { loadScenes, selectScene, loadProps, loadSurfaces };
})();
