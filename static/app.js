/**
 * PubCast AI — app.js
 * Main application controller.
 * Requires ws.js and ui.js to be loaded first.
 */
(function initApp() {

  // ── WebSocket connection ────────────────────────────────────────────────
  const ROOM = 'main';
  const hub  = new WSHub(`/ws/${ROOM}`, {
    onOpen:  () => console.log('[pubcast] WS connected'),
    onClose: () => console.log('[pubcast] WS disconnected'),
    onEvent: onWsEvent,
  });

  function onWsEvent(ev) {
    // Forward to control_stations hook if present
    if (typeof window.__pubcastStationsHook === 'function') {
      window.__pubcastStationsHook(ev);
    }

    switch (ev.type) {
      case 'presence':
        window.uiSetPresence(ev.participants ? ev.participants.length : 0);
        ev.participants && renderRoster(ev.participants);
        break;
      case 'say':
        window.uiAppendChat(ev.sender_id, ev.text);
        break;
      case 'production_state':
        applyProductionState(ev.payload || ev);
        break;
      case 'stream_chunk':
        // agent streaming — append to last agent row or create new
        appendAgentChunk(ev.sender_id, ev.delta);
        break;
    }
  }

  // ── Production state ────────────────────────────────────────────────────
  async function loadProductionState() {
    try {
      const res = await fetch('/api/state/production');
      if (!res.ok) return;
      const state = await res.json();
      applyProductionState(state);
      populateControlForm(state);
    } catch (e) { console.warn('[pubcast] Could not load production state', e); }
  }

  function applyProductionState(s) {
    const onAir     = s.on_air || false;
    const lower     = s.lower_third || '';
    const camera    = s.camera || 'wide';
    const lighting  = s.lighting || 'normal';
    const isReplay  = s.mode === 'REPLAY';

    // Green room monitor
    const replay    = document.getElementById('replay-video');
    const liveBanner= document.getElementById('live-banner');
    const lowerEl   = document.getElementById('lower-third');
    const badge     = document.getElementById('program-badge');

    if (replay && liveBanner) {
      if (isReplay && s.replay_asset) {
        replay.src = `/assets/${s.replay_asset}`;
        replay.classList.remove('hidden');
        liveBanner.classList.add('hidden');
      } else {
        replay.classList.add('hidden');
        liveBanner.classList.toggle('hidden', !onAir);
      }
    }
    if (lowerEl)  lowerEl.textContent  = lower;
    if (badge)    badge.textContent    = onAir ? 'LIVE' : 'OFF';

    // Studio view
    const studioOnAir = document.getElementById('studio-onair');
    const studioLower = document.getElementById('studio-lower-third');
    const cameraMode  = document.getElementById('camera-mode');
    const lightMode   = document.getElementById('lighting-mode');

    if (studioOnAir) studioOnAir.classList.toggle('hidden', !onAir);
    if (studioLower) studioLower.textContent = lower;
    if (cameraMode)  cameraMode.textContent  = camera;
    if (lightMode)   lightMode.textContent   = lighting;
  }

  function populateControlForm(s) {
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    set('prod-mode',    s.mode    || 'LIVE');
    set('prod-onair',   String(!!s.on_air));
    set('prod-replay',  s.replay_asset || '');
    set('prod-lower',   s.lower_third  || '');
    set('prod-camera',  s.camera   || 'wide');
    set('prod-lighting',s.lighting || 'normal');
    const pre = document.getElementById('prod-json');
    if (pre) pre.textContent = JSON.stringify(s, null, 2);
  }

  // Control form submit
  const controlForm = document.getElementById('control-form');
  if (controlForm) {
    controlForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        mode:          document.getElementById('prod-mode')?.value,
        on_air:        document.getElementById('prod-onair')?.value === 'true',
        replay_asset:  document.getElementById('prod-replay')?.value || '',
        lower_third:   document.getElementById('prod-lower')?.value  || '',
        camera:        document.getElementById('prod-camera')?.value  || 'wide',
        lighting:      document.getElementById('prod-lighting')?.value || 'normal',
      };
      try {
        const res = await fetch('/api/state/production', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          const data = await res.json();
          populateControlForm(data.state || payload);
        }
      } catch (e) { console.error('[pubcast] Control push failed', e); }
    });
  }

  // ── Wardrobe / user state ───────────────────────────────────────────────
  async function loadUserState() {
    try {
      const res = await fetch('/api/state/user');
      if (!res.ok) return;
      const u = await res.json();
      const nameEl  = document.getElementById('displayName');
      const colorEl = document.getElementById('avatarColor');
      const badgeEl = document.getElementById('badge');
      if (nameEl  && u.display_name) nameEl.value  = u.display_name;
      if (colorEl && u.avatar_color) colorEl.value = u.avatar_color;
      if (badgeEl && u.badge)        badgeEl.value = u.badge;
      updateMirror(u);
    } catch (e) { console.warn('[pubcast] Could not load user state', e); }
  }

  function updateMirror(u) {
    const preview = document.getElementById('avatar-preview');
    const nameEl  = document.getElementById('name-preview');
    if (preview) preview.style.background = u.avatar_color || '#00e0ff';
    if (nameEl)  nameEl.textContent = u.display_name || 'You';
  }

  const wardrobeForm = document.getElementById('wardrobe-form');
  if (wardrobeForm) {
    wardrobeForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const u = {
        display_name: document.getElementById('displayName')?.value || '',
        avatar_color: document.getElementById('avatarColor')?.value || '#00e0ff',
        badge:        document.getElementById('badge')?.value        || '',
      };
      updateMirror(u);
      try {
        await fetch('/api/state/user', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(u),
        });
      } catch (e) { console.error('[pubcast] Wardrobe save failed', e); }
    });

    // Live mirror preview on color change
    document.getElementById('avatarColor')?.addEventListener('input', (e) => {
      const preview = document.getElementById('avatar-preview');
      if (preview) preview.style.background = e.target.value;
    });
  }

  // ── File upload ─────────────────────────────────────────────────────────
  const uploadForm = document.getElementById('upload-form');
  if (uploadForm) {
    uploadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const file    = document.getElementById('uploadFile')?.files[0];
      const target  = document.getElementById('uploadTarget')?.value || '';
      const resultEl= document.getElementById('upload-result');
      if (!file) return;
      const fd = new FormData();
      fd.append('file', file);
      if (target) fd.append('target', target);
      try {
        if (resultEl) resultEl.textContent = 'Uploading…';
        const res = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (resultEl) resultEl.textContent = res.ok ? `✓ ${data.filename || 'uploaded'}` : `✗ ${data.error || 'failed'}`;
      } catch (e) {
        if (resultEl) resultEl.textContent = '✗ Upload failed';
        console.error('[pubcast] Upload error', e);
      }
    });
  }

  // ── Chat ────────────────────────────────────────────────────────────────
  const chatForm = document.getElementById('chat-form');
  if (chatForm) {
    chatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const input = document.getElementById('chat-input');
      const text  = input?.value.trim();
      if (!text) return;
      hub.send({ type: 'chat', text, t: Date.now() / 1000 });
      window.uiAppendChat('You', text, 'self');
      if (input) input.value = '';
    });
  }

  // ── Roster ──────────────────────────────────────────────────────────────
  function renderRoster(participants) {
    const list = document.getElementById('roster');
    if (!list) return;
    list.innerHTML = '';
    participants.forEach(p => {
      const li = document.createElement('li');
      li.textContent = `${p.display_name || p.participant_id} (${p.role})`;
      list.appendChild(li);
    });
  }

  // ── Agent stream chunk accumulator ─────────────────────────────────────
  const _agentBuffers = {};
  function appendAgentChunk(senderId, delta) {
    const log = document.getElementById('chat-log');
    if (!log) return;
    let row = document.getElementById(`agent-stream-${senderId}`);
    if (!row) {
      row = document.createElement('div');
      row.id = `agent-stream-${senderId}`;
      row.className = 'chat-row agent';
      const name = document.createElement('span');
      name.className = 'chat-name';
      name.textContent = senderId + ': ';
      const msg = document.createElement('span');
      msg.className = 'agent-text';
      row.appendChild(name);
      row.appendChild(msg);
      log.appendChild(row);
      _agentBuffers[senderId] = '';
    }
    _agentBuffers[senderId] = (_agentBuffers[senderId] || '') + delta;
    const textEl = row.querySelector('.agent-text');
    if (textEl) textEl.textContent = _agentBuffers[senderId];
    log.scrollTop = log.scrollHeight;
  }

  // ── Bootstrap ───────────────────────────────────────────────────────────
  loadProductionState();
  loadUserState();

})();
