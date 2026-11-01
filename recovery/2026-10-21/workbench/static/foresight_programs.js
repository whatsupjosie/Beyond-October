/* Foresight Programs — everything PubCast can open in a tray, and how each one is put on its screen.

   This is the content provider for the Foresight Counter (foresight_counter.js). The counter owns each tray's
   physical life (where it sits, its shape and frame, how it is pushed, squeezed, locked, put away, closed into the
   fan); this module owns what is inside: the programs, rooms, tools, chats, web pages, videos and files, and their
   own working state. "A tray's physical state belongs to the tray. Its functional state belongs to its contents."
   (Josie, 2026-10-14.)

   The program list and the way each kind is mounted come from the earlier Foresight page (foresight.html, which is
   kept as it was): the same addresses, the same live status polling, the same Iteration Wallet check, the same
   browser, video, recording and file handling, the same messages from the pages inside trays. What is new is that
   each content also says what it needs from its tray: its natural size, the smallest size at which it stays usable,
   and the general shape it reads best in.

   Usage (see foresight_counter.html):
     const programs = ForesightPrograms.create({config, toast, ask});
     const counter = ForesightCounter.create({..., provider: programs.provider});
     programs.bind(counter);
     programs.open(id, data)   open a program by id (a singleton already open is brought forward instead)
*/
(function(root){
  'use strict';

  const DEFAULT_CONFIG = {
    // PubPartner's canonical full-host spine lives inside Reach; pubpartnerBase may point at a deliberate remote host.
    pubpartnerBase: '',
    pubpartnerStatusPath: '/api/pubpartner/status',
    // Same-origin gateway to the BotManager and the optional 2i utilities; pages never call port 8787 directly.
    twoIBase: '/api/foresight/bridge',
    twoIUi: '/writers-room',
    // Iteration Wallet is a separate local program with its own server (START_ITERATION_WALLET.ps1, port 7432).
    iterationWalletUrl: 'http://127.0.0.1:7432/',
  };

  // The general shape each kind of content reads best in (the tray makes its own exact shape from it). Josie: no
  // squares or rectangles; wide rooms read as octagons, tall chats as hexagons, small panels as heptagons.
  const SHAPE = {room: 'octagon', wide: 'octagon', chat: 'hexagon', tool: 'pentagon', status: 'heptagon',
                 browser: 'octagon', video: 'heptagon', image: 'hexagon', pdf: 'pentagon', text: 'pentagon', list: 'hexagon'};
  const DARK = 'linear-gradient(165deg,#15110d,#090706)';

  // id, title, group, kind, address, natural size (w x h of its screen), smallest usable size, shape.
  const PROGRAMS = [
    // conversation and collaboration
    {id: 'world_chat', title: 'World Chat', group: 'Chat & Collaboration', kind: 'page', url: '/static/world_chat.html',
     w: 440, h: 520, minW: 320, minH: 360, shape: 'chat', singleton: true},
    {id: 'pubpartner_workspace', title: 'PubPartner · Alex & Cartridges', short: 'PubPartner', group: 'Programs', kind: 'page', url: '/pubpartner',
     w: 1000, h: 640, minW: 640, minH: 440, shape: 'wide', singleton: true},
    {id: 'twoi', title: "2i Writer's Room", short: '2i', group: 'Programs', kind: 'page', url: c => c.twoIUi,
     w: 980, h: 620, minW: 640, minH: 420, shape: 'wide', singleton: true},
    {id: 'iteration_wallet', title: 'Iteration Wallet', group: 'Programs', kind: 'external', url: c => c.iterationWalletUrl,
     w: 980, h: 620, minW: 600, minH: 400, shape: 'wide', singleton: true},
    {id: 'pubpartner_chat', title: 'Character Chat', group: 'Programs', kind: 'page', url: '/pub-partner-chat',
     w: 520, h: 560, minW: 360, minH: 380, shape: 'chat', singleton: true},
    {id: 'care_eq', title: 'CARE / EQ & Little Mode', short: 'CARE', group: 'Programs', kind: 'page', url: '/static/foresight_care.html',
     w: 640, h: 520, minW: 440, minH: 360, shape: 'tool', singleton: true},
    // studio rooms: direct work navigation, always available beside any walkable map
    {id: 'stage', title: 'Stage', group: 'Studio Rooms', kind: 'page', url: '/static/stage.html', w: 860, h: 560, minW: 520, minH: 360, shape: 'room', singleton: true},
    {id: 'panoramic', title: '360° Panoramic', group: 'Studio Rooms', kind: 'page', url: '/static/stage_panoramic.html', w: 860, h: 560, minW: 520, minH: 360, shape: 'room', singleton: true},
    {id: 'control_room', title: 'Control Room', group: 'Studio Rooms', kind: 'page', url: '/static/control_room.html', w: 860, h: 580, minW: 560, minH: 380, shape: 'room', singleton: true},
    {id: 'studio_control', title: 'Studio Control Room', group: 'Studio Rooms', kind: 'page', url: '/static/studio_control_room.html', w: 860, h: 580, minW: 560, minH: 380, shape: 'room', singleton: true},
    {id: 'director', title: 'Director Switcher', group: 'Studio Rooms', kind: 'page', url: '/static/director_switcher.html', w: 860, h: 580, minW: 560, minH: 380, shape: 'room', singleton: true},
    {id: 'world', title: 'World', group: 'Studio Rooms', kind: 'page', url: '/static/world.html', w: 880, h: 580, minW: 520, minH: 360, shape: 'room', singleton: true},
    {id: 'pubworld_set', title: 'PubWorld Set', group: 'Studio Rooms', kind: 'page', url: '/static/pubworld_stage.html', w: 880, h: 580, minW: 520, minH: 360, shape: 'room', singleton: true},
    {id: 'bar', title: 'Bar', group: 'Studio Rooms', kind: 'page', url: '/static/bar.html', w: 780, h: 540, minW: 480, minH: 340, shape: 'room', singleton: true},
    {id: 'dressing', title: 'Dressing Room', group: 'Studio Rooms', kind: 'page', url: '/static/dressing.html', w: 780, h: 540, minW: 480, minH: 340, shape: 'room', singleton: true},
    {id: 'waiting_room', title: 'Waiting Room', group: 'Studio Rooms', kind: 'page', url: '/static/waiting_room.html', w: 720, h: 500, minW: 440, minH: 320, shape: 'room', singleton: true},
    {id: 'map', title: 'Map / Walk', group: 'Studio Rooms', kind: 'page', url: '/static/map.html', w: 780, h: 540, minW: 480, minH: 340, shape: 'room', singleton: true},
    // production tools
    {id: 'teleprompter', title: 'Teleprompter', group: 'Production Tools', kind: 'page', url: '/static/pubcast_teleprompter.html', w: 660, h: 480, minW: 420, minH: 300, shape: 'tool', singleton: true},
    {id: 'gallery', title: 'Gallery', group: 'Production Tools', kind: 'page', url: '/static/gallery.html', w: 660, h: 480, minW: 420, minH: 300, shape: 'tool', singleton: true},
    {id: 'analytics', title: 'Analytics', group: 'Production Tools', kind: 'page', url: '/static/analytics.html', w: 660, h: 460, minW: 420, minH: 300, shape: 'tool', singleton: true},
    {id: 'doctor', title: 'Doctor', group: 'Production Tools', kind: 'page', url: '/static/doctor.html', w: 600, h: 460, minW: 400, minH: 300, shape: 'tool', singleton: true},
    {id: 'recordings', title: 'Recordings', group: 'Production Tools', kind: 'recordings', w: 460, h: 460, minW: 320, minH: 300, shape: 'list', singleton: true},
    // live status of the services Foresight leans on
    {id: 'pubpartner_status', title: 'PubPartner Status', group: 'Status', kind: 'status', service: 'pubpartner', w: 380, h: 300, minW: 300, minH: 240, shape: 'status', singleton: true},
    {id: 'twoi_status', title: '2i Bridge Status', group: 'Status', kind: 'status', service: 'twoi', w: 380, h: 300, minW: 300, minH: 240, shape: 'status', singleton: true},
    // made per use: web pages, videos, files, chats
    {id: 'browser', title: 'Web Browser', group: 'Web & Media', kind: 'browser', w: 900, h: 600, minW: 480, minH: 320, shape: 'browser'},
    {id: 'video', title: 'Video', group: 'Web & Media', kind: 'video', w: 720, h: 420, minW: 320, minH: 190, shape: 'video', minScale: 0.5},
    {id: 'file', title: 'File', group: 'Web & Media', kind: 'file', w: 640, h: 480, minW: 260, minH: 200, shape: 'image', minScale: 0.5},
    {id: 'chat', title: 'Chat', group: 'Chat & Collaboration', kind: 'chat', w: 440, h: 520, minW: 320, minH: 360, shape: 'chat'},
  ];
  const byId = id => PROGRAMS.find(p => p.id === id) || null;

  // ---------------------------------------------------------------- small helpers
  const safeLabel = (v, fallback) => { const s = String(v || '').replace(/[<>]/g, '').trim(); return (s || fallback || '').slice(0, 80); };
  function el(tag, attrs, ...kids){
    const e = document.createElement(tag);
    for(const [k, v] of Object.entries(attrs || {})){ if(k === 'style') e.style.cssText = v; else if(k === 'class') e.className = v; else if(k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v); }
    for(const k of kids){ if(k == null) continue; e.appendChild(typeof k === 'string' ? document.createTextNode(k) : k); }
    return e;
  }
  // Only http(s) pages may be opened. A bare host gets https://; a path stays on this site. Anything else
  // (javascript:, data:, file:, blob:) is refused.
  function normalizeAddress(raw){
    let s = String(raw || '').trim();
    if(!s) throw new Error('Type a web address');
    if(s.startsWith('/')) return new URL(s, location.origin).href;
    if(!/^[a-z][a-z0-9+.-]*:/i.test(s)) s = 'https://' + s;
    let u; try{ u = new URL(s); }catch(e){ throw new Error('That is not a valid web address'); }
    if(u.protocol !== 'http:' && u.protocol !== 'https:') throw new Error('Only http and https addresses can be opened');
    if(!u.hostname) throw new Error('That address has no site name');
    return u.href;
  }
  function addressLabel(address){
    if(!address) return 'Web Browser';
    try{ const u = new URL(address); return u.origin === location.origin ? 'PubCast · ' + u.pathname : u.hostname.replace(/^www\./, ''); }
    catch(e){ return 'Web Browser'; }
  }
  function fileKind(name, mime){
    mime = mime || '';
    if(mime.startsWith('video/') || mime.startsWith('audio/') || /\.(mp4|webm|mov|m4v|ogv|mp3|wav|m4a|ogg|flac)$/i.test(name)) return 'video';
    if(mime.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp|svg|avif)$/i.test(name)) return 'image';
    if(mime === 'application/pdf' || /\.pdf$/i.test(name)) return 'pdf';
    if(mime.startsWith('text/') || /\.(txt|md|csv|json|log)$/i.test(name)) return 'text';
    return null;
  }
  // A cross-origin server cannot be inspected from here, but a no-cors request resolves when the server answers
  // and rejects when nothing is listening.
  async function reachable(url, ms){
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), ms || 2500);
    try{ await fetch(url, {mode: 'no-cors', cache: 'no-store', signal: ctl.signal}); return true; }
    catch(e){ return false; }
    finally{ clearTimeout(timer); }
  }

  // ---------------------------------------------------------------- the provider
  function create(opts){
    opts = opts || {};
    const config = Object.assign({}, DEFAULT_CONFIG, root.FORESIGHT_CONFIG || {}, opts.config || {});
    const toast = opts.toast || (t => console.log(t));
    let counter = null;
    const frames = new Map();     // iframe window -> content, for messages from pages inside trays
    const files = new WeakMap();  // content -> File (a picked file is never written to storage)
    const urlOf = p => typeof p.url === 'function' ? p.url(config) : p.url;

    function programFor(type){ return byId(type); }
    // A panel with a title, a few lines and buttons: used for "not running", "choose the file again" and errors.
    function panel(body, title, lines, actions){
      body.innerHTML = '';
      const wrap = el('div', {class: 'fp-panel'}, el('h3', {}, title));
      for(const l of [].concat(lines || [])) wrap.appendChild(typeof l === 'string' ? el('p', {}, l) : l);
      const row = el('div', {class: 'fp-acts'});
      for(const [label, fn] of actions || []) row.appendChild(el('button', {class: 'fp-btn', onclick: e => { e.stopPropagation(); fn(); }}, label));
      wrap.appendChild(row); body.appendChild(wrap);
      return wrap;
    }
    function frameFor(c, body, src, attrs){
      const f = el('iframe', Object.assign({allow: 'microphone; camera; autoplay; clipboard-read; clipboard-write; fullscreen', loading: 'eager'}, attrs || {}));
      f.src = src; body.appendChild(f);
      f.addEventListener('load', () => { try{ if(f.contentWindow) frames.set(f.contentWindow, c); }catch(e){} });
      c.frame = f;
      return f;
    }

    // --- what each content needs from its tray
    function describe(type, data){
      const p = programFor(type); if(!p) return null;
      data = data || {};
      let title = p.title, shape = p.shape, ink = 'light', bg = DARK;
      if(type === 'browser') title = data.address ? 'Browser · ' + addressLabel(data.address) : 'Web Browser';
      if(type === 'video') title = safeLabel(data.name, 'Video');
      if(type === 'chat') title = safeLabel(data.title, 'Chat');
      if(type === 'file'){ const k = fileKind(data.name || '', data.mime || ''); title = safeLabel(data.name, 'File'); shape = k || 'image'; if(k === 'text'){ ink = 'light'; } }
      if(type === 'video' || type === 'file') bg = '#050403';
      return {title, family: SHAPE[shape] || 'pentagon', w: p.w, h: p.h, minW: p.minW, minH: p.minH, minScale: p.minScale || 0.7, ink, bg};
    }

    // --- putting a content on its screen
    function mount(c, host){
      const p = programFor(c.type); if(!p) throw new Error('Unknown program: ' + c.type);
      c.data = c.data || {};
      const body = host.body; body.classList.add('fp-body');
      c.host = host;
      if(p.kind === 'page') frameFor(c, body, urlOf(p));
      else if(p.kind === 'external') mountExternal(c, body, p);
      else if(p.kind === 'status') mountStatus(c, body, p);
      else if(p.kind === 'browser') mountBrowser(c, body);
      else if(p.kind === 'video') mountVideo(c, body);
      else if(p.kind === 'file') mountFile(c, body);
      else if(p.kind === 'recordings') mountRecordings(c, body);
      else if(p.kind === 'chat') frameFor(c, body, '/general-chat?conversation=' + encodeURIComponent(c.data.conversationId || ''));
      return {destroy: () => release(c)};
    }
    function release(c){
      if(c.objectUrl){ URL.revokeObjectURL(c.objectUrl); c.objectUrl = null; }
      if(c.frame){ try{ frames.delete(c.frame.contentWindow); }catch(e){} try{ c.frame.src = 'about:blank'; }catch(e){} c.frame = null; }
      const v = c.body && c.body.querySelector('video'); if(v){ v.pause(); v.removeAttribute('src'); v.load(); }
      if(c.abort){ c.abort.abort(); c.abort = null; }
      if(c.poll){ clearTimeout(c.poll); c.poll = null; }
      c.stopped = true;
    }

    async function mountExternal(c, body, p){
      const url = urlOf(p);
      panel(body, p.title, 'Checking whether ' + p.title + ' is running…');
      const up = await reachable(url);
      if(c.stopped) return;
      if(!up){
        const code1 = el('code', {}, '.\\START_ITERATION_WALLET.ps1'), code2 = el('code', {}, url);
        panel(body, p.title + ' is not running', [
          'It is a separate program with its own server. Start it on this computer, then press Retry.',
          el('p', {}, 'In PowerShell, from the Iteration Wallet folder: ', code1),
          el('p', {}, 'Expected address: ', code2)],
          [['Retry', () => mountExternal(c, body, p)], ['Open in a new window', () => window.open(url, '_blank', 'noopener')]]);
        return;
      }
      body.innerHTML = '';
      frameFor(c, body, url, {allow: 'clipboard-read; clipboard-write'});
    }

    function mountStatus(c, body, p){
      body.innerHTML = '';
      const wrap = el('div', {class: 'fp-status'}, el('h3', {}, p.title), el('div', {class: 'fp-sub'}, 'Live status, asked of the real service every 4 seconds.'));
      const rows = el('div', {class: 'fp-rows'}, 'Connecting…'); wrap.appendChild(rows); body.appendChild(wrap);
      const url = p.service === 'pubpartner' ? config.pubpartnerBase + config.pubpartnerStatusPath : config.twoIBase + '/health';
      const row = (k, v, cls) => el('div', {class: 'fp-row'}, el('span', {}, k), el('span', cls ? {class: cls} : {}, String(v == null ? '—' : v)));
      async function tick(){
        if(c.stopped) return;
        try{
          const res = await fetch(url, {mode: 'cors'}); if(!res.ok) throw new Error('HTTP ' + res.status);
          const d = await res.json(); rows.innerHTML = '';
          if(p.service === 'pubpartner'){
            const list = v => Array.isArray(v) ? v.join(', ') : (v || '—');
            const vessel = d.vessel && typeof d.vessel === 'object' ? (d.vessel.status || d.vessel.state || 'mounted') : (d.vessel ? 'mounted' : '—');
            rows.append(row('Status', d.ok === false ? 'degraded' : (d.spine || d.status || 'ready'), 'fp-pill ok'), row('Spine', d.spine || d.service),
              row('Protocols', list(d.protocols || d.protocol)), row('Providers', list(d.providers)), row('Vessel', vessel));
          } else {
            const env = d.environment || {}, svc = d.services || {};
            rows.append(row('Status', d.status, 'fp-pill ok'), row('Service', d.service), row('Uptime', d.uptime != null ? d.uptime + 's' : null),
              row('Node', env.node_version), row('Characters', svc.character_count), row('Optional 2i utilities', svc.legacy_2i_utilities));
          }
        }catch(err){
          rows.innerHTML = '';
          rows.append(row('Status', 'unreachable', 'fp-pill bad'),
            el('div', {class: 'fp-err'}, String(err && err.message || err) + '. Is the ' + (p.service === 'pubpartner' ? 'Reach PubPartner spine' : 'Foresight character bridge') + ' running?'));
        }
        if(!c.stopped) c.poll = setTimeout(tick, 4000);
      }
      tick();
    }

    function mountBrowser(c, body){
      body.innerHTML = '';
      const addr = el('input', {class: 'fp-addr', type: 'text', spellcheck: 'false', autocomplete: 'off', placeholder: 'Type a web address and press Enter', 'aria-label': 'Web address'});
      const bar = el('div', {class: 'fp-webbar'},
        el('button', {class: 'fp-btn small', title: 'Reload', onclick: () => { if(c.data.address) frame.src = c.data.address; }}, '↻'), addr,
        el('button', {class: 'fp-btn small', title: 'Go', onclick: () => go(addr.value)}, 'Go'),
        el('button', {class: 'fp-btn small', title: 'Open in a normal browser window', onclick: () => { try{ window.open(normalizeAddress(c.data.address || addr.value), '_blank', 'noopener'); }catch(err){ toast(err.message); } }}, '↗'));
      const frame = el('iframe', {sandbox: 'allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-downloads allow-modals', referrerpolicy: 'strict-origin-when-cross-origin'});
      const note = el('div', {class: 'fp-note'}, 'Some sites refuse to be shown inside another page and stay blank here. Use ↗ to open those in a normal browser window.');
      body.append(el('div', {class: 'fp-web'}, bar, frame, note));
      c.frame = frame;
      function go(raw){
        let href; try{ href = normalizeAddress(raw); }catch(err){ toast(err.message); addr.focus(); return; }
        c.data.address = href; addr.value = href; frame.src = href;
        c.host.setTitle('Browser · ' + addressLabel(href)); c.host.changed();
      }
      addr.addEventListener('keydown', e => { if(e.key === 'Enter'){ e.preventDefault(); go(addr.value); } });
      if(c.data.address){ addr.value = c.data.address; frame.src = c.data.address; } else setTimeout(() => addr.focus(), 60);
    }

    function mountVideo(c, body){
      const d = c.data, file = files.get(c);
      if(d.type === 'file' && !file){
        panel(body, 'Choose the video again', ['Browsers do not keep access to files from your computer after the page reloads. Choose ' + (d.name || 'the file') + ' again to keep watching.'],
          [['Choose file…', () => pickInto(c)]]);
        return;
      }
      body.innerHTML = '';
      const video = el('video', {controls: '', playsinline: '', preload: 'metadata', class: 'fp-video'});
      video.addEventListener('error', () => {
        const code = video.error ? video.error.code : 0;
        panel(body, 'Video unavailable', code === 4 ? 'This browser cannot play this file or format.' : code === 2 ? 'The video stopped loading because of a network error.' : 'The video could not be played.',
          [['Choose another file…', () => pickInto(c)]]);
      });
      body.appendChild(video);
      if(d.type === 'file'){ if(c.objectUrl) URL.revokeObjectURL(c.objectUrl); c.objectUrl = URL.createObjectURL(file); video.src = c.objectUrl; }
      else if(d.type === 'url') video.src = d.url;
      else if(d.type === 'vod') loadRecording(c, body, video);
    }
    // Recordings are protected: a <video src> cannot send the Reach sign-in, so the file is fetched (signed in) and
    // played from memory.
    async function loadRecording(c, body, video){
      const ctl = new AbortController(); c.abort = ctl;
      try{
        const res = await fetch(c.data.url, {signal: ctl.signal}); if(!res.ok) throw new Error('HTTP ' + res.status);
        const blob = await res.blob(); if(c.stopped) return;
        if(c.objectUrl) URL.revokeObjectURL(c.objectUrl);
        c.objectUrl = URL.createObjectURL(blob); video.src = c.objectUrl;
      }catch(err){
        if(err.name === 'AbortError') return;
        panel(body, 'Recording unavailable', 'Could not load this recording: ' + (err.message || err), [['Retry', () => mountVideo(c, body)]]);
      }finally{ c.abort = null; }
    }

    async function mountFile(c, body){
      const d = c.data, file = files.get(c), kind = fileKind(d.name || '', d.mime || '');
      if(!file){
        panel(body, 'Choose the file again', ['Browsers do not keep access to files from your computer after the page reloads. Choose ' + (d.name || 'the file') + ' again to keep working with it.'],
          [['Choose file…', () => pickInto(c)]]);
        return;
      }
      body.innerHTML = '';
      if(c.objectUrl){ URL.revokeObjectURL(c.objectUrl); c.objectUrl = null; }
      if(kind === 'image'){
        c.objectUrl = URL.createObjectURL(file);
        const img = el('img', {alt: d.name || '', class: 'fp-img'}); img.src = c.objectUrl;
        img.addEventListener('error', () => panel(body, 'Image unavailable', 'This browser cannot show this image file.', [['Choose another file…', () => pickInto(c)]]));
        body.appendChild(img);
      } else if(kind === 'pdf'){
        c.objectUrl = URL.createObjectURL(file); frameFor(c, body, c.objectUrl, {title: d.name || 'Document'});
      } else if(kind === 'text'){
        if(file.size > 5*1024*1024){ panel(body, 'File too large to show', 'Text files over 5 MB are not shown in a tray.'); return; }
        const pre = el('pre', {class: 'fp-text'}); pre.textContent = await file.text(); body.appendChild(pre);
      } else panel(body, 'Cannot show this file', 'This kind of file cannot be shown in a tray.');
    }

    async function mountRecordings(c, body){
      panel(body, 'Recordings', 'Loading recordings…');
      try{
        const res = await fetch('/api/vod'); if(!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json(); if(c.stopped) return;
        const list = (data.files || []).filter(f => /\.(mp4|webm|mov|m4v|ogg|ogv|mp3|wav|m4a)$/i.test(f.name || ''));
        if(!list.length){ panel(body, 'Recordings', 'No playable recordings yet. Recordings made in the studio appear here.', [['Refresh', () => mountRecordings(c, body)]]); return; }
        const wrap = panel(body, 'Recordings', list.length + ' playable recording' + (list.length === 1 ? '' : 's') + '. Click one to open it in its own tray.', [['Refresh', () => mountRecordings(c, body)]]);
        const ul = el('div', {class: 'fp-list'});
        for(const f of list){
          const mb = f.size_bytes ? (f.size_bytes/1048576).toFixed(1) + ' MB' : '';
          ul.appendChild(el('button', {class: 'fp-item', onclick: () => openProgram('video', {type: 'vod', url: f.url, name: f.name})},
            el('span', {}, f.name), el('span', {class: 'fp-meta'}, [mb, f.ended_at ? String(f.ended_at).slice(0, 16).replace('T', ' ') : ''].filter(Boolean).join(' · '))));
        }
        wrap.appendChild(ul);
      }catch(err){
        if(c.stopped) return;
        panel(body, 'Recordings unavailable', 'Could not list recordings: ' + (err.message || err), [['Retry', () => mountRecordings(c, body)]]);
      }
    }

    // A file picked to go into an existing content (one asking for its file again).
    function pickInto(c){
      const input = el('input', {type: 'file', accept: 'image/*,video/*,audio/*,application/pdf,text/plain,.txt,.md,.csv,.json,.log'});
      input.addEventListener('change', () => {
        const f = input.files && input.files[0]; if(!f) return;
        const r = fromFile(f); if(!r){ toast('This file type cannot be shown in a tray: ' + f.name); return; }
        if(c.tray && counter){ counter.importInto(c.tray, r.type, r.data); }
      });
      input.click();
    }

    // --- a file from this computer: which content shows it. The file itself is kept in memory only.
    const pendingFiles = new Map();   // data object -> File, until the content is made from it
    function fromFile(file){
      const kind = fileKind(file.name, file.type);
      if(!kind) return null;
      const data = kind === 'video' ? {type: 'file', name: file.name, mime: file.type || ''} : {name: file.name, mime: file.type || ''};
      pendingFiles.set(data, file);
      return {type: kind === 'video' ? 'video' : 'file', data};
    }
    // claim a picked file for the content made from it (mount runs right after makeContent)
    const mountInner = mount;
    function mountWithFile(c, host){
      if(pendingFiles.has(c.data)){ files.set(c, pendingFiles.get(c.data)); pendingFiles.delete(c.data); }
      return mountInner(c, host);
    }

    // --- what is kept across reloads: the content's own data, never a file or a live object
    function serialize(c){
      const out = Object.assign({}, c.state || {});
      return out;
    }

    // --- Export: the content as a file to keep
    async function exportContent(c){
      const p = programFor(c.type), file = files.get(c);
      if(file) return {name: file.name, data: file, type: file.type};
      if(c.type === 'browser' && c.data.address){
        // a Windows internet shortcut: double-click it to open the page
        return {name: safeLabel(addressLabel(c.data.address), 'page') + '.url', data: '[InternetShortcut]\r\nURL=' + c.data.address + '\r\n', type: 'application/internet-shortcut'};
      }
      if(c.type === 'video' && c.data.type !== 'file' && c.objectUrl){
        const blob = await fetch(c.objectUrl).then(r => r.blob());
        return {name: c.data.name || 'video', data: blob, type: blob.type};
      }
      return {name: safeLabel(c.title || (p && p.title), 'tray') + '.json', type: 'application/json',
        data: JSON.stringify({kind: 'foresight.content', program: c.type, title: c.title, address: p && p.url ? urlOf(p) : undefined,
          data: Object.assign({}, c.data), exported: new Date().toISOString()}, null, 2)};
    }

    // --- the picker (New blade, File > Open, a tray's Import…)
    function catalog(){
      const items = [];
      const groups = ['Programs', 'Chat & Collaboration', 'Studio Rooms', 'Production Tools', 'Status'];
      for(const g of groups) for(const p of PROGRAMS.filter(x => x.group === g && !['browser', 'video', 'file', 'chat'].includes(x.id))){
        items.push({type: p.id, title: p.title, group: g === 'Chat & Collaboration' ? 'Programs' : g, hint: isOpen(p.id) ? 'Already open: brings it forward' : ''});
      }
      items.push({type: 'browser', title: 'Web browser', group: 'Trays', hint: 'Any web address, in a tray'});
      items.push({title: 'Video from a link…', group: 'Trays', hint: 'A direct link to a video file', run: askVideoUrl});
      items.push({title: 'New chat', group: 'Trays', hint: 'A new conversation in a tray', run: newChat});
      return items;
    }
    function isOpen(id){ return !!(counter && counter.trays.some(t => t.stack.some(c => c.type === id))); }
    function trayWith(id){ return counter ? counter.trays.find(t => t.stack.some(c => c.type === id)) : null; }
    // a singleton already open somewhere is brought forward (opened from the fan, brought back, shown) instead
    function bringForward(t, id){
      const k = t.stack.findIndex(c => c.type === id);
      if(t.closed) counter.reopen(t); else if(t.parked) counter.unpark(t); else counter.select(t);
      if(k >= 0 && t.active !== k && counter.show) counter.show(t, k);
      return t;
    }
    function beforeOpen(type, data, tray){
      const p = programFor(type);
      if(p && p.singleton){ const t = trayWith(type); if(t){ bringForward(t, type); toast(p.title + ' is already open in its own tray'); return false; } }
      return true;
    }
    function openProgram(id, data){
      if(!counter) return null;
      if(!beforeOpen(id, data, null)) return null;
      return counter.open(id, data || {});
    }

    async function askVideoUrl(){
      const raw = opts.ask ? await opts.ask({title: 'Open a video from a link', sub: 'A direct link to a video file (for example .mp4 or .webm). Pages like YouTube are web pages, not video files: open those in a web browser tray.',
        placeholder: 'https://…/video.mp4', validate: normalizeAddress}) : prompt('Video link');
      if(raw == null) return;
      const href = normalizeAddress(raw);
      openProgram('video', {type: 'url', url: href, name: decodeURIComponent(new URL(href).pathname.split('/').pop() || 'Video')});
    }
    async function newChat(){
      const clientId = (() => { try{ return localStorage.getItem('pubcast.clientId') || 'josie'; }catch(e){ return 'josie'; } })();
      const title = 'Chat · ' + new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
      try{
        const res = await fetch('/api/conversations', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Client-Id': clientId, 'X-Dev-Role': 'guest'}, body: JSON.stringify({title})});
        if(!res.ok) throw new Error('HTTP ' + res.status);
        const d = await res.json();
        openProgram('chat', {conversationId: d.conversation_id, title});
      }catch(err){
        // the conversation page can still create and save its own conversation
        openProgram('chat', {conversationId: '', title: 'New Chat'});
        toast('Chat opened; the conversation will be created inside it');
      }
    }

    // --- reload what a tray shows
    function reload(c){
      const p = programFor(c.type); if(!p) return;
      if(p.kind === 'page' && c.frame) c.frame.src = urlOf(p);
      else if(p.kind === 'chat' && c.frame) c.frame.src = c.frame.src;
      else if(p.kind === 'browser' && c.data.address && c.frame) c.frame.src = c.data.address;
      else if(p.kind === 'external') mountExternal(c, c.body, p);
      else if(p.kind === 'recordings') mountRecordings(c, c.body);
      else if(p.kind === 'video') mountVideo(c, c.body);
      else { toast('This tray refreshes itself'); return; }
      toast('Reloaded ' + c.title);
    }

    // --- messages from the pages inside trays (as the earlier Foresight page took them)
    addEventListener('message', e => {
      const c = frames.get(e.source); if(!c || !e.data || typeof e.data !== 'object') return;
      if(e.data.type === 'foresight:new-chat'){ newChat(); return; }
      if(e.data.type === 'foresight:open-conversation' && e.data.conversationId){ openProgram('chat', {conversationId: String(e.data.conversationId), title: safeLabel(e.data.title, 'Chat')}); return; }
      if(e.data.type === 'foresight:portal-conversation' && c.type === 'chat' && e.data.conversationId){
        c.data.conversationId = String(e.data.conversationId); c.data.title = safeLabel(e.data.title, c.title);
        c.host.setTitle(c.data.title); c.host.changed();
      }
    });

    const provider = {catalog, describe, mount: mountWithFile, serialize, exportContent, fromFile, beforeOpen};
    return {
      provider, programs: PROGRAMS, config, normalizeAddress, reload, newChat, askVideoUrl,
      bind(c){ counter = c; },
      open: openProgram,
      autostart(){ for(const p of PROGRAMS) if(p.autostart && !isOpen(p.id)) openProgram(p.id, {}); },
    };
  }

  root.ForesightPrograms = {create, PROGRAMS, fileKind, normalizeAddress, addressLabel, version: 1};
})(window);
