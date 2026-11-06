(async function () {
  'use strict';
  const $ = id => document.getElementById(id);
  let socket = null, timer = null, room = null, pending = null, opening = 0;
  const status = message => { $('status').textContent = message; };
  const busy = value => { $('text').disabled = value; $('send').querySelector('button').disabled = value; };
  const draftKey = () => 'pubcast.dm.draft.' + (ReachAuth.getUser?.()?.username || 'participant') + '.' + room;

  function remember() {
    if (!room) return;
    try {
      if (!$('text').value && !pending) sessionStorage.removeItem(draftKey());
      else sessionStorage.setItem(draftKey(), JSON.stringify({ text: $('text').value, pending }));
    } catch (_) { status('This tab could not keep the draft. Keep it open until your message is confirmed.'); }
  }
  function restore() {
    pending = null; $('text').value = '';
    try {
      const kept = JSON.parse(sessionStorage.getItem(draftKey()) || 'null');
      if (kept && typeof kept.text === 'string' && kept.text.length <= 10000) {
        $('text').value = kept.text;
        if (kept.pending?.room === room && kept.pending.text === kept.text && typeof kept.pending.id === 'string') pending = kept.pending;
      }
    } catch (_) { status('The saved draft could not be read.'); }
  }
  function messageID() {
    if (crypto.randomUUID) return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
    const hex = [...bytes].map(byte => byte.toString(16).padStart(2, '0')).join('');
    return hex.slice(0, 8) + '-' + hex.slice(8, 12) + '-' + hex.slice(12, 16) + '-' + hex.slice(16, 20) + '-' + hex.slice(20);
  }
  async function api(path, body) {
    const response = await fetch('/api/chat/dm/' + path, { method: body ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined, cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Contact request failed');
    return data;
  }
  function button(text, action) {
    const element = document.createElement('button'); element.type = 'button'; element.textContent = text;
    element.onclick = () => Promise.resolve(action()).catch(error => status(error.message)); return element;
  }
  function line(target, text) { const row = document.createElement('article'); row.textContent = text; $(target).append(row); return row; }
  async function load() {
    const [requests, active, blocked] = await Promise.all([api('pending'), api('active'), api('blocked')]);
    for (const id of ['pending', 'active', 'blocked']) $(id).replaceChildren();
    for (const request of requests.requests) {
      const row = line('pending', request.from_display + ' · ' + request.from_user + ' · ' + request.message);
      for (const action of ['accept', 'decline']) row.append(button(action === 'accept' ? 'Accept contact' : 'Decline', async () => { await api(action + '/' + request.request_id, {}); await load(); }));
    }
    for (const contact of active.rooms) {
      const row = line('active', contact.other_user);
      row.append(button('Open conversation', () => open(contact)),
        button('End conversation', async () => { await api('revoke', { other_user: contact.other_user }); if (room === contact.dm_room) socket?.close(); await load(); }),
        button('Block contact', async () => { await api('block', { other_user: contact.other_user, blocked: true }); if (room === contact.dm_room) socket?.close(); await load(); }));
    }
    for (const person of blocked.people) line('blocked', person).append(button('Unblock', async () => { await api('block', { other_user: person, blocked: false }); await load(); }));
  }
  async function open(contact) {
    const generation = ++opening;
    remember(); const previous = socket; socket = null; previous?.close();
    const verified = await ReachAuth.verify();
    if (generation !== opening) return;
    if (!verified) throw Error('Sign in again before opening a private channel.');
    room = contact.dm_room; restore(); busy(false);
    $('conversation').hidden = false; $('who').textContent = 'Private conversation with ' + contact.other_user; $('log').replaceChildren();
    const current = new WebSocket(ReachAuth.websocketURL('/ws/chat/' + room)); socket = current;
    current.onopen = () => { if (socket === current) status(pending ? 'Private channel open. Resend the unconfirmed message to retry safely.' : 'Private channel open.'); };
    current.onclose = () => { if (socket === current) { busy(false); remember(); status(pending ? 'Private channel closed. Your unconfirmed message is kept for retry.' : 'Private channel closed.'); } };
    current.onerror = () => { if (socket === current) { busy(false); status('The private channel could not connect. Your draft is kept.'); } };
    current.onmessage = event => {
      if (socket !== current) return;
      try {
        const packet = JSON.parse(event.data);
        if (packet.type === 'chat_receipt' && pending && packet.payload?.client_message_id === pending.id) {
          if ($('text').value === pending.text) $('text').value = '';
          pending = null; busy(false); remember(); status('Private message confirmed.');
        }
        if (packet.type === 'error') { busy(false); status(packet.message || packet.payload?.msg || 'The message was not confirmed. Your draft is kept.'); }
        const messages = packet.type === 'history' ? packet.payload : packet.type === 'chat' ? [packet.payload] : [];
        for (const message of messages) { const row = document.createElement('p'); row.textContent = (message.user || message.user_id || 'Participant') + ': ' + (message.text || ''); $('log').append(row); }
        $('log').scrollTop = $('log').scrollHeight;
      } catch (_) { busy(false); status('An unreadable message was received. Your draft is kept.'); }
    };
  }
  $('request').onsubmit = async event => {
    event.preventDefault();
    try { const result = await api('request', { to_user: $('person').value.trim(), message: $('hello').value }); status(result.status === 'pending' ? 'Contact request sent.' : 'Contact channel is open.'); await load(); }
    catch (error) { status(error.message); }
  };
  $('refresh').onclick = () => load().catch(error => status(error.message));
  $('text').oninput = remember;
  $('send').onsubmit = event => {
    event.preventDefault();
    if (!socket || socket.readyState !== WebSocket.OPEN) { status('Open an accepted conversation first.'); return; }
    const text = $('text').value;
    if (!text.trim()) { status('Write a private message first.'); return; }
    if (!pending || pending.room !== room || pending.text !== text) pending = { id: messageID(), room, text };
    remember(); busy(true);
    try { socket.send(JSON.stringify({ type: 'chat', text, client_message_id: pending.id })); status('Sending private message…'); }
    catch (error) { busy(false); status('Message not confirmed. Your draft is kept.'); }
  };
  window.addEventListener('pagehide', () => { remember(); clearInterval(timer); socket?.close(); });
  try { const session = await ReachAuth.requireSession(location.pathname); if (session) { await load(); timer = setInterval(() => { if (!document.hidden) load().catch(error => status(error.message)); }, 10000); } }
  catch (error) { status(error.message); }
})();
