/**
 * PubCast AI — audio.js
 * Audio routing UI helpers: channel meters, matrix controls.
 * Ties into studio_control WebSocket at /ws/studio.
 */
(function() {
  'use strict';

  let _studioWs = null;

  function connectStudio() {
    if (_studioWs) return;
    _studioWs = new WebSocket(window.ReachAuth.websocketURL('/ws/studio'));

    _studioWs.onopen = () => {
      window.pubConsole && window.pubConsole.ok('AUDIO', 'Studio WS connected');
      window.dispatchEvent(new CustomEvent('pubcast:ws_open'));
    };

    _studioWs.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data);
        handleStudioEvent(ev);
      } catch(_) {}
    };

    _studioWs.onclose = () => {
      window.pubConsole && window.pubConsole.warn('AUDIO', 'Studio WS closed — retrying in 4s');
      _studioWs = null;
      setTimeout(connectStudio, 4000);
    };
  }

  function handleStudioEvent(ev) {
    if (ev.type === 'audio_matrix') {
      updateMeters(ev.channels || []);
    }
    if (ev.type === 'preflight_check') {
      const el = document.getElementById('preflight-status');
      if (el) {
        el.textContent = ev.passed ? '✓ ' + ev.message : '✗ ' + ev.message;
        el.style.color = ev.passed ? '#00cc88' : '#e03e3e';
      }
    }
  }

  function updateMeters(channels) {
    channels.forEach(ch => {
      const el = document.getElementById(`meter-${ch.id}`);
      if (el) {
        const pct = Math.round(ch.level * 100);
        el.style.width = pct + '%';
        el.style.background = pct > 80 ? '#e03e3e' : pct > 60 ? '#f0a500' : '#00cc88';
      }
    });
  }

  function runPreflight() {
    const el = document.getElementById('preflight-status');
    if (el) el.textContent = 'Running preflight…';
    fetch('/api/studio/preflight', { method: 'POST' })
      .then(r => r.json())
      .then(d => {
        if (el) {
          el.textContent = d.ok ? '✓ Preflight passed' : '✗ Preflight failed';
          el.style.color = d.ok ? '#00cc88' : '#e03e3e';
        }
        window.pubConsole && window.pubConsole[d.ok?'ok':'error']('AUDIO',
          d.ok ? 'Preflight passed' : 'Preflight failed');
      })
      .catch(e => window.pubConsole && window.pubConsole.error('AUDIO', e.message));
  }

  function init() {
    connectStudio();
    const btn = document.getElementById('btn-preflight');
    if (btn) btn.addEventListener('click', runPreflight);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.audioUI = { runPreflight, connectStudio };
})();
