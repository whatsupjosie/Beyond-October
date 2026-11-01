/**
 * PubCast AI — console.js
 * Live system console overlay. Intercepts window events and WS messages.
 * Exposes window.pubConsole.log(tag, msg, level)
 */
(function() {
  'use strict';

  let _lines = [];
  const MAX = 200;

  function ts() {
    const d = new Date();
    return d.toTimeString().slice(0,8);
  }

  function render(el) {
    el.innerHTML = _lines.map(l =>
      `<div class="console-line">
        <span class="console-ts">${l.ts}</span>
        <span class="console-tag ${l.level}">${l.tag}</span>
        <span class="console-body">${escHtml(l.msg)}</span>
      </div>`
    ).join('');
    el.scrollTop = el.scrollHeight;
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g,'&amp;')
      .replace(/</g,'&lt;')
      .replace(/>/g,'&gt;');
  }

  function addLine(tag, msg, level) {
    _lines.push({ ts: ts(), tag: (tag||'SYS').toUpperCase().slice(0,6), msg: String(msg), level: level||'info' });
    if (_lines.length > MAX) _lines = _lines.slice(-MAX);
    const el = document.getElementById('pubcast-console');
    if (el) render(el);
  }

  function init() {
    // Create DOM
    const cons = document.createElement('div');
    cons.id = 'pubcast-console';
    document.body.appendChild(cons);

    const btn = document.createElement('button');
    btn.id = 'console-toggle';
    btn.textContent = '›_';
    btn.title = 'Toggle system console';
    document.body.appendChild(btn);

    btn.addEventListener('click', () => {
      cons.classList.toggle('open');
      btn.classList.toggle('active');
    });

    // Listen for pubcast system events
    window.addEventListener('pubcast:log', e => {
      const d = e.detail || {};
      addLine(d.tag, d.msg, d.level);
    });

    // Also catch WS events
    window.addEventListener('pubcast:ws', e => {
      const d = e.detail || {};
      addLine('WS', JSON.stringify(d).slice(0,120), 'ws');
    });

    // Initial hello
    addLine('SYS', 'PubCast AI v2.0 console ready', 'ok');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Public API
  window.pubConsole = {
    log:   (tag, msg) => addLine(tag, msg, 'info'),
    warn:  (tag, msg) => addLine(tag, msg, 'warn'),
    error: (tag, msg) => addLine(tag, msg, 'error'),
    ok:    (tag, msg) => addLine(tag, msg, 'ok'),
  };
})();
