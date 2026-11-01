/**
 * PubCast AI — basebar.js
 * The persistent bottom bar shown on all pages using base.html.
 * Shows: REC indicator, viewer count, room name, quick nav, WS status.
 */
(function() {
  'use strict';

  let _recActive  = false;
  let _recStart   = null;
  let _viewers    = 0;
  let _wsConnected = false;
  let _recTimer   = null;

  function fmt(secs) {
    const h = Math.floor(secs/3600);
    const m = Math.floor((secs%3600)/60);
    const s = Math.floor(secs%60);
    return h > 0
      ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
      : `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  }

  function updateRec() {
    const badge  = document.getElementById('bb-rec-badge');
    const timer  = document.getElementById('bb-rec-timer');
    if (!badge) return;
    if (_recActive) {
      badge.classList.add('live');
      badge.textContent = '● REC';
      const elapsed = _recStart ? Math.floor((Date.now() - _recStart) / 1000) : 0;
      if (timer) timer.textContent = fmt(elapsed);
    } else {
      badge.classList.remove('live');
      badge.textContent = '○ REC';
      if (timer) timer.textContent = '';
    }
  }

  function updateViewers() {
    const el = document.getElementById('bb-viewers');
    if (el) el.textContent = _viewers > 0 ? `${_viewers} viewer${_viewers===1?'':'s'}` : '';
  }

  function updateWs() {
    const el = document.getElementById('bb-ws');
    if (!el) return;
    el.textContent = _wsConnected ? '◉' : '◎';
    el.title = _wsConnected ? 'WebSocket connected' : 'WebSocket disconnected';
    el.style.color = _wsConnected ? '#00cc88' : '#e03e3e';
  }

  function init() {
    const bar = document.getElementById('pub-basebar');
    if (!bar) return;

    // Build the bar
    bar.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;">
        <span id="bb-rec-badge" style="display:inline-flex;align-items:center;gap:5px;
          background:rgba(60,20,20,0.8);color:#888;border-radius:12px;
          padding:3px 10px;font-size:11px;letter-spacing:0.12em;cursor:default;
          border:1px solid rgba(200,0,0,0.2);transition:all 0.3s;">○ REC</span>
        <span id="bb-rec-timer" style="font-size:11px;color:#f0a500;font-family:monospace;min-width:44px;"></span>
        <span id="bb-viewers" style="font-size:11px;color:#5c6478;"></span>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span id="bb-room" style="font-size:11px;color:#3a4058;letter-spacing:0.08em;text-transform:uppercase;"></span>
        <span id="bb-ws" style="font-size:14px;color:#3a4058;cursor:default;" title="WebSocket">◎</span>
        <button id="bb-mark" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
          border-radius:4px;color:#5c6478;font-size:10px;padding:2px 8px;cursor:pointer;
          letter-spacing:0.1em;transition:all 0.15s;" title="Drop a marker">MARK</button>
      </div>
    `;

    // Style the REC badge when live
    const style = document.createElement('style');
    style.textContent = `
      #bb-rec-badge.live {
        background: rgba(180,0,0,0.85) !important;
        color: #fff !important;
        border-color: rgba(255,60,60,0.5) !important;
        box-shadow: 0 0 10px rgba(200,0,0,0.4);
        animation: bb-pulse 1.4s ease-in-out infinite;
      }
      @keyframes bb-pulse {
        0%,100% { box-shadow: 0 0 10px rgba(200,0,0,0.4); }
        50%      { box-shadow: 0 0 20px rgba(255,40,40,0.7); }
      }
    `;
    document.head.appendChild(style);

    // Mark button
    document.getElementById('bb-mark').addEventListener('click', async () => {
      try {
        // Find active session from page state if available
        const sessionId = window.__activeSessionId;
        if (!sessionId) { window.pubConsole && window.pubConsole.warn('MARK','No active session'); return; }
        await fetch(`/api/recording/sessions/${sessionId}/marker`, {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ label: 'mark', operator: 'user' }),
        });
        window.pubConsole && window.pubConsole.ok('MARK','Marker dropped');
      } catch(e) { window.pubConsole && window.pubConsole.error('MARK', e.message); }
    });

    // Set room name from URL
    const room = location.pathname.replace('/','') || 'lobby';
    const el = document.getElementById('bb-room');
    if (el) el.textContent = room;

    // Start rec timer
    _recTimer = setInterval(updateRec, 1000);

    updateRec();
    updateViewers();
    updateWs();
  }

  // Listen for system events from ws
  window.addEventListener('pubcast:ws', e => {
    const ev = e.detail || {};
    switch(ev.type) {
      case 'recording_start':
        _recActive = true;
        _recStart  = Date.now();
        window.__activeSessionId = ev.payload && ev.payload.session_id;
        break;
      case 'recording_stop':
        _recActive = false;
        _recStart  = null;
        break;
      case 'presence':
        _viewers = ev.participants ? ev.participants.length : (ev.count || 0);
        updateViewers();
        break;
    }
  });

  window.addEventListener('pubcast:ws_open',  () => { _wsConnected = true;  updateWs(); });
  window.addEventListener('pubcast:ws_close', () => { _wsConnected = false; updateWs(); });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
