/**
 * conference.js — Conference room presence + invite panel
 * Wires conference section in control.html to /api/rooms and WS events.
 */
(function () {
  'use strict';

  const $ = id => document.getElementById(id);

  let agentRooms = [];

  // ── Load orchestrator rooms ────────────────────────────────────────────────
  async function loadRooms() {
    try {
      const data = await fetch('/api/rooms').then(r => r.json());
      agentRooms = Array.isArray(data) ? data : [];
      renderRooms();
    } catch (e) {
      console.warn('rooms load failed', e);
    }
  }

  function renderRooms() {
    const el = $('conf-room-list');
    if (!el) return;
    el.innerHTML = '';
    if (!agentRooms.length) {
      el.innerHTML = '<div class="muted small">No agent rooms active.</div>';
      return;
    }
    agentRooms.forEach(room => {
      const div = document.createElement('div');
      div.style.cssText = 'padding:6px 0;border-bottom:1px solid #1e2b3d;';
      const agents = (room.agents || []).join(', ') || 'none';
      const humans = room.participants?.filter(p => p.role === 'human').length ?? 0;
      div.innerHTML = `
        <strong>${escHtml(room.room_name)}</strong>
        <span class="badge" style="margin-left:6px;">${agents}</span>
        <span class="muted small" style="margin-left:8px;">${humans} human(s)</span>
      `;
      el.appendChild(div);
    });
  }

  // ── Create room ────────────────────────────────────────────────────────────
  function initCreateRoom() {
    const btn = $('conf-create-btn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      const name = $('conf-room-name')?.value.trim();
      if (!name) return;
      try {
        await fetch('/api/rooms', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ room_name: name }),
        });
        $('conf-room-name').value = '';
        await loadRooms();
      } catch (e) {
        console.error('create room failed', e);
      }
    });
  }

  // ── Load agents ────────────────────────────────────────────────────────────
  async function loadAgents() {
    const sel = $('conf-agent-sel');
    if (!sel) return;
    try {
      const agents = await fetch('/api/agents').then(r => r.json());
      sel.innerHTML = '';
      (Array.isArray(agents) ? agents : []).forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.agent_id;
        opt.textContent = `${a.display_name} (${a.provider})`;
        sel.appendChild(opt);
      });
    } catch (e) { /* silent */ }
  }

  function escHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadRooms();
    loadAgents();
    initCreateRoom();
  });

  window.conferenceApi = { loadRooms, loadAgents };
})();
