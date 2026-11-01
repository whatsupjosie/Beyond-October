/**
 * PubCast AI — ui.js
 * View switching (nav-btn / data-room) and chat drawer toggle.
 * Runs after DOM is ready; no external dependencies.
 */
(function initUI() {
  // ── View switching ──────────────────────────────────────────────────────
  document.querySelectorAll('.nav-btn[data-room]').forEach(btn => {
    btn.addEventListener('click', () => {
      const room = btn.dataset.room;
      document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      const target = document.getElementById(`view-${room}`);
      if (target) target.classList.remove('hidden');
      btn.classList.add('active');
      window.dispatchEvent(new CustomEvent('pubcast:view', { detail: { room } }));
    });
  });

  // Activate first nav button on load
  const first = document.querySelector('.nav-btn[data-room]');
  if (first) first.click();

  // ── Chat drawer ─────────────────────────────────────────────────────────
  const tab    = document.getElementById('drawer-tab');
  const drawer = document.getElementById('chat-drawer');
  if (tab && drawer) {
    tab.addEventListener('click', () => drawer.classList.toggle('open'));
  }

  // ── Presence display helper ─────────────────────────────────────────────
  window.uiSetPresence = function(count) {
    const el = document.getElementById('presence');
    if (el) el.textContent = `${count} online`;
  };

  // ── Chat log helper ─────────────────────────────────────────────────────
  window.uiAppendChat = function(sender, text, cls) {
    const log = document.getElementById('chat-log');
    if (!log) return;
    const row  = document.createElement('div');
    row.className = `chat-row${cls ? ' ' + cls : ''}`;
    const name = document.createElement('span');
    name.className = 'chat-name';
    name.textContent = sender + ': ';
    const msg  = document.createElement('span');
    msg.textContent = text;
    row.appendChild(name);
    row.appendChild(msg);
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  };
})();
