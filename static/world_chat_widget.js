/* One shared PubCast world room; never touches 2i documents or private chats. */
(() => {
  'use strict';
  const identity = () => (window.ReachAuth && window.ReachAuth.getUser()) || {};
  const clientName = () => identity().username || identity().user_id || localStorage.getItem('pubcast.clientId') || 'anon';
  const fetchRoom = async (url, options = {}) => {
    const response = await fetch(url, { ...options, cache: 'no-store', headers: {'Accept':'application/json', ...(options.headers || {})} });
    if (!response.ok) {
      let detail;
      try { detail = (await response.json()).detail; } catch (_) {}
      throw new Error(typeof detail === 'string' ? detail : `Room HTTP ${response.status}`);
    }
    return response.json();
  };
  function attach(root) {
    const log = root.querySelector('[data-world-messages]');
    const status = root.querySelector('[data-world-status]');
    const form = root.querySelector('[data-world-form]');
    const input = root.querySelector('[data-world-input]');
    const send = root.querySelector('[data-world-send]');
    let previous = '', inflight = false, sending = false, socket = null, pendingSend = null;
    function visible() { return root.getClientRects().length > 0 && (!root.closest('details') || root.closest('details').open); }
    async function refresh() {
      if (inflight || !visible() || document.hidden) return;
      inflight = true;
      try {
        const room = await fetchRoom('/api/chat/rooms/world?limit=100');
        const entries = Array.isArray(room.recent_messages) ? room.recent_messages : [];
        const snapshot = JSON.stringify(entries);
        if (snapshot !== previous) {
          const pinned = log.scrollHeight - log.scrollTop - log.clientHeight < 56;
          const items = document.createDocumentFragment();
          for (const message of entries) {
            const entry = document.createElement('article');
            entry.className = 'world-entry';
            entry.dataset.self = String(message.user_id === clientName());
            const who = document.createElement('strong');
            who.textContent = String(message.user || message.user_id || 'Participant');
            const text = document.createElement('span');
            text.textContent = String(message.text ?? '');
            entry.append(who, text);
            items.append(entry);
          }
          log.replaceChildren(items);
          previous = snapshot;
          if (pinned) log.scrollTop = log.scrollHeight;
        }
        const connected = socket && socket.readyState === WebSocket.OPEN;
        status.textContent = `World room · ${entries.length} recent messages · ${connected ? 'live' : 'reconnecting / refresh'}`;
      } catch (error) { status.textContent = `World Chat unavailable: ${error.message}`; }
      finally { inflight = false; }
    }
    function ensureSocket() {
      if (!visible() || document.hidden || socket || typeof WebSocket !== 'function') return;
      try {
        const path = '/ws/chat/world?client_id=' + encodeURIComponent(clientName());
        const href = window.ReachAuth ? window.ReachAuth.websocketURL(path) : (() => {
          const url = new URL(path, location.href);
          url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
          return url.href;
        })();
        const connected = new WebSocket(href);
        socket = connected;
        connected.onopen = refresh;
        connected.onmessage = event => {
          try {
            const payload = JSON.parse(event.data);
            if (payload.type === 'chat' || payload.type === 'history') refresh();
          } catch (_) { /* The REST transcript remains authoritative. */ }
        };
        connected.onclose = () => {
          if (socket === connected) { socket = null; refresh(); }
        };
        connected.onerror = () => { try { connected.close(); } catch (_) {} };
      } catch (_) { socket = null; } // REST polling remains a functioning fallback.
    }
    const download = root.querySelector('[data-world-export]') || document.querySelector('[data-world-export]');
    if (download) download.addEventListener('click', async () => {
      download.disabled = true;
      try {
        const response = await fetch('/api/chat/rooms/world/export', {cache:'no-store'});
        if (!response.ok) throw new Error(`Room log HTTP ${response.status}`);
        const blob = await response.blob();
        const objectURL = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = objectURL;
        link.download = 'PubCast_World_Chat_full_log.jsonl';
        document.body.append(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(objectURL), 1000);
        status.textContent = 'Full world-room log downloaded.';
      } catch (error) { status.textContent = `Room log export failed: ${error.message}`; }
      finally { download.disabled = false; }
    });
    root.closest('details')?.addEventListener('toggle', ensureSocket);
    function newMessageId() {
      // A random v4 UUID is the durable server receipt key. Keep the same key
      // after a transport failure, but never reuse it for changed draft text.
      if (window.crypto?.randomUUID) return window.crypto.randomUUID();
      if (!window.crypto?.getRandomValues) throw new Error('Secure random IDs unavailable');
      const bytes = window.crypto.getRandomValues(new Uint8Array(16));
      bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
      const hex = Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
      return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
    }
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (sending || !input.value.trim()) return;
      const exact = input.value;
      if (!pendingSend || pendingSend.text !== exact) {
        try { pendingSend = {text:exact, id:newMessageId()}; }
        catch (error) { status.textContent = `Cannot prepare message: ${error.message}`; return; }
      }
      sending = true; send.disabled = true;
      try {
        const receipt = await fetchRoom('/api/chat/rooms/world/send', {method:'POST', headers:{'Content-Type':'application/json', 'X-Client-Id':clientName()},
          body:JSON.stringify({text:exact, client_message_id:pendingSend.id})});
        // An acknowledged retry is NOT a second message. Only clear text once
        // the server confirms that the original UUID was actually committed.
        if (input.value === exact) input.value = '';
        pendingSend = null;
        await refresh();
        if (receipt.duplicate) status.textContent = 'Message was already saved · no duplicate sent.';
        if (receipt.warnings?.length) status.textContent = `Message saved · ${receipt.warnings.join('; ')}`;
        input.focus();
      } catch (error) { status.textContent = `Delivery unconfirmed: ${error.message}. Check room history before resending; your draft is still here.`; }
      finally { sending = false; send.disabled = false; }
    });
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey) {event.preventDefault(); form.requestSubmit();}
    });
    refresh();
    ensureSocket();
    const timer = setInterval(() => { ensureSocket(); refresh(); }, 2000);
    window.addEventListener('pagehide', () => { clearInterval(timer); socket?.close(); }, {once:true});
    root.addEventListener('world-chat:refresh', refresh);
  }
  document.querySelectorAll('[data-world-chat]').forEach(attach);
})();
