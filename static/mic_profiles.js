/**
 * mic_profiles.js — Per-person mic profiles + cough button system
 *
 * Each participant on a mic gets:
 *   - A named profile (role: host / guest / crew)
 *   - An assignable cough key (held to mute, released to unmute)
 *   - Web Audio gain gate (client-side, zero-latency)
 *   - Visual cough indicator (can't miss it)
 *   - WebSocket flag to orchestrator: { type: "cough", user_id, active }
 *     → suppresses AI agent scheduling while active
 *
 * Conflict detection: warns if assigned key collides with known bindings
 * in the current page context (switcher, chat, etc.)
 *
 * Injects a "Mic Profiles" panel into #station-audio when the DOM is ready.
 */

(function () {
  'use strict';

  // ── Known key conflicts by page context ──────────────────────────────────
  const KNOWN_CONFLICTS = {
    ' ':      'Cut (Vision Mixer)',
    'Enter':  'Send chat message',
    'Tab':    'Focus navigation',
    'f':      'Fade (Vision Mixer)',
    't':      'Toggle on-air',
    '1':      'Camera 1 preview',
    '2':      'Camera 2 preview',
    '3':      'Camera 3 preview',
    '4':      'Camera 4 preview',
    '5':      'Camera 5 preview',
    '6':      'Camera 6 preview',
  };

  // Safe defaults by role
  const ROLE_DEFAULTS = {
    host:  '`',        // backtick — nothing else uses it
    guest: 'c',        // 'c' — easy to reach, rarely mapped
    crew:  'Shift',    // held modifier — won't type characters
  };

  const ROLE_LABELS = { host: 'Host', guest: 'Guest', crew: 'Crew' };

  // ── State ─────────────────────────────────────────────────────────────────
  let profiles = loadProfiles();   // { id -> MicProfile }
  let audioCtx = null;
  let gainNodes = {};              // { profileId -> GainNode }
  let coughActive = {};            // { profileId -> bool }
  let keyListeners = {};           // { profileId -> keydown/keyup handlers }
  let _ws = null;

  function loadProfiles() {
    try {
      const raw = localStorage.getItem('pubcast_mic_profiles');
      return raw ? JSON.parse(raw) : {};
    } catch (_) { return {}; }
  }

  function saveProfiles() {
    try { localStorage.setItem('pubcast_mic_profiles', JSON.stringify(profiles)); } catch (_) {}
  }

  function getOrCreateAudioCtx() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    return audioCtx;
  }

  // ── WebSocket (reuse studio WS if available, else hub) ───────────────────
  function getWS() {
    if (_ws && _ws.readyState === WebSocket.OPEN) return _ws;
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    _ws = new WebSocket(window.ReachAuth.websocketURL('/ws/main'));
    _ws.onclose = () => { _ws = null; };
    return _ws;
  }

  function sendCoughFlag(profileId, active) {
    const profile = profiles[profileId];
    if (!profile) return;
    const payload = JSON.stringify({
      type: 'cough',
      payload: { user_id: profileId, display_name: profile.name, active }
    });
    try {
      const ws = getWS();
      if (ws.readyState === WebSocket.OPEN) ws.send(payload);
    } catch (_) {}
    // Also POST so the server can log it
    fetch('/api/mic/cough', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
    }).catch(() => {});
  }

  // ── Cough gate ────────────────────────────────────────────────────────────
  function activateCough(profileId) {
    if (coughActive[profileId]) return;
    coughActive[profileId] = true;

    // Web Audio gain gate — instant, client-side
    const processedGain = window._micProcessorGains?.[profileId];
    if (processedGain) processedGain.gain.setTargetAtTime(0, processedGain.context.currentTime, 0.01);
    if (gainNodes[profileId]) {
      gainNodes[profileId].gain.setTargetAtTime(0, getOrCreateAudioCtx().currentTime, 0.01);
    }

    // Visual
    updateCoughIndicator(profileId, true);

    // Orchestrator flag
    sendCoughFlag(profileId, true);
  }

  function deactivateCough(profileId) {
    if (!coughActive[profileId]) return;
    coughActive[profileId] = false;

    const processedGain = window._micProcessorGains?.[profileId];
    if (processedGain) processedGain.gain.setTargetAtTime(1, processedGain.context.currentTime, 0.02);
    if (gainNodes[profileId]) {
      gainNodes[profileId].gain.setTargetAtTime(1, getOrCreateAudioCtx().currentTime, 0.02);
    }

    updateCoughIndicator(profileId, false);
    sendCoughFlag(profileId, false);
  }

  function updateCoughIndicator(profileId, active) {
    const card = document.getElementById(`mic-card-${profileId}`);
    if (!card) return;
    card.classList.toggle('coughing', active);
    const btn = card.querySelector('.cough-btn');
    if (btn) btn.textContent = active ? '🔇 MUTED' : '🎙 COUGH';
    const indicator = card.querySelector('.cough-indicator');
    if (indicator) indicator.style.display = active ? 'block' : 'none';
  }

  // ── Key binding ───────────────────────────────────────────────────────────
  function bindCoughKey(profileId) {
    unbindCoughKey(profileId);
    const profile = profiles[profileId];
    if (!profile || !profile.coughKey) return;

    const key = profile.coughKey;
    const isShift = key === 'Shift';

    const onDown = (e) => {
      const tag = document.activeElement?.tagName?.toLowerCase();
      if (['input', 'textarea', 'select'].includes(tag)) return;
      const pressed = isShift ? e.shiftKey && !e.key.match(/^[A-Z]$/) : e.key === key;
      if (pressed) { e.preventDefault(); activateCough(profileId); }
    };

    const onUp = (e) => {
      const released = isShift ? !e.shiftKey : e.key === key;
      if (released) deactivateCough(profileId);
    };

    document.addEventListener('keydown', onDown);
    document.addEventListener('keyup', onUp);
    keyListeners[profileId] = { onDown, onUp };
  }

  function unbindCoughKey(profileId) {
    const listeners = keyListeners[profileId];
    if (!listeners) return;
    document.removeEventListener('keydown', listeners.onDown);
    document.removeEventListener('keyup', listeners.onUp);
    delete keyListeners[profileId];
  }

  // ── Conflict detection ────────────────────────────────────────────────────
  function detectConflict(key) {
    return KNOWN_CONFLICTS[key] || null;
  }

  // ── CRUD ──────────────────────────────────────────────────────────────────
  function addProfile(name, role) {
    const id = `mic_${Date.now()}`;
    const coughKey = ROLE_DEFAULTS[role] || '`';
    profiles[id] = { id, name, role, coughKey };
    saveProfiles();
    bindCoughKey(id);
    renderProfiles();
    return id;
  }

  function updateProfileKey(profileId, newKey) {
    if (!profiles[profileId]) return;
    unbindCoughKey(profileId);
    profiles[profileId].coughKey = newKey;
    saveProfiles();
    bindCoughKey(profileId);
    renderProfiles();
  }

  function removeProfile(profileId) {
    unbindCoughKey(profileId);
    deactivateCough(profileId);
    window.micProcessor?.detach(profileId);
    delete profiles[profileId];
    delete coughActive[profileId];
    delete gainNodes[profileId];
    saveProfiles();
    renderProfiles();
  }

  // ── Render ────────────────────────────────────────────────────────────────
  function renderProfiles() {
    const container = document.getElementById('mic-profiles-list');
    if (!container) return;
    container.innerHTML = '';

    const profileList = Object.values(profiles);
    if (!profileList.length) {
      container.innerHTML = '<p class="muted small" style="padding:8px 0;">No mic profiles yet. Add a participant above.</p>';
      return;
    }

    profileList.forEach(profile => {
      const isCoughing = !!coughActive[profile.id];
      const conflict = detectConflict(profile.coughKey);

      const card = document.createElement('div');
      card.id = `mic-card-${profile.id}`;
      card.className = 'mic-card' + (isCoughing ? ' coughing' : '');
      card.innerHTML = `
        <div class="mic-card-header">
          <span class="mic-role-badge mic-role-${profile.role}">${ROLE_LABELS[profile.role]}</span>
          <span class="mic-name">${escHtml(profile.name)}</span>
          <div class="cough-indicator" style="display:${isCoughing ? 'block' : 'none'};">MIC OFF</div>
          <button class="mic-remove ghost" data-id="${profile.id}" title="Remove">✕</button>
        </div>
        <div class="mic-card-body">
          <div class="mic-key-row">
            <label class="muted small">Cough key</label>
            <div class="mic-key-display">${escHtml(profile.coughKey)}</div>
            <button class="ghost mic-assign-btn" data-id="${profile.id}">Reassign</button>
            ${conflict ? `<span class="mic-conflict-warn" title="Conflict: ${escHtml(conflict)}">⚠ conflicts with ${escHtml(conflict)}</span>` : ''}
          </div>
          <div class="mic-key-row" style="margin-top:6px;">
            <span class="muted small">Hold <kbd>${escHtml(profile.coughKey)}</kbd> to mute mic. Release to unmute.</span>
          </div>
          <div class="mic-card-actions">
            <button class="cough-btn${isCoughing ? ' coughing' : ''}" data-id="${profile.id}">
              ${isCoughing ? '🔇 MUTED' : '🎙 COUGH'}
            </button>
          </div>
        </div>
      `;
      container.appendChild(card);
    });

    // Wire card buttons
    container.querySelectorAll('.mic-remove').forEach(btn => {
      btn.addEventListener('click', () => removeProfile(btn.dataset.id));
    });

    container.querySelectorAll('.cough-btn').forEach(btn => {
      btn.addEventListener('mousedown', () => activateCough(btn.dataset.id));
      btn.addEventListener('mouseup', () => deactivateCough(btn.dataset.id));
      btn.addEventListener('mouseleave', () => deactivateCough(btn.dataset.id));
      // Touch support
      btn.addEventListener('touchstart', (e) => { e.preventDefault(); activateCough(btn.dataset.id); });
      btn.addEventListener('touchend', (e) => { e.preventDefault(); deactivateCough(btn.dataset.id); });
    });

    container.querySelectorAll('.mic-assign-btn').forEach(btn => {
      btn.addEventListener('click', () => startKeyCapture(btn.dataset.id));
    });
  }

  // ── Key capture ───────────────────────────────────────────────────────────
  function startKeyCapture(profileId) {
    const card = document.getElementById(`mic-card-${profileId}`);
    if (!card) return;
    const display = card.querySelector('.mic-key-display');
    const original = display.textContent;
    display.textContent = '[ press key ]';
    display.classList.add('capturing');

    function onKey(e) {
      e.preventDefault();
      e.stopPropagation();
      let key = e.key;
      if (key === 'Escape') {
        display.textContent = original;
        display.classList.remove('capturing');
        document.removeEventListener('keydown', onKey, true);
        return;
      }
      // Normalize
      if (key === ' ') key = 'Space';

      const conflict = detectConflict(key === 'Space' ? ' ' : key);
      if (conflict) {
        const confirmed = window.confirm(
          `"${key}" is already used for: ${conflict}\n\nAssign it anyway?`
        );
        if (!confirmed) {
          display.textContent = original;
          display.classList.remove('capturing');
          document.removeEventListener('keydown', onKey, true);
          return;
        }
      }

      document.removeEventListener('keydown', onKey, true);
      updateProfileKey(profileId, key === 'Space' ? ' ' : key);
    }

    document.addEventListener('keydown', onKey, true);
  }

  // ── Add profile form ──────────────────────────────────────────────────────
  function buildAddForm() {
    const form = document.getElementById('mic-add-form');
    if (!form) return;
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const name = document.getElementById('mic-add-name').value.trim();
      const role = document.getElementById('mic-add-role').value;
      if (!name) return;
      addProfile(name, role);
      document.getElementById('mic-add-name').value = '';
    });
  }

  // ── Panel injection ───────────────────────────────────────────────────────
  function injectPanel() {
    const audioStation = document.getElementById('station-audio');
    if (!audioStation) return;

    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.id = 'mic-profiles-panel';
    panel.innerHTML = `
      <h3>Mic Profiles &amp; Cough Button</h3>
      <p class="muted small" style="margin-bottom:10px;">
        Add everyone on a mic. Each person gets their own cough key —
        hold it to drop off air, release to come back. The AI holds
        while any mic is down.
      </p>

      <form id="mic-add-form" class="row" style="gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px;">
        <input id="mic-add-name" placeholder="Name (e.g. Josie)" style="min-width:160px;" required />
        <select id="mic-add-role">
          <option value="host">Host</option>
          <option value="guest">Guest</option>
          <option value="crew">Crew</option>
        </select>
        <button type="submit">Add</button>
      </form>

      <div id="mic-profiles-list"></div>
    `;

    audioStation.appendChild(panel);

    injectStyles();
    buildAddForm();
    renderProfiles();

    // Bind keys for any profiles loaded from storage
    Object.keys(profiles).forEach(id => bindCoughKey(id));
  }

  // ── Styles ────────────────────────────────────────────────────────────────
  function injectStyles() {
    if (document.getElementById('mic-profiles-styles')) return;
    const style = document.createElement('style');
    style.id = 'mic-profiles-styles';
    style.textContent = `
      #mic-profiles-panel h3 {
        font-size: .85rem;
        letter-spacing: .12em;
        text-transform: uppercase;
        color: var(--gold, #c9a84c);
        margin-bottom: 6px;
      }

      .mic-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        margin-bottom: 10px;
        overflow: hidden;
        transition: border-color .2s, box-shadow .2s;
      }
      .mic-card.coughing {
        border-color: #cc2200;
        box-shadow: 0 0 16px rgba(204,34,0,0.35);
        animation: cough-pulse 0.8s ease-in-out infinite;
      }
      @keyframes cough-pulse {
        0%, 100% { box-shadow: 0 0 12px rgba(204,34,0,0.3); }
        50%       { box-shadow: 0 0 28px rgba(204,34,0,0.65); }
      }

      .mic-card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        background: rgba(255,255,255,0.04);
        border-bottom: 1px solid rgba(255,255,255,0.06);
      }
      .mic-name {
        font-weight: 600;
        font-size: .85rem;
        flex: 1;
        color: #e8e8e8;
      }

      .cough-indicator {
        background: #cc2200;
        color: #fff;
        font-size: .65rem;
        font-weight: 700;
        letter-spacing: .18em;
        padding: 3px 8px;
        border-radius: 3px;
        animation: blink-indicator 1s step-end infinite;
      }
      @keyframes blink-indicator {
        0%, 100% { opacity: 1; }
        50%       { opacity: 0.2; }
      }

      .mic-role-badge {
        font-size: .65rem;
        font-weight: 700;
        letter-spacing: .14em;
        text-transform: uppercase;
        padding: 2px 7px;
        border-radius: 3px;
      }
      .mic-role-host  { background: rgba(201,168,76,0.2);  color: #c9a84c; }
      .mic-role-guest { background: rgba(0,229,204,0.15);  color: #00e5cc; }
      .mic-role-crew  { background: rgba(100,120,255,0.18); color: #8899ff; }

      .mic-card-body {
        padding: 10px 12px;
      }
      .mic-key-row {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }
      .mic-key-display {
        font-family: 'Share Tech Mono', monospace, monospace;
        background: rgba(0,0,0,0.4);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 4px;
        padding: 3px 10px;
        font-size: .8rem;
        color: #00e5cc;
        min-width: 32px;
        text-align: center;
        transition: background .15s, color .15s;
      }
      .mic-key-display.capturing {
        background: rgba(201,168,76,0.15);
        color: #c9a84c;
        border-color: #c9a84c;
        animation: key-capture-pulse 0.6s ease-in-out infinite;
      }
      @keyframes key-capture-pulse {
        0%, 100% { opacity: 1; }
        50%       { opacity: 0.5; }
      }

      kbd {
        font-family: 'Share Tech Mono', monospace;
        background: rgba(255,255,255,0.1);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 3px;
        padding: 1px 5px;
        font-size: .75rem;
      }

      .mic-conflict-warn {
        font-size: .7rem;
        color: #f0a500;
        cursor: help;
      }

      .mic-card-actions {
        margin-top: 10px;
      }

      .cough-btn {
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .1em;
        padding: 7px 18px;
        border-radius: 5px;
        background: rgba(0,229,204,0.12);
        border: 1px solid rgba(0,229,204,0.3);
        color: #00e5cc;
        cursor: pointer;
        transition: background .1s, border-color .1s, transform .08s;
        user-select: none;
        -webkit-user-select: none;
      }
      .cough-btn:active,
      .cough-btn.coughing {
        background: rgba(204,34,0,0.25);
        border-color: #cc2200;
        color: #ff6644;
        transform: scale(0.97);
      }
      .cough-btn:hover {
        background: rgba(0,229,204,0.2);
      }

      .mic-remove {
        font-size: .75rem;
        padding: 2px 6px;
        opacity: 0.45;
        transition: opacity .15s;
      }
      .mic-remove:hover { opacity: 1; color: #e03e3e; }
    `;
    document.head.appendChild(style);
  }

  // ── Utility ───────────────────────────────────────────────────────────────
  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Boot ──────────────────────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectPanel);
  } else {
    injectPanel();
  }

  // Public API for console debugging / integration
  window.micProfiles = {
    add: addProfile,
    remove: removeProfile,
    list: () => Object.values(profiles),
    cough: activateCough,
    release: deactivateCough,
  };

})();
