// PubCast AI — bots.js
// Strict boring-check hardening pass: replace zero-byte placeholder with
// a defensive control-room bot manager UI that degrades cleanly.
(function () {
  const $ = (id) => document.getElementById(id);
  const state = {
    bots: [],
    rooms: ["dressing", "green", "studio", "control", "conference", "pub"],
    busy: false,
  };

  function safeText(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[ch]));
  }

  function selectedValues(selectEl) {
    return Array.from(selectEl?.selectedOptions || []).map((opt) => opt.value);
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
      ...options,
    });
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const payload = await response.json();
        detail = payload.detail || JSON.stringify(payload);
      } catch (_) {}
      throw new Error(`${response.status} ${detail}`);
    }
    if (response.status === 204) return null;
    return response.json();
  }

  function setStatus(message, kind) {
    let el = $('bot-status');
    if (!el) {
      const anchor = $('bot-admin');
      if (!anchor) return;
      el = document.createElement('div');
      el.id = 'bot-status';
      el.style.margin = '8px 0';
      el.style.fontSize = '12px';
      el.style.color = '#b8c0cc';
      anchor.insertBefore(el, anchor.children[1] || null);
    }
    el.textContent = message || '';
    el.dataset.kind = kind || 'info';
  }

  function renderBotList() {
    const list = $('bot-list');
    const speakSelect = $('bot-speak-id');
    if (!list || !speakSelect) return;
    list.innerHTML = '';
    speakSelect.innerHTML = '<option value="">Select bot…</option>';
    for (const bot of state.bots) {
      const li = document.createElement('li');
      li.className = 'bot-item';
      li.style.display = 'flex';
      li.style.justifyContent = 'space-between';
      li.style.alignItems = 'center';
      li.style.gap = '8px';
      li.style.padding = '8px 0';
      li.style.borderBottom = '1px solid rgba(255,255,255,0.06)';
      li.innerHTML = `
        <div>
          <strong>${safeText(bot.display_name || bot.bot_id)}</strong>
          <div style="font-size:12px;color:#98a2b3;">
            ${safeText(bot.provider)} · ${safeText(bot.model)} · rooms: ${safeText((bot.rooms || []).join(', ') || 'none')}
          </div>
        </div>
      `;
      const deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.textContent = 'Delete';
      deleteBtn.className = 'ghost';
      deleteBtn.addEventListener('click', () => removeBot(bot.bot_id));
      li.appendChild(deleteBtn);
      list.appendChild(li);

      const opt = document.createElement('option');
      opt.value = bot.bot_id;
      opt.textContent = bot.display_name || bot.bot_id;
      speakSelect.appendChild(opt);
    }
    if (!state.bots.length) {
      const li = document.createElement('li');
      li.textContent = 'No bots registered yet.';
      li.style.color = '#98a2b3';
      li.style.padding = '8px 0';
      list.appendChild(li);
    }
  }

  async function loadRooms() {
    const roomsSelect = $('bot-rooms');
    if (!roomsSelect) return;
    try {
      const payload = await fetchJson('/api/rooms');
      const apiRooms = Array.isArray(payload?.rooms)
        ? payload.rooms.map((room) => room.room_id || room.id || room.slug).filter(Boolean)
        : [];
      const merged = Array.from(new Set([...state.rooms, ...apiRooms]));
      state.rooms = merged;
      roomsSelect.innerHTML = '';
      for (const room of merged) {
        const opt = document.createElement('option');
        opt.value = room;
        opt.textContent = room;
        roomsSelect.appendChild(opt);
      }
    } catch (err) {
      setStatus(`Room list unavailable: ${err.message}`, 'warn');
    }
  }

  async function loadBots() {
    state.busy = true;
    try {
      state.bots = await fetchJson('/api/bots');
      renderBotList();
      setStatus(`Loaded ${state.bots.length} bot${state.bots.length === 1 ? '' : 's'}.`, 'ok');
    } catch (err) {
      setStatus(`Bot list unavailable: ${err.message}`, 'error');
    } finally {
      state.busy = false;
    }
  }

  async function removeBot(botId) {
    if (!botId || state.busy) return;
    state.busy = true;
    try {
      await fetchJson(`/api/bots/${encodeURIComponent(botId)}`, { method: 'DELETE' });
      await loadBots();
      setStatus(`Deleted bot ${botId}.`, 'ok');
    } catch (err) {
      setStatus(`Delete failed: ${err.message}`, 'error');
    } finally {
      state.busy = false;
    }
  }

  async function handleRegister(event) {
    event.preventDefault();
    if (state.busy) return;
    const payload = {
      bot_id: $('bot-id')?.value?.trim(),
      display_name: $('bot-name')?.value?.trim(),
      provider: $('bot-provider')?.value,
      model: $('bot-model')?.value?.trim(),
      api_key_env: $('bot-key')?.value?.trim(),
      rooms: selectedValues($('bot-rooms')),
      system_prompt: $('bot-system')?.value || '',
      auto_reply: Boolean($('bot-auto')?.checked),
      mention_only: Boolean($('bot-mention')?.checked),
      shadow_presence: Boolean($('bot-shadow')?.checked),
    };
    state.busy = true;
    try {
      await fetchJson('/api/bots', { method: 'POST', body: JSON.stringify(payload) });
      await loadBots();
      setStatus(`Saved bot ${payload.bot_id}.`, 'ok');
    } catch (err) {
      setStatus(`Save failed: ${err.message}`, 'error');
    } finally {
      state.busy = false;
    }
  }

  function handleSpeak(event) {
    event.preventDefault();
    const botId = $('bot-speak-id')?.value;
    const room = $('bot-speak-room')?.value || 'control';
    const text = $('bot-speak-text')?.value?.trim();
    if (!botId || !text) {
      setStatus('Choose a bot and enter text before speaking.', 'warn');
      return;
    }
    const input = $('chat-input');
    const roomSelect = $('chat-room');
    if (roomSelect) roomSelect.value = room;
    if (input) input.value = `[${botId}] ${text}`;
    const form = $('chat-form');
    if (form && typeof form.requestSubmit === 'function') {
      form.requestSubmit();
      setStatus(`Queued chat message for ${botId} in ${room}.`, 'ok');
    } else {
      setStatus('Chat form unavailable; could not route bot speech.', 'error');
    }
  }

  function init() {
    const form = $('bot-form');
    if (!form) return;
    loadRooms().finally(loadBots);
    form.addEventListener('submit', handleRegister);
    $('bot-reload')?.addEventListener('click', (event) => {
      event.preventDefault();
      loadBots();
    });
    $('bot-speak-btn')?.addEventListener('click', handleSpeak);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
