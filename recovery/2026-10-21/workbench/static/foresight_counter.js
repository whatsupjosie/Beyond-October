/* Foresight Counter — the tray system as one module.

   A tray is a universal container (Josie, 2026-10-14): "A tray's physical state belongs to the tray. Its functional
   state belongs to its contents." The counter owns the physical side: where each tray sits, its shape and frame,
   how it is pushed, dented, squeezed, locked, put away, closed into the fan and opened out of it. What a tray shows
   comes from a content provider the page supplies; the counter never knows what a program is.

   Depends on foresight_shapes.js (ForesightShapes), foresight_chain.js (ForesightChain, the frame physics) and
   foresight_gl.js (ForesightGL, the renderer). No other libraries.

   ---- the content provider (supplied by the page) ----
     catalog()                      -> [{type, title, group, hint}]  what can be opened (the Import picker and New)
     describe(type, data)           -> {title, family, w, h, minW, minH, minScale?, ink?, bg?}
                                       title: plaque text; family: the general shape it reads best in
                                       (rhombus trapezoid pentagon hexagon heptagon octagon ellipse); w,h: natural size
                                       of its TV box; minW,minH: smallest size at which its text stays readable and its
                                       controls pressable; minScale: how far it may be squeezed (default 0.7);
                                       ink: 'light' or 'dark' text; bg: CSS background for the screen behind it
     mount(content, host)           build the content. host = {bg, body, setTitle(text), toast(text), changed()};
                                    content = {id, type, data, state}. Keep live state in content.state (JSON-able).
                                    May return {destroy()}.
     serialize(content)?            -> JSON-able state to keep across reloads (default: content.state)
     save(content)?                 the content's own Save (a document saving itself). Without it, Save keeps the
                                    counter (every tray, its contents and their state) in this browser.
     exportContent(content)?        -> {name, type, data (Blob|string)} a file for Export. Without it, Export gives a
                                    small JSON file of the content's kind, data and state.
     fromFile(file)?                -> {type, data} | null  how a file from this computer opens (Import > File…)

   ---- the counter ----
     const counter = ForesightCounter.create({canvas, gl, provider, theme, storageKey, top, looks, onEvent})
     counter.open(type, data, opts)  a new tray holding that content; its blade pops out of the fan and becomes it
     counter.importInto(tray, type, data)   load content into a tray (stacks on what is there; a blank is replaced)
     counter.close(tray) / reopen(tray) / discard(tray) / park(tray) / unpark(tray)
     counter.lock(tray, on) / lockAll(on) / reset(tray) / select(tray)
     counter.capture(tray) / fullScreen(tray) / exportTray(tray) / save(tray)
     counter.trays, counter.find(id), counter.serialize(), counter.setTheme(name), counter.destroy()

   Proposed, not owner-set, and easy to change: the menu wording, blade order (newest at the bottom of the fan),
   the squeeze floor (70%), the dock position (right edge), and Close keeping the tray's blade in the fan (dimmed,
   one click reopens it with its contents as they were; the blade's own x removes it for good).
*/
(function(root){
  'use strict';
  const S = root.ForesightShapes, Ch = root.ForesightChain, GLC = root.ForesightGL;
  if(!S || !Ch || !GLC) throw new Error('Foresight Counter needs foresight_shapes.js, foresight_chain.js and foresight_gl.js loaded first');
  const M = GLC.MAT;

  // ---------------------------------------------------------------- styles (injected once)
  const CSS = `
  .fc-root{position:fixed;inset:0;z-index:1;pointer-events:none}
  .fc-screen{position:absolute;pointer-events:auto;overflow:hidden;color:#f1e3c6;transition:opacity .18s}
  .fc-screen[data-ink=dark]{color:#2a2219}
  .fc-screen > .fc-bg{position:absolute;inset:0}
  .fc-screen > .fc-bg video{width:100%;height:100%;object-fit:cover;display:block}
  .fc-safe{position:absolute;transform-origin:0 0}
  .fc-content{position:absolute;inset:0}
  .fc-content > iframe{width:100%;height:100%;border:0;display:block;background:transparent}
  .fc-dragging .fc-screen iframe{pointer-events:none}
  .fc-screen.fc-full{left:0!important;top:0!important;width:100vw!important;height:100vh!important;clip-path:none!important}
  .fc-screen.fc-full > .fc-safe{left:0!important;top:0!important;width:100%!important;height:100%!important;transform:none!important}
  .fc-plaque{position:fixed;z-index:3;pointer-events:auto;transform-origin:50% 50%;cursor:grab;user-select:none;white-space:nowrap;
    font-family:var(--fs-font-display,serif);font-size:11px;letter-spacing:.2em;text-transform:uppercase;font-weight:700;color:#f6e7c4;
    text-shadow:0 1px 2px rgba(0,0,0,.7);transition:opacity .18s;touch-action:none}
  .fc-plaque:active{cursor:grabbing}
  .fc-knob{position:fixed;z-index:4;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;cursor:pointer;display:none;user-select:none;pointer-events:auto;
    background:radial-gradient(circle at 35% 30%,#fff3cf,#d6a54e 45%,#6b4512 100%);box-shadow:0 1px 3px rgba(0,0,0,.6);
    font:700 11px/18px var(--fs-font-display,serif);text-align:center;color:#3a2410;touch-action:none}
  .fc-knob.fc-grip{cursor:nwse-resize;box-shadow:0 1px 3px rgba(0,0,0,.6),inset 0 0 0 1px rgba(80,50,10,.6)}
  .fc-tag{position:fixed;z-index:3;transform-origin:50% 50%;cursor:pointer;user-select:none;white-space:nowrap;pointer-events:auto;
    font-family:var(--fs-font-display,serif);font-size:9.5px;letter-spacing:.16em;text-transform:uppercase;font-weight:700;color:#2b2016;text-shadow:0 1px 0 rgba(255,255,255,.55)}
  .fc-dock{position:fixed;z-index:3;width:150px;margin:-8px 0 0 -75px;text-align:center;cursor:pointer;user-select:none;pointer-events:auto;
    font-family:var(--fs-font-display,serif);font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#2b2016;
    text-shadow:0 1px 0 rgba(255,255,255,.6);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .fc-blade{position:fixed;z-index:2;transform-origin:0 50%;font-family:var(--fs-font-display,serif);font-size:11.5px;font-weight:700;letter-spacing:.06em;
    color:#2b2016;text-shadow:0 1px 0 rgba(255,255,255,.6);pointer-events:none;white-space:nowrap;max-width:118px;overflow:hidden;text-overflow:ellipsis}
  .fc-blade.fc-dim{color:#5b4a36;opacity:.8}
  .fc-menu{position:fixed;z-index:20;display:none;min-width:190px;padding:6px;border-radius:12px;pointer-events:auto;
    background:linear-gradient(170deg,#2c2118,#140e0a);box-shadow:0 8px 24px rgba(0,0,0,.55),inset 0 0 0 1px rgba(214,169,87,.45)}
  .fc-menu button{display:block;width:100%;text-align:left;background:none;border:0;border-radius:8px;padding:7px 10px;color:#f1e3c6;
    font:600 12.5px var(--fs-font-body,sans-serif);cursor:pointer}
  .fc-menu button:hover,.fc-menu button:focus{background:rgba(214,169,87,.16);outline:none}
  .fc-menu button[disabled]{opacity:.4;cursor:default}
  .fc-menu hr{border:0;border-top:1px solid rgba(214,169,87,.25);margin:5px 6px}
  .fc-veil{position:fixed;inset:0;z-index:30;display:none;place-items:center;background:rgba(10,6,3,.45);pointer-events:auto}
  .fc-veil.fc-open{display:grid}
  .fc-panel{max-width:min(720px,calc(100vw - 32px));max-height:calc(100vh - 64px);overflow:auto;padding:18px 20px;border-radius:18px;color:#f1e3c6;
    background:linear-gradient(170deg,#2c2118,#120c08);box-shadow:0 18px 50px rgba(0,0,0,.6),inset 0 0 0 1px rgba(214,169,87,.5);font:13px/1.45 var(--fs-font-body,sans-serif)}
  .fc-panel h3{margin:0 0 10px;font:700 13px var(--fs-font-display,serif);letter-spacing:.2em;text-transform:uppercase;color:#e9c987}
  .fc-panel .fc-sec{margin:12px 0 6px;font:700 10.5px var(--fs-font-display,serif);letter-spacing:.18em;text-transform:uppercase;color:#bfa06a}
  .fc-panel .fc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px}
  .fc-panel .fc-item{text-align:left;background:rgba(255,255,255,.05);border:0;border-radius:10px;padding:9px 11px;color:inherit;cursor:pointer;font:inherit}
  .fc-panel .fc-item:hover,.fc-panel .fc-item:focus{background:rgba(214,169,87,.18);outline:none}
  .fc-panel .fc-item b{display:block;font-weight:600} .fc-panel .fc-item span{opacity:.7;font-size:11.5px}
  .fc-panel .fc-row{display:flex;gap:8px;justify-content:flex-end;margin-top:14px;flex-wrap:wrap}
  .fc-panel .fc-btn{border:0;border-radius:10px;padding:8px 14px;cursor:pointer;font:600 12.5px var(--fs-font-body,sans-serif);background:rgba(255,255,255,.08);color:#f1e3c6}
  .fc-panel .fc-btn.fc-main{background:linear-gradient(180deg,#e2b866,#a8772a);color:#2a1a08}
  .fc-toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:40;padding:9px 16px;border-radius:12px;pointer-events:none;opacity:0;transition:opacity .2s;
    background:rgba(20,13,8,.92);color:#f1e3c6;font:600 12.5px var(--fs-font-body,sans-serif);box-shadow:0 6px 18px rgba(0,0,0,.5),inset 0 0 0 1px rgba(214,169,87,.4)}
  .fc-toast.fc-show{opacity:1}
  `;
  function injectCSS(){ if(document.getElementById('fc-css')) return; const s = document.createElement('style'); s.id = 'fc-css'; s.textContent = CSS; document.head.appendChild(s); }

  // ---------------------------------------------------------------- geometry helpers
  function hull(pts){
    pts = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    const cr = (o, a, b) => (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0]);
    const lo = [], up = [];
    for(const p of pts){ while(lo.length >= 2 && cr(lo[lo.length-2], lo[lo.length-1], p) <= 0) lo.pop(); lo.push(p); }
    for(const p of pts.slice().reverse()){ while(up.length >= 2 && cr(up[up.length-2], up[up.length-1], p) <= 0) up.pop(); up.push(p); }
    return S.geom.orient(lo.slice(0, -1).concat(up.slice(0, -1)));
  }
  const circlePts = (c, r, n) => Array.from({length: n}, (_, i) => [c[0] + Math.cos(i/n*Math.PI*2)*r, c[1] + Math.sin(i/n*Math.PI*2)*r]);
  function inPoly(P, x, y){ let inside = false; for(let i = 0, j = P.length - 1; i < P.length; j = i++){ const [xi, yi] = P[i], [xj, yj] = P[j]; if(((yi > y) !== (yj > y)) && x < (xj - xi)*(y - yi)/(yj - yi) + xi) inside = !inside; } return inside; }
  // a small hexagonal tag, set into the rim, carrying a name
  function plaquePoly(x, y, ang, w, h){
    const c = Math.cos(ang), s = Math.sin(ang), k = h/2;
    return S.geom.orient([[-w/2,0],[-w/2+k,-k],[w/2-k,-k],[w/2,0],[w/2-k,k],[-w/2+k,k]].map(([u, v]) => [x + u*c - v*s, y + u*s + v*c]));
  }
  const ease = x => x < 0.5 ? 4*x*x*x : 1 - Math.pow(-2*x + 2, 3)/2;
  const GLOW = {amber:[1.0,0.62,0.25,0.6], violet:[0.65,0.35,1.0,0.6], blue:[0.30,0.55,1.0,0.55], warm:[1.0,0.85,0.6,0.45],
                green:[0.25,0.9,0.55,0.5], red:[1.0,0.3,0.25,0.55], pearl:[0.9,0.9,1.0,0.4], ruby:[0.95,0.22,0.32,0.55], teal:[0.2,0.85,0.8,0.5],
                sapphire:[0.28,0.45,1.0,0.55], citrine:[1.0,0.78,0.32,0.5], emerald:[0.2,0.9,0.5,0.5], amethyst:[0.72,0.42,1.0,0.55]};
  // frames for trays the page gives no look of its own: [rim metal, glow, frame design 0..8], dealt in turn
  const LOOK_DECK = [[M.GOLD,'amber',4],[M.BRONZE,'violet',7],[M.STEEL,'blue',8],[M.NACRE,'warm',5],[M.SILVER,'green',6],[M.OPAL,'red',2],
                     [M.ROSE_GOLD,'ruby',1],[M.CHAMPAGNE,'sapphire',0],[M.COPPER,'teal',3],[M.BRASS,'citrine',6]];
  const FAMILIES = ['rhombus','trapezoid','pentagon','hexagon','heptagon','octagon','ellipse'];

  // ---------------------------------------------------------------- the counter
  function create(opt){
    injectCSS();
    const canvas = opt.canvas, G = opt.gl || new GLC(canvas), provider = opt.provider;
    if(!provider || !provider.describe || !provider.mount) throw new Error('Foresight Counter needs a content provider with describe() and mount()');
    const TOP = opt.top === undefined ? 70 : opt.top;              // the system bar's height: the counter starts below it
    const storageKey = opt.storageKey === undefined ? 'foresight.counter.v3' : opt.storageKey;
    const emit = (ev, data) => { try{ opt.onEvent && opt.onEvent(ev, data); }catch(e){ console.error(e); } };
    let theme = opt.theme || 'tigereye';
    const root = document.createElement('div'); root.className = 'fc-root'; (opt.root || document.body).appendChild(root);
    const trays = [];
    let selected = null, drag = null, sizing = null, anim = null, settle = 60, dirty = true, alive = true, nextId = 1, lookTurn = 0;
    let clock = () => performance.now();
    const parked = [];

    // ---------- contents
    // A blank tray is the counter's own: an empty tray waiting for something to be imported into it.
    const BLANK = {title: 'New Tray', family: 'pentagon', w: 340, h: 210, minW: 220, minH: 130, bg: 'linear-gradient(165deg,#2b2620,#0f0c09)'};
    function mountBlank(c){
      const wrap = document.createElement('div'); wrap.style.cssText = 'position:absolute;inset:0;display:grid;place-items:center;text-align:center;padding:14px;font-size:13px;line-height:1.5';
      const inner = document.createElement('div');
      const p = document.createElement('div'); p.style.opacity = '.75'; p.textContent = 'An empty tray. Bring anything into it.';
      const b = document.createElement('button'); b.textContent = 'Import\u2026'; b.className = 'fc-btn fc-main';
      b.style.cssText = 'margin-top:10px;border:0;border-radius:10px;padding:8px 16px;cursor:pointer;font:600 12.5px var(--fs-font-body,sans-serif);background:linear-gradient(180deg,#e2b866,#a8772a);color:#2a1a08';
      b.addEventListener('click', e => { e.stopPropagation(); if(c.tray) openPicker(c.tray); });
      inner.append(p, b); wrap.appendChild(inner); c.body.appendChild(wrap);
    }
    function describe(type, data){
      const own = type === 'blank' ? Object.assign({}, BLANK, (provider.describe(type, data) || {})) : provider.describe(type, data);
      const d = Object.assign({title: type, family: 'pentagon', w: 360, h: 240, minW: 200, minH: 130, minScale: 0.7, ink: 'light', bg: '#14100c'}, own || {});
      d.w = Math.max(d.w, d.minW); d.h = Math.max(d.h, d.minH);
      if(!FAMILIES.includes(d.family)) d.family = 'pentagon';
      return d;
    }
    function makeContent(type, data, state){
      const def = describe(type, data);
      const c = {id: 'c' + (nextId++), type, data: data === undefined ? null : data, state: state || {}, def, title: def.title};
      c.bg = document.createElement('div'); c.bg.className = 'fc-bg';
      if(def.bg) c.bg.style.background = def.bg;
      c.body = document.createElement('div'); c.body.className = 'fc-content';
      const host = {bg: c.bg, body: c.body, content: c,
        setTitle: text => { c.title = String(text || def.title).slice(0, 80); if(c.tray){ refreshPlaque(c.tray); renderSoon(); } },
        toast, changed: () => scheduleSave()};
      try{ c.handle = type === 'blank' ? mountBlank(c) || null : provider.mount(c, host) || null; }
      catch(err){ console.error(err); c.body.innerHTML = ''; const p = document.createElement('div'); p.style.cssText = 'padding:16px;font-size:13px'; p.textContent = 'This could not be opened: ' + (err && err.message || err); c.body.appendChild(p); }
      return c;
    }
    function destroyContent(c){ try{ c.handle && c.handle.destroy && c.handle.destroy(); }catch(e){ console.error(e); } c.bg.remove(); c.body.remove(); }
    const activeContent = t => t.stack[t.active];
    // the tray can never be smaller than the largest minimum among its contents
    function stackMin(t){ return {w: Math.max(...t.stack.map(c => c.def.minW)), h: Math.max(...t.stack.map(c => c.def.minH))}; }
    function stackMinScale(t){ return Math.max(...t.stack.map(c => c.def.minScale || 0.7)); }

    // ---------- trays
    function lookFor(t){
      if(opt.looks){ const l = opt.looks(t, theme); if(l) return l; }
      if(!t.look){ t.look = LOOK_DECK[lookTurn % LOOK_DECK.length]; lookTurn++; }
      return t.look;
    }
    function buildTray(spec){
      // spec: {id, contents:[{type,data,state}], x, y, w?, h?, family?, look?, saved?}
      const stack = spec.contents.map(c => makeContent(c.type, c.data, c.state));
      const first = stack[0].def, mn = {w: Math.max(...stack.map(c => c.def.minW)), h: Math.max(...stack.map(c => c.def.minH))};
      const w = Math.max(spec.w || first.w, mn.w), h = Math.max(spec.h || first.h, mn.h), family = spec.family || first.family;
      let t;
      if(spec.saved && spec.saved.unit0){
        // the very same outline it had: the shape is kept with the tray, not made again
        const sv = spec.saved;
        t = {id: spec.id, cx: spec.x, cy: spec.y, a: w/2, b: h/2, family: sv.family, requestedFamily: sv.requestedFamily || sv.family,
             unit0: sv.unit0, aspect0: sv.aspect0, reqW: w, reqH: h, scale: 1, pressure: 0};
        S.setBox(t, w, h);
      } else t = S.makeTray(spec.id, family, spec.x, spec.y, w, h);
      t.stack = stack; t.active = Math.min(spec.active || 0, stack.length - 1); t.locked = !!spec.locked;
      t.natural = spec.natural || {w: Math.max(first.w, mn.w), h: Math.max(first.h, mn.h), family: first.family};
      if(spec.look) t.look = spec.look;
      stack.forEach(c => { c.tray = t; });
      buildTrayDOM(t);
      showContent(t, t.active);
      Ch.attach(t, S);
      return t;
    }
    function buildTrayDOM(t){
      const el = document.createElement('div'); el.className = 'fc-screen';
      const safe = document.createElement('div'); safe.className = 'fc-safe';
      for(const c of t.stack){ el.appendChild(c.bg); safe.appendChild(c.body); }
      el.appendChild(safe); root.appendChild(el); t.el = el; t.safeEl = safe;
      const pl = document.createElement('div'); pl.className = 'fc-plaque'; pl.setAttribute('role', 'button'); pl.tabIndex = 0;
      root.appendChild(pl); t.plaque = pl;
      const knob = (cls, text, title, fn) => { const k = document.createElement('div'); k.className = 'fc-knob ' + cls; k.textContent = text; k.title = title; k.setAttribute('aria-label', title);
        k.addEventListener('pointerdown', e => { e.stopPropagation(); e.preventDefault(); fn(e); }); root.appendChild(k); return k; };
      t.grip = knob('fc-grip', '', 'Resize', e => startResize(e, t));
      t.closer = knob('', '×', 'Close into the fan', () => close(t));
      t.parker = knob('', '–', 'Put away', () => park(t));
      t.menuKnob = knob('', '⋯', 'Tray menu', e => openTrayMenu(t, e.clientX, e.clientY));
      pl.addEventListener('pointerdown', e => { if(e.button === 0) startDrag(e, t); });
      pl.addEventListener('dblclick', e => { e.preventDefault(); fullScreen(t); });
      pl.addEventListener('contextmenu', e => { e.preventDefault(); openTrayMenu(t, e.clientX, e.clientY); });
      pl.addEventListener('keydown', e => { if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); select(t); } if(e.key === 'ContextMenu' || (e.shiftKey && e.key === 'F10')){ e.preventDefault(); const r = pl.getBoundingClientRect(); openTrayMenu(t, r.left, r.bottom); } });
      el.addEventListener('pointerdown', () => { if(selected !== t){ selected = t; dirty = true; emit('select', t); } }, true);
      t.tags = [];
    }
    function refreshPlaque(t){ const c = activeContent(t); t.plaque.textContent = c.title; t.plaque.setAttribute('aria-label', c.title + ' tray'); }
    // Show one content of the stack; the others stay alive (hidden) with their state. Every other content gets a
    // small blade tucked under the plaque, to switch to it.
    function showContent(t, i){
      t.active = Math.max(0, Math.min(i, t.stack.length - 1));
      t.stack.forEach((c, k) => { c.bg.style.display = k === t.active ? '' : 'none'; c.body.style.display = k === t.active ? '' : 'none'; });
      const c = activeContent(t);
      t.el.dataset.ink = c.def.ink || 'light';
      refreshPlaque(t);
      for(const g of t.tags) g.remove();
      t.tags = t.stack.map((cc, k) => k).filter(k => k !== t.active).map(k => {
        const g = document.createElement('div'); g.className = 'fc-tag'; g.textContent = t.stack[k].title; g.title = 'Show ' + t.stack[k].title;
        g.addEventListener('pointerdown', e => { e.preventDefault(); e.stopPropagation(); showContent(t, k); scheduleSave(); });
        g.addEventListener('contextmenu', e => { e.preventDefault(); openTrayMenu(t, e.clientX, e.clientY); });
        root.appendChild(g); return g;
      });
      dirty = true;
    }
    function removeTrayDOM(t){ [t.el, t.plaque, t.grip, t.closer, t.parker, t.menuKnob, t.dockLabel].forEach(e => e && e.remove()); for(const g of t.tags) g.remove(); }

    // ---------- the scene: bounds, fan, lantern, dock
    const PIVOT = [62, 112];
    function bladeCount(){ return 1 + trays.length; }   // the New blade, then one per tray
    function bladeAngles(n){
      const span = 92, stepDeg = n > 1 ? Math.min(14.5, span/(n - 1)) : 0;
      return Array.from({length: n}, (_, i) => (2 + i*stepDeg)*Math.PI/180);
    }
    function bladePoly(a, pop){
      const dir = [Math.cos(a), Math.sin(a)];
      const c1 = [PIVOT[0] + dir[0]*(34 + pop), PIVOT[1] + dir[1]*(34 + pop)], c2 = [PIVOT[0] + dir[0]*(190 + pop), PIVOT[1] + dir[1]*(190 + pop)];
      return {q: hull(circlePts(c1, 9, 18).concat(circlePts(c2, 25, 30))), angle: a, tip: [PIVOT[0] + dir[0]*(200 + pop), PIVOT[1] + dir[1]*(200 + pop)], pop};
    }
    function lanternPoly(){
      const pts = [[PIVOT[0]-30, PIVOT[1]+40], [PIVOT[0]+30, PIVOT[1]+40]];
      for(let i = 0; i <= 16; i++){ const a = Math.PI + i/16*Math.PI; pts.push([PIVOT[0] + Math.cos(a)*30, PIVOT[1] - 6 + Math.sin(a)*38]); }
      return hull(pts);
    }
    const barPoly = W => S.geom.orient([[22,10],[W-22,10],[W-8,32],[W-22,54],[22,54],[8,32]]);
    function dockSlot(i){ return [innerWidth - 112, TOP + 34 + i*36]; }
    function dockTagPoly(i){ const [x, y] = dockSlot(i); return hull(circlePts([x - 78, y], 14, 16).concat(circlePts([x + 78, y], 14, 16))); }
    function bladeIndexOf(t){ return 1 + trays.indexOf(t); }
    function bladePop(){
      if(!anim || anim.blade === undefined) return {i: -1, pop: 0};
      const k = Math.min(1, (clock() - anim.t0)/anim.dur);
      // opening: the blade swings out first, then settles; closing: it ducks in as the tray arrives
      const pop = anim.kind === 'open' ? 26*Math.sin(Math.PI*Math.min(1, k*1.6)) : -10*Math.sin(Math.PI*k);
      return {i: anim.blade, pop};
    }
    function ctx(){
      const W = innerWidth, H = innerHeight;
      const bp = bladePop(), angles = bladeAngles(bladeCount());
      const blades = angles.map((a, i) => bladePoly(a, i === bp.i ? bp.pop : 0)), lantern = lanternPoly();
      const obstacles = [hull(blades.flatMap(b => b.q).concat(lantern))];
      if(parked.length) obstacles.push(hull(parked.flatMap((_, i) => dockTagPoly(i))));
      return {W, H, bounds: {x0: 0, y0: TOP, x1: W, y1: H}, blades, lantern, obstacles};
    }
    function physEnv(c){
      return {bounds: c.bounds, obstacles: c.obstacles, pad: S.FLOOR_PAD,
        rigid: t => t.locked || t === selected || (drag && drag.hand.t === t) || (sizing && sizing.t === t),   // the selected tray never dents
        coast: t => !t.locked && !(drag && drag.hand.t === t) && !(sizing && sizing.t === t),                   // but it can still glide after a flick; a locked one cannot
        locked: t => t.locked,
        minScale: t => stackMinScale(t),
        target: t => drag && drag.hand.t === t ? drag.hand.at : null};
    }

    // ---------- selecting, dragging, resizing
    function select(t){ if(t && (t.hidden || t.closed)) return; selected = t || null; dirty = true; settle = 30; emit('select', selected); }
    function startDrag(e, t){
      e.preventDefault(); hideMenu();
      if(selected !== t) select(t);
      if(t.locked || t.hidden){ return; }   // a locked tray is selected but stays exactly where it is
      G.quality = 'fast'; root.classList.add('fc-dragging');
      try{ e.target.setPointerCapture && e.target.setPointerCapture(e.pointerId); }catch(err){}
      drag = {hand: {t, want: [t.cx, t.cy], at: [t.cx, t.cy]}, dx: e.clientX - t.cx, dy: e.clientY - t.cy, trail: [[e.clientX, e.clientY, performance.now()]]};
      const move = ev => { drag.hand.want = [ev.clientX - drag.dx, ev.clientY - drag.dy]; dirty = true;
        drag.trail.push([ev.clientX, ev.clientY, performance.now()]); if(drag.trail.length > 8) drag.trail.shift(); };
      const up = () => {
        removeEventListener('pointermove', move); removeEventListener('pointerup', up); removeEventListener('pointercancel', up);
        if(!drag) return;
        // a flick: the speed over the last tenth of a second carries on, in px per frame
        const now = performance.now(), tr = drag.trail.filter(p => now - p[2] < 100);
        if(tr.length > 1){ const a = tr[0], b = tr[tr.length - 1], dt = Math.max(8, b[2] - a[2]); Ch.fling(t, (b[0] - a[0])/dt*16.7, (b[1] - a[1])/dt*16.7); }
        drag = null; G.quality = 'full'; root.classList.remove('fc-dragging'); dirty = true; settle = 60; scheduleSave();
      };
      addEventListener('pointermove', move); addEventListener('pointerup', up); addEventListener('pointercancel', up);
    }
    const MAX_W = () => Math.max(400, innerWidth - 40), MAX_H = () => Math.max(300, innerHeight - TOP - 30);
    // Resize: the grip sits at the lower right of the window; the upper left stays where it is. The tray keeps its own
    // shape, stretched to the new size (owner decision: the size changes, not the shape; stretching is allowed).
    function startResize(e, t){
      e.preventDefault(); hideMenu(); select(t);
      if(t.locked) return;
      G.quality = 'fast'; root.classList.add('fc-dragging');
      sizing = {t, left: t.cx - t.reqW/2, top: t.cy - t.reqH/2, w: t.reqW, h: t.reqH};
      const move = ev => { const mn = stackMin(t);
        sizing.w = Math.max(mn.w, Math.min(MAX_W(), ev.clientX - sizing.left)); sizing.h = Math.max(mn.h, Math.min(MAX_H(), ev.clientY - sizing.top)); dirty = true; };
      const up = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', up); removeEventListener('pointercancel', up);
        sizing = null; G.quality = 'full'; root.classList.remove('fc-dragging'); dirty = true; settle = 40; scheduleSave(); };
      addEventListener('pointermove', move); addEventListener('pointerup', up); addEventListener('pointercancel', up);
    }
    // Give a tray an on-screen size of w x h. Its contents are laid out at that size, never below what they need: if
    // the tray is smaller than that, they are laid out at what they need and shown scaled down to fit.
    const visW = t => t.reqW*(t.scale || 1), visH = t => t.reqH*(t.scale || 1);
    function sizeTray(t, w, h, cx, cy){
      const mn = stackMin(t), rw = Math.max(w, mn.w), rh = Math.max(h, mn.h), sc = Math.min(1, w/rw, h/rh);
      S.resize(t, rw, rh); if(cx !== undefined){ t.cx = cx; t.cy = cy; } Ch.attach(t, S);
      if(sc < 0.999) Ch.rescale(t, S, sc);
    }
    // Try a size for a tray; keep it if the others could make room (nothing pressed into anything), else go back.
    // Returns true when it fitted.
    function trySize(t, w, h, cx, cy){
      const prev = {w: t.reqW, h: t.reqH, cx: t.cx, cy: t.cy, scale: t.scale};
      const c = ctx(), env = physEnv(c), snap = Ch.snapshot(trays), before = Ch.pressure(trays);
      sizeTray(t, w, h, cx, cy);
      for(let k = 0; k < 6; k++) Ch.step(trays, env);
      if(!Ch.worsened(before, Ch.pressure(trays))) return true;
      Ch.restore(snap); S.resize(t, prev.w, prev.h); t.cx = prev.cx; t.cy = prev.cy; Ch.attach(t, S);
      if(prev.scale !== 1) Ch.rescale(t, S, prev.scale);
      return false;
    }
    function sizingStep(){
      const t = sizing.t;
      if(Math.abs(t.reqW - sizing.w) < 0.5 && Math.abs(t.reqH - sizing.h) < 0.5) return;
      // the others get a chance to give way first: those touching it are asked to shrink if they must
      if(!trySize(t, sizing.w, sizing.h, sizing.left + sizing.w/2, sizing.top + sizing.h/2)){
        for(const u of Ch.neighbours(t, trays, Ch.OPT.gap + 6)) u.squeezeReq = Math.max(u.squeezeReq || 0, 10);
        // no room for that size yet: grow toward it as far as fits
        const w0 = t.reqW, h0 = t.reqH;
        for(const f of [0.5, 0.25, 0.1]){ const w = w0 + (sizing.w - w0)*f, h = h0 + (sizing.h - h0)*f;
          if(Math.abs(w - w0) < 1 && Math.abs(h - h0) < 1) break;
          if(trySize(t, w, h, sizing.left + w/2, sizing.top + h/2)) break; }
      }
    }

    // ---------- fly into the fan, out of it, and to the dock
    // One animation at a time. Closing: the screen fades, the frame shrinks and flies along an arc into the tip of its
    // own blade, which ducks in to take it. Opening: the blade pops out and the tray grows out of its tip to where it
    // belongs. Putting away: the frame flies to its tag in the dock at the right edge.
    function freezeShape(t){ t.q0 = t.q.map(p => [p[0] - t.cx, p[1] - t.cy]); t.r0 = t.r; t.rim0 = t.rim; }
    function setVisible(t, on){ t.el.style.opacity = on ? '1' : '0'; t.plaque.style.opacity = on ? '1' : '0'; }
    function close(t){
      if(!t || anim || t.hidden) return;
      exitFull(t); if(selected === t) selected = null;
      t.home = [t.cx, t.cy]; freezeShape(t); t.hidden = true; setVisible(t, false);
      anim = {kind: 'close', t, blade: bladeIndexOf(t), t0: clock(), dur: 650};
      dirty = true; emit('close', t);
    }
    // Where a tray coming back (out of the fan, out of the side stack) lands: where it was, if that is still free,
    // else wherever it fits largest now; null if the counter has no room for it at all.
    function landing(t){
      const env = physEnv(ctx()), floor = stackMinScale(t);
      if(t.home) for(const s of [t.scale || 1, 0.85, 0.7].filter(x => x >= floor - 1e-6)) if(Ch.roomAt(t, t.home, s, trays, env) >= Ch.OPT.gap) return {p: t.home, s};
      return fitPlace(t);
    }
    function settleAt(t, l){ t.home = l.p; t.cx = l.p[0]; t.cy = l.p[1]; Ch.attach(t, S); if(Math.abs(l.s - (t.scale || 1)) > 1e-3) Ch.rescale(t, S, l.s); }
    function reopen(t){
      if(!t || anim || !t.closed) return;
      const l = landing(t);
      if(!l){ toast('No room on the counter for ' + activeContent(t).title + ' yet: put something away or close a tray first.'); return; }
      settleAt(t, l); t.cuts = []; S.finalize(t); freezeShape(t);
      anim = {kind: 'open', t, blade: bladeIndexOf(t), t0: clock(), dur: 700}; dirty = true;
    }
    function park(t){
      if(!t || anim || t.hidden) return;
      exitFull(t); if(selected === t) selected = null;
      t.home = [t.cx, t.cy]; freezeShape(t); t.hidden = true; setVisible(t, false);
      anim = {kind: 'park', t, slot: parked.length, t0: clock(), dur: 600}; dirty = true;
    }
    // the tag a put-away tray leaves in the side stack: click to bring it back, right-click for its menu
    function addDockLabel(t){
      const lab = document.createElement('div'); lab.className = 'fc-dock'; lab.textContent = activeContent(t).title; lab.title = 'Bring back ' + activeContent(t).title;
      lab.addEventListener('pointerdown', e => { e.preventDefault(); unpark(t); });
      lab.addEventListener('contextmenu', e => { e.preventDefault(); openTrayMenu(t, e.clientX, e.clientY); });
      root.appendChild(lab); t.dockLabel = lab;
    }
    function unpark(t){
      if(!t || anim) return;
      const i = parked.indexOf(t); if(i < 0) return;
      const l = landing(t);
      if(!l){ toast('No room on the counter for ' + activeContent(t).title + ' yet: put something away or close a tray first.'); return; }
      parked.splice(i, 1); t.parked = false; if(t.dockLabel){ t.dockLabel.remove(); t.dockLabel = null; }
      settleAt(t, l); t.cuts = []; S.finalize(t); freezeShape(t);
      anim = {kind: 'unpark', t, slot: i, t0: clock(), dur: 600}; dirty = true;
    }
    function discard(t){
      if(!t || anim) return;
      exitFull(t);
      const i = trays.indexOf(t); if(i < 0) return;
      const pi = parked.indexOf(t); if(pi >= 0) parked.splice(pi, 1);
      trays.splice(i, 1); if(selected === t) selected = null;
      t.stack.forEach(destroyContent); removeTrayDOM(t);
      dirty = true; settle = 30; scheduleSave(); emit('discard', t);
    }
    function flight(a, k){
      const c = ctx(), home = a.t.home, away = a.kind === 'close' || a.kind === 'park';
      const spot = a.blade !== undefined ? c.blades[Math.min(a.blade, c.blades.length - 1)].tip : dockSlot(a.slot);
      const e = ease(k), from = away ? home : spot, to = away ? spot : home;
      const mid = [(from[0] + to[0])/2, Math.max(TOP + 20, Math.min(from[1], to[1]) - 160)];   // a rising arc, not a straight slide
      const u = 1 - e, pos = [u*u*from[0] + 2*u*e*mid[0] + e*e*to[0], u*u*from[1] + 2*u*e*mid[1] + e*e*to[1]];
      const small = a.blade !== undefined ? 0.10 : 0.16, sc = away ? 1 - (1 - small)*e : small + (1 - small)*e;
      const ang = a.blade !== undefined ? (away ? e : 1 - e) * (c.blades[Math.min(a.blade, c.blades.length - 1)].angle - 0.2) : 0;   // turns to lie along the blade
      return {pos, sc, ang};
    }
    function stepAnim(){
      if(!anim) return;
      if((clock() - anim.t0)/anim.dur < 1) return;
      const t = anim.t, kind = anim.kind;
      anim = null;
      if(kind === 'open' || kind === 'unpark'){
        t.hidden = false; t.closed = false; setVisible(t, true);
        Ch.attach(t, S); selected = t; emit('open', t);
      }
      if(kind === 'close'){ t.closed = true; }
      if(kind === 'park'){ t.parked = true; parked.push(t); addDockLabel(t); }
      dirty = true; settle = 40; scheduleSave();
    }
    // Where a new tray should land: the open spot on the counter that its frame overlaps least.
    function freePlace(t){
      const c = ctx(), B = c.bounds, ex = t.a + 60, ey = t.b + 60, best = {s: Infinity, p: [(B.x0 + B.x1)/2, (B.y0 + B.y1)/2]};
      const open = trays.filter(u => u !== t && !u.hidden);
      for(let gx = 0; gx <= 8; gx++) for(let gy = 0; gy <= 6; gy++){
        const x = B.x0 + 230 + ex + (B.x1 - B.x0 - 230 - 2*ex)*gx/8, y = B.y0 + ey + (B.y1 - B.y0 - 2*ey)*gy/6;
        let s = 0;
        for(const u of open){ const ox = Math.max(0, (ex + u.a + 60) - Math.abs(x - u.cx)), oy = Math.max(0, (ey + u.b + 60) - Math.abs(y - u.cy)); s += ox*oy; }
        s += Math.hypot(x - (B.x0 + B.x1)/2, y - (B.y0 + B.y1)/2)*0.5;   // other things equal, toward the middle
        if(s < best.s){ best.s = s; best.p = [x, y]; }
      }
      return best.p;
    }

    // ---------- opening and importing content
    // A new tray: its blade pops out of the fan and the tray grows out of the blade's tip to its place.
    function open(type, data, o){
      o = o || {};
      if(anim){ queue.push(() => open(type, data, o)); return null; }
      const id = o.id || ('tray' + Date.now().toString(36) + (nextId++));
      const t = buildTray({id, contents: [{type, data, state: o.state}], x: 0, y: 0, w: o.w, h: o.h, family: o.family, look: o.look});
      t.cx = 0; t.cy = 0; trays.push(t); t.hidden = true; t.closed = true; setVisible(t, false);
      // Where, and how big: the open spot where it fits largest, never pressed into another tray, the fan or a wall.
      // A full counter gives it less room: it opens smaller (its contents shown scaled to fit, down to what they
      // allow) and, once it is the selected tray, swells back toward its own size as the others make way.
      const place = o.x !== undefined ? {p: [o.x, o.y], s: 1} : fitPlace(t);
      if(!place){
        // nowhere on the counter, even at its smallest: it waits in the side stack until room is made
        t.home = freePlace(t); t.cx = t.home[0]; t.cy = t.home[1]; Ch.attach(t, S); freezeShape(t);
        t.closed = false; t.parked = true; parked.push(t); addDockLabel(t);
        toast('The counter is full. ' + activeContent(t).title + ' is waiting in the side stack: put something away to bring it out.');
        dirty = true; scheduleSave(); emit('open', t);
        return t;
      }
      t.home = place.p; t.cx = place.p[0]; t.cy = place.p[1]; Ch.attach(t, S);
      if(place.s < 0.999) Ch.rescale(t, S, place.s);
      t.cuts = []; S.finalize(t); freezeShape(t);
      anim = {kind: 'open', t, blade: bladeIndexOf(t), t0: clock(), dur: 700};
      dirty = true; scheduleSave();
      return t;
    }
    // The largest size (from its own down to what its contents allow) and a spot at which tray t fits on the counter
    // without touching anything: {p:[x,y], s} or null. Other things equal, nearer the middle of the open space.
    function fitPlace(t){
      const c = ctx(), env = physEnv(c), B = c.bounds, floor = stackMinScale(t), gap = Ch.OPT.gap;
      const scales = [1, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4].filter(s => s >= floor - 1e-6);
      if(!scales.length || scales[scales.length - 1] > floor + 1e-6) scales.push(floor);
      for(const s of scales){
        let best = null;
        for(let gx = 0; gx <= 14; gx++) for(let gy = 0; gy <= 9; gy++){
          const p = [B.x0 + (B.x1 - B.x0)*(gx + 0.5)/15, B.y0 + (B.y1 - B.y0)*(gy + 0.5)/10];
          const room = Ch.roomAt(t, p, s, trays, env);
          if(room < gap) continue;
          const score = room - 0.04*Math.hypot(p[0] - (B.x0 + B.x1)/2, p[1] - (B.y0 + B.y1)/2);
          if(!best || score > best.score) best = {p, s, score};
        }
        if(best) return best;
      }
      return null;
    }
    const queue = [];
    // Load content into a tray. A blank tray's placeholder is replaced; anything else stays in the tray's stack (a
    // blade under the plaque switches back to it). An unlocked tray grows to what the new content needs; a locked
    // tray asks first.
    function importInto(t, type, data){
      const def = describe(type, data), need = {w: Math.max(def.minW, ...t.stack.map(c => c.def.minW)), h: Math.max(def.minH, ...t.stack.map(c => c.def.minH))};
      const tooSmall = t.reqW < need.w - 0.5 || t.reqH < need.h - 0.5;
      const place = () => {
        const c = makeContent(type, data); c.tray = t;
        t.el.insertBefore(c.bg, t.safeEl); t.safeEl.appendChild(c.body);
        const blankOnly = t.stack.length === 1 && t.stack[0].type === 'blank';
        if(blankOnly){ destroyContent(t.stack[0]); t.stack = [c]; t.natural = {w: def.w, h: def.h, family: t.natural.family}; }
        else t.stack.push(c);
        showContent(t, t.stack.indexOf(c));
        if(tooSmall) growTo(t, Math.max(visW(t), need.w), Math.max(visH(t), need.h), {push: true, need});
        select(t); scheduleSave(); emit('import', {tray: t, content: c});
        return c;
      };
      if(tooSmall && t.locked){
        ask(def.title + ' needs a little more room than this tray has. Make a little more room?',
          [['Make room', () => { place(); }, true],   // it stays locked where it is; the others move aside for it
           ['Open in a new tray', () => open(type, data)], ['Cancel', () => {}]]);
        return null;
      }
      return place();
    }
    // Grow (or shrink) a tray toward w x h over a few frames, keeping its shape and its spot (upper left stays put
    // where it can), the others making room as it comes. o.push: the others may be squeezed to make that room (Make
    // room, a new content that needs it, Reset on the main tray); without it the tray only takes room that is free.
    // After at most two seconds it stops wherever it has got to, never pressing frames into each other. If its
    // contents (o.need) still want more than that, they are shown scaled down to fit, as in a squeezed tray, and the
    // tray grows back to full size by itself once room comes free.
    function growTo(t, w, h, o){
      o = o || {};
      t.grow = {w, h, push: !!o.push, need: o.need || null, frames: 0, stuck: 0, left: t.cx - visW(t)/2, top: t.cy - visH(t)/2, centre: t.locked ? [t.cx, t.cy] : null};
      dirty = true; settle = 60;
    }
    function growStep(t){
      const g = t.grow, B = ctx().bounds; g.frames++;
      const cw = visW(t), ch = visH(t);
      if(Math.abs(cw - g.w) < 0.75 && Math.abs(ch - g.h) < 0.75){ t.grow = null; scheduleSave(); return; }
      // a locked tray stays anchored on its own centre (it grows evenly all round); any other keeps its upper left
      const at = (w, h) => { const x = g.centre ? g.centre[0] : g.left + w/2, y = g.centre ? g.centre[1] : g.top + h/2;
        return [Math.min(B.x1 - w/2 - 20, Math.max(B.x0 + w/2 + 20, x)), Math.min(B.y1 - h/2 - 20, Math.max(B.y0 + h/2 + 20, y))]; };
      let ok = false;
      for(const f of [0.35, 0.12, 0.04]){
        const w = cw + (g.w - cw)*f, h = ch + (g.h - ch)*f, p = at(w, h);
        if(Math.abs(w - cw) < 0.5 && Math.abs(h - ch) < 0.5) break;
        if(trySize(t, w, h, p[0], p[1])){ ok = true; break; }
      }
      if(!ok){
        g.stuck++;
        if(g.push) for(const u of Ch.neighbours(t, trays, Ch.OPT.gap + 6)) if(!u.locked) u.squeezeReq = Math.max(u.squeezeReq || 0, 12);
      }
      if(g.stuck > 40 || g.frames > 120){
        t.grow = null; scheduleSave();
        if(g.need && (visW(t) < g.need.w - 1 || visH(t) < g.need.h - 1)) toast('Showing ' + activeContent(t).title + ' a little smaller until there is more room');
      }
      dirty = true;
    }

    // ---------- reset, lock
    // Reset: back toward the tray's own natural shape and size. The main (selected) tray takes its full size and the
    // others make room; any other tray grows only as far as fits, trying full size first and backing off in steps.
    function reset(t){
      if(!t || t.hidden) return;
      if(t.locked){ toast('This tray is locked. Unlock it to reset it.'); return; }
      const main = t === selected, nat = t.natural, mn = stackMin(t);
      if((t.requestedFamily || t.family) !== nat.family) S.reshape(t, nat.family);   // a different general shape only if its contents ask for one
      const W = Math.max(nat.w, mn.w), H = Math.max(nat.h, mn.h);
      // back to its own size: at once if that is smaller (it always fits), else over a few frames as the others make
      // way (pushed aside and squeezed for the main tray; only free room for any other)
      if(visW(t) >= W - 0.5 && visH(t) >= H - 0.5){ if(!trySize(t, W, H)) growTo(t, W, H, {push: main}); }
      else growTo(t, W, H, {push: main});
      dirty = true; settle = 60; scheduleSave();
    }
    function lock(t, on){ if(!t) return; t.locked = on === undefined ? !t.locked : !!on; if(t.locked && t.chain){ t.chain.vx = 0; t.chain.vy = 0; } dirty = true; settle = 30; scheduleSave(); }
    function lockAll(on){ const v = on === undefined ? !trays.every(x => x.hidden || x.locked) : !!on; trays.forEach(x => { if(!x.hidden) lock(x, v); }); }

    // ---------- capture, full screen, export, save
    function trayBounds(t){ const xs = t.q.map(p => p[0]), ys = t.q.map(p => p[1]), r = t.r + 14;
      return [Math.max(0, Math.min(...xs) - r), Math.max(0, Math.min(...ys) - r), Math.min(innerWidth, Math.max(...xs) + r), Math.min(innerHeight, Math.max(...ys) + r)]; }
    function download(name, blobOrText, type){
      const blob = blobOrText instanceof Blob ? blobOrText : new Blob([blobOrText], {type: type || 'application/octet-stream'});
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
    }
    const fileSafe = s => String(s || 'tray').replace(/[^\w\- .]+/g, '').trim().slice(0, 60) || 'tray';
    // Screen capture: the tray exactly as it is on screen, frame and contents (pages, video and all). The browser asks
    // once to share this tab; the picture is cropped to the tray. If sharing is refused or not available, the frame
    // and any video or drawing in it are captured from the page itself, and a note says the rest was left out.
    async function capture(t){
      if(!t || t.hidden) return;
      hideMenu(); const box = trayBounds(t), name = fileSafe(activeContent(t).title) + ' ' + new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-') + '.png';
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      if(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia){
        let stream = null;
        try{
          stream = await navigator.mediaDevices.getDisplayMedia({video: {displaySurface: 'browser'}, audio: false, preferCurrentTab: true, selfBrowserSurface: 'include'});
          const video = document.createElement('video'); video.muted = true; video.srcObject = stream; await video.play();
          await new Promise(r => setTimeout(r, 120));
          const sx = video.videoWidth/innerWidth, sy = video.videoHeight/innerHeight;
          const cv = document.createElement('canvas'); cv.width = Math.round((box[2] - box[0])*sx); cv.height = Math.round((box[3] - box[1])*sy);
          cv.getContext('2d').drawImage(video, box[0]*sx, box[1]*sy, cv.width, cv.height, 0, 0, cv.width, cv.height);
          stream.getTracks().forEach(k => k.stop());
          const blob = await new Promise(r => cv.toBlob(r, 'image/png'));
          download(name, blob); toast('Captured ' + activeContent(t).title); return;
        }catch(err){ if(stream) stream.getTracks().forEach(k => k.stop()); }
      }
      // fallback: what this page can draw itself
      const dpr = canvas.width/innerWidth, cv = document.createElement('canvas');
      cv.width = Math.round((box[2] - box[0])*dpr); cv.height = Math.round((box[3] - box[1])*dpr);
      const g = cv.getContext('2d');
      render(ctx()); g.drawImage(canvas, box[0]*dpr, box[1]*dpr, cv.width, cv.height, 0, 0, cv.width, cv.height);
      let skipped = false;
      // pictures the page can draw (video frames, drawings, images), clipped to the screen inside the frame
      const scr = t.el.getBoundingClientRect(), clip = new Path2D();
      const fl = t.floor && t.floor.q ? t.floor.q : t.q; clip.moveTo((fl[0][0] - box[0])*dpr, (fl[0][1] - box[1])*dpr);
      for(const p of fl) clip.lineTo((p[0] - box[0])*dpr, (p[1] - box[1])*dpr); clip.closePath();
      for(const m of [activeContent(t).bg, activeContent(t).body]){
        for(const el of m.querySelectorAll('video,canvas,img')){
          const r = el.getBoundingClientRect(); if(!r.width || !r.height || r.right < scr.left || r.left > scr.right) continue;
          g.save(); g.clip(clip);
          try{ g.drawImage(el, (r.left - box[0])*dpr, (r.top - box[1])*dpr, r.width*dpr, r.height*dpr); }catch(e){ skipped = true; }
          g.restore();
        }
      }
      if(activeContent(t).body.querySelector('iframe') || activeContent(t).body.textContent.trim()) skipped = true;
      try{ const blob = await new Promise(r => cv.toBlob(r, 'image/png')); download(name, blob);
        toast(skipped ? 'Captured the frame; allow screen sharing to include the page inside it.' : 'Captured ' + activeContent(t).title); }
      catch(e){ toast('This tray could not be captured here.'); }
    }
    // Full screen: the tray's own screen fills the display, live (nothing reloads). Escape comes back to the counter.
    let fullTray = null;
    function fullScreen(t){
      if(!t || t.hidden) return;
      hideMenu(); select(t);
      if(opt.onFullScreen){ opt.onFullScreen(t, activeContent(t)); return; }
      const el = t.el; el.classList.add('fc-full'); fullTray = t;
      const req = el.requestFullscreen || el.webkitRequestFullscreen;
      if(req){ Promise.resolve(req.call(el)).catch(() => {}); }
      else toast('Press Escape to come back to the counter');
      dirty = true;
    }
    function exitFull(t){
      if(fullTray !== t) return;
      t.el.classList.remove('fc-full'); fullTray = null;
      if(document.fullscreenElement === t.el && document.exitFullscreen) document.exitFullscreen().catch(() => {});
      dirty = true;
    }
    const onFsChange = () => { if(fullTray && document.fullscreenElement !== fullTray.el){ fullTray.el.classList.remove('fc-full'); fullTray = null; dirty = true; } };
    document.addEventListener('fullscreenchange', onFsChange);
    async function exportTray(t){
      if(!t) return; hideMenu();
      const c = activeContent(t);
      try{
        if(provider.exportContent){ const f = await provider.exportContent(c); if(f){ download(f.name || fileSafe(c.title), f.data, f.type); toast('Exported ' + c.title); return; } }
        const body = JSON.stringify({kind: 'foresight.content', type: c.type, title: c.title, data: c.data, state: serializeContent(c), exported: new Date().toISOString()}, null, 2);
        download(fileSafe(c.title) + '.json', body, 'application/json'); toast('Exported ' + c.title);
      }catch(err){ console.error(err); toast('Export did not work: ' + (err && err.message || err)); }
    }
    async function save(t){
      hideMenu();
      if(t && provider.save){ try{ const r = await provider.save(activeContent(t)); if(r !== false){ saveCounter(); toast('Saved ' + activeContent(t).title); return; } }catch(err){ toast('Save did not work: ' + (err && err.message || err)); return; } }
      const ok = saveCounter(); toast(ok ? 'Saved the counter in this browser' : 'Could not save here (browser storage is off)');
    }

    // ---------- keeping the counter across reloads
    function serializeContent(c){ try{ return provider.serialize ? provider.serialize(c) : c.state; }catch(e){ return c.state; } }
    function serialize(){
      return {v: 3, theme, selected: selected ? selected.id : null, trays: trays.map(t => ({
        id: t.id, x: t.home && t.hidden ? t.home[0] : t.cx, y: t.home && t.hidden ? t.home[1] : t.cy, w: t.reqW, h: t.reqH,
        family: t.family, requestedFamily: t.requestedFamily, unit0: t.unit0, aspect0: t.aspect0, natural: t.natural,
        scale: +(t.scale || 1).toFixed(4), locked: t.locked, look: t.look || null, active: t.active, closed: !!t.closed, parked: !!t.parked,
        contents: t.stack.map(c => ({type: c.type, data: c.data, state: serializeContent(c)}))}))};
    }
    let saveTimer = null;
    function saveCounter(){ if(!storageKey) return false; try{ localStorage.setItem(storageKey, JSON.stringify(serialize())); return true; }catch(e){ return false; } }
    function scheduleSave(){ if(!storageKey) return; clearTimeout(saveTimer); saveTimer = setTimeout(saveCounter, 400); }
    function restore(data){
      if(!data || !Array.isArray(data.trays)) return false;
      for(const s of data.trays){
        try{
          const contents = (s.contents || []).filter(c => c && c.type);
          if(!contents.length) continue;
          const t = buildTray({id: s.id || ('tray' + (nextId++)), contents, x: s.x, y: s.y, w: s.w, h: s.h, family: s.family, look: s.look, active: s.active, locked: s.locked, natural: s.natural, saved: s});
          trays.push(t); t.home = [s.x, s.y];
          if(s.scale && s.scale < 0.999) Ch.rescale(t, S, Math.max(0.3, s.scale));   // squeezed (or showing its contents smaller) as it was
          if(s.closed){ t.hidden = true; t.closed = true; setVisible(t, false); }
          else if(s.parked){ t.hidden = true; t.parked = true; setVisible(t, false); parked.push(t); freezeShape(t); addDockLabel(t); }
        }catch(err){ console.error('Could not bring back a tray', s && s.id, err); }
      }
      selected = trays.find(t => t.id === data.selected && !t.hidden) || null;
      dirty = true; settle = 120;
      return trays.length > 0;
    }
    function load(){ if(!storageKey) return null; try{ return JSON.parse(localStorage.getItem(storageKey) || 'null'); }catch(e){ return null; } }

    // ---------- menus, picker, questions, toasts
    const menu = document.createElement('div'); menu.className = 'fc-menu'; menu.setAttribute('role', 'menu'); root.appendChild(menu);
    function openMenu(items, x, y){
      menu.innerHTML = '';
      for(const it of items){
        if(it === '-'){ menu.appendChild(document.createElement('hr')); continue; }
        const b = document.createElement('button'); b.textContent = it[0]; b.setAttribute('role', 'menuitem');
        if(it[2] === false) b.disabled = true;
        b.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); hideMenu(); it[1](); });
        menu.appendChild(b);
      }
      menu.style.display = 'block';
      const w = menu.offsetWidth, h = menu.offsetHeight;
      Object.assign(menu.style, {left: Math.max(6, Math.min(x, innerWidth - w - 6)) + 'px', top: Math.max(6, Math.min(y, innerHeight - h - 6)) + 'px'});
      const first = menu.querySelector('button:not([disabled])'); if(first) first.focus({preventScroll: true});
    }
    function hideMenu(){ menu.style.display = 'none'; }
    menu.addEventListener('keydown', e => {
      const bs = [...menu.querySelectorAll('button:not([disabled])')], i = bs.indexOf(document.activeElement);
      if(e.key === 'ArrowDown'){ e.preventDefault(); (bs[(i + 1) % bs.length] || bs[0]).focus(); }
      if(e.key === 'ArrowUp'){ e.preventDefault(); (bs[(i - 1 + bs.length) % bs.length] || bs[0]).focus(); }
      if(e.key === 'Escape'){ e.preventDefault(); hideMenu(); }
    });
    function openTrayMenu(t, x, y){
      const items = [];
      if(t.stack.length > 1){ t.stack.forEach((c, k) => items.push([(k === t.active ? '● ' : '○ ') + c.title, () => { showContent(t, k); scheduleSave(); }])); items.push('-'); }
      if(t.closed){ items.push(['Open', () => reopen(t)], ['Remove from the fan', () => discard(t)]); openMenu(items, x, y); return; }
      if(t.parked){ items.push(['Bring back', () => unpark(t)], ['Close into the fan', () => { unparkThenClose(t); }]); openMenu(items, x, y); return; }
      items.push(['Reset tray', () => reset(t), !t.locked],
                 [t.locked ? 'Unlock tray' : 'Lock tray', () => lock(t)],
                 [trays.every(u => u.hidden || u.locked) ? 'Unlock all trays' : 'Lock all trays', () => lockAll()],
                 '-',
                 ['Import…', () => openPicker(t)],
                 ['Export', () => exportTray(t)],
                 ['Screen capture', () => capture(t)],
                 ['Full screen', () => fullScreen(t)],
                 ['Save', () => save(t)],
                 '-',
                 ['Put away', () => park(t)],
                 ['Close into the fan', () => close(t)]);
      openMenu(items, x, y);
    }
    function unparkThenClose(t){ unpark(t); queue.push(() => close(t)); }
    const veil = document.createElement('div'); veil.className = 'fc-veil'; root.appendChild(veil);
    veil.addEventListener('pointerdown', e => { if(e.target === veil) hideVeil(); });
    veil.addEventListener('keydown', e => { if(e.key === 'Escape'){ e.preventDefault(); hideVeil(); } });
    function hideVeil(){ veil.classList.remove('fc-open'); veil.innerHTML = ''; }
    function panel(title){ veil.innerHTML = ''; const p = document.createElement('div'); p.className = 'fc-panel'; p.setAttribute('role', 'dialog'); p.setAttribute('aria-label', title);
      const h = document.createElement('h3'); h.textContent = title; p.appendChild(h); veil.appendChild(p); veil.classList.add('fc-open'); return p; }
    // The picker: everything the page can open, by group, plus a blank tray and a file from this computer. With a
    // tray, what is picked loads into that tray; without one, it opens in a new tray out of the fan.
    function openPicker(t){
      hideMenu();
      const p = panel(t ? 'Import into ' + activeContent(t).title : 'Open in a new tray');
      const list = (provider.catalog ? provider.catalog() : []).filter(x => x && (x.type || x.run));
      const groups = [];
      for(const it of list){ const g = it.group || 'Programs'; let grp = groups.find(x => x.name === g); if(!grp){ grp = {name: g, items: []}; groups.push(grp); } grp.items.push(it); }
      const pick = (type, data) => { hideVeil();
        if(provider.beforeOpen && provider.beforeOpen(type, data, t) === false) return;   // e.g. a one-of-a-kind program already open: brought forward instead
        if(t) importInto(t, type, data); else open(type, data); };
      const section = (name, items) => {
        const h = document.createElement('div'); h.className = 'fc-sec'; h.textContent = name; p.appendChild(h);
        const grid = document.createElement('div'); grid.className = 'fc-grid'; p.appendChild(grid);
        for(const it of items){ const b = document.createElement('button'); b.className = 'fc-item';
          const bt = document.createElement('b'); bt.textContent = it.title; b.appendChild(bt);
          if(it.hint){ const sp = document.createElement('span'); sp.textContent = it.hint; b.appendChild(sp); }
          b.addEventListener('click', () => it.run ? (hideVeil(), it.run()) : pick(it.type, it.data)); grid.appendChild(b); }
      };
      const extras = [];
      if(!t) extras.push({title: 'Blank tray', hint: 'Load anything into it later', type: 'blank'});
      extras.push({title: 'A file from this computer…', hint: 'Image, video, audio, PDF, text', run: () => pickFile(t)});
      const trayGroup = groups.find(g => g.name === 'Trays');
      if(trayGroup) trayGroup.items.push(...extras); else groups.push({name: 'Trays', items: extras});
      groups.forEach(g => section(g.name, g.items));
      const row = document.createElement('div'); row.className = 'fc-row';
      const cancel = document.createElement('button'); cancel.className = 'fc-btn'; cancel.textContent = 'Cancel'; cancel.addEventListener('click', hideVeil);
      row.appendChild(cancel); p.appendChild(row);
      const first = p.querySelector('.fc-item'); if(first) first.focus({preventScroll: true});
    }
    function pickFile(t){
      const inp = document.createElement('input'); inp.type = 'file';
      inp.addEventListener('change', () => {
        const f = inp.files && inp.files[0]; if(!f) return;
        const r = provider.fromFile ? provider.fromFile(f) : null;
        if(!r){ toast('That kind of file cannot be opened in a tray yet'); return; }
        if(t) importInto(t, r.type, r.data); else open(r.type, r.data);
      });
      inp.click();
    }
    // A short question with a few answers: [[label, fn, isMain], ...]
    function ask(text, answers){
      const p = panel('Make room');
      const msg = document.createElement('div'); msg.textContent = text; msg.style.maxWidth = '420px'; p.appendChild(msg);
      const row = document.createElement('div'); row.className = 'fc-row';
      for(const [label, fn, main] of answers){ const b = document.createElement('button'); b.className = 'fc-btn' + (main ? ' fc-main' : ''); b.textContent = label;
        b.addEventListener('click', () => { hideVeil(); fn(); }); row.appendChild(b); }
      p.appendChild(row); const m = row.querySelector('.fc-main') || row.querySelector('button'); if(m) m.focus({preventScroll: true});
    }
    const toastEl = document.createElement('div'); toastEl.className = 'fc-toast'; toastEl.setAttribute('role', 'status'); root.appendChild(toastEl);
    let toastTimer = null;
    function toast(text){ toastEl.textContent = text; toastEl.classList.add('fc-show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toastEl.classList.remove('fc-show'), 2400); }

    // ---------- pointer on the counter itself: a blade, a tray's frame, or empty bench
    const bladeLabels = [];
    function hitTray(x, y){ return trays.find(t => !t.hidden && t.q && S.hit(t, [x, y]) <= 0) || null; }
    function hitBlade(x, y){ const c = ctx(); for(let i = c.blades.length - 1; i >= 0; i--) if(inPoly(c.blades[i].q, x, y)) return i; return -1; }
    const onCanvasDown = e => {
      if(e.button !== 0) return;
      hideMenu();
      const b = hitBlade(e.clientX, e.clientY);
      if(b === 0){ openPicker(null); return; }
      if(b > 0){ const t = trays[b - 1]; if(!t) return;
        if(t.closed) reopen(t); else if(t.parked) unpark(t); else { select(t); t.flash = clock(); dirty = true; }
        return; }
      const t = hitTray(e.clientX, e.clientY);
      if(t){ startDrag(e, t); return; }   // the frame itself is a handle too
      if(selected){ select(null); }
    };
    const onCanvasMenu = e => {
      e.preventDefault();
      const b = hitBlade(e.clientX, e.clientY);
      if(b > 0 && trays[b - 1]){ openTrayMenu(trays[b - 1], e.clientX, e.clientY); return; }
      if(b === 0){ openPicker(null); return; }
      const t = hitTray(e.clientX, e.clientY); if(t) openTrayMenu(t, e.clientX, e.clientY);
    };
    canvas.addEventListener('pointerdown', onCanvasDown);
    canvas.addEventListener('contextmenu', onCanvasMenu);
    const onDocDown = e => { if(!menu.contains(e.target)) hideMenu(); };
    addEventListener('pointerdown', onDocDown, true);
    // a click inside a page in a tray (an iframe) does not reach this page; its window losing focus to that frame does
    const onBlur = () => setTimeout(() => { const f = document.activeElement; if(f && f.tagName === 'IFRAME'){ const t = trays.find(u => u.el.contains(f)); if(t && selected !== t) select(t); } }, 0);
    addEventListener('blur', onBlur);
    const onKey = e => { if(e.key === 'Escape'){ hideMenu(); if(veil.classList.contains('fc-open')) hideVeil(); if(fullTray) exitFull(fullTray); } };
    addEventListener('keydown', onKey);
    const onResize = () => { dirty = true; settle = 60; };
    addEventListener('resize', onResize);

    // ---------- each frame
    function physics(c){
      stepAnim();
      if(!anim && queue.length) queue.shift()();
      if(sizing) sizingStep();
      for(const t of trays) if(t.grow && !t.hidden) growStep(t);
      const env = physEnv(c);
      let moved;
      if(drag){ const r = Ch.dragStep(trays, env, drag.hand); moved = r.moved; }
      else moved = Ch.step(trays, env);
      const resized = Ch.squeeze(trays, env, S);
      settle = (moved > 0.05 || resized || drag || sizing || anim || trays.some(t => t.grow)) ? 30 : settle - 1;
    }
    function layoutDOM(){
      for(const t of trays){
        const on = !t.hidden;
        const showEl = on || (anim && anim.t === t);
        t.el.style.display = showEl ? '' : 'none'; t.plaque.style.display = showEl ? '' : 'none';
        const sel = on && t === selected;
        t.grip.style.display = sel && !t.locked ? 'block' : 'none';   // a locked tray cannot be resized until it is unlocked
        t.closer.style.display = t.parker.style.display = t.menuKnob.style.display = sel ? 'block' : 'none';
        if(!on) for(const g of t.tags) g.style.display = 'none';
        if(t.dockLabel){ const [x, y] = dockSlot(parked.indexOf(t)); Object.assign(t.dockLabel.style, {left: x + 'px', top: y + 'px'}); }
        if(!on) continue;
        const sr = S.screenRect(t), sa = S.safeArea(t), s = t.scale || 1;
        Object.assign(t.el.style, {left: sr[0] + 'px', top: sr[1] + 'px', width: (sr[2] - sr[0]) + 'px', height: (sr[3] - sr[1]) + 'px',
          clipPath: t.chain ? Ch.clipPath(t, [sr[0], sr[1]]) : S.contentClipPath(t)});
        // the contents keep their own layout size; a squeezed tray shows them scaled down with it
        Object.assign(t.safeEl.style, {left: sa[0] + 'px', top: sa[1] + 'px', width: t.reqW + 'px', height: t.reqH + 'px', transform: s === 1 ? '' : 'scale(' + s.toFixed(4) + ')'});
        // the plaque sits on the frame's top side at rest, and rides (and turns with) that side when it gives way
        let an = S.titleAnchor(Object.assign({}, t, {poly: t.base.map(p => [p[0] + t.cx, p[1] + t.cy])}));
        const d = Ch.anchorOffset(t, [an.x, an.y]); an = Object.assign({}, an, {x: an.x + d[0], y: an.y + d[1], angle: an.angle + (d[2] || 0)});
        t.anchor = an;
        const w = t.plaque.offsetWidth;
        Object.assign(t.plaque.style, {left: (an.x - w/2) + 'px', top: (an.y - 7) + 'px', transform: 'rotate(' + an.angle + 'rad)'});
        t.plaqueW = w + 34;
        Object.assign(t.grip.style, {left: (sr[0] + sa[0] + sa[2]) + 'px', top: (sr[1] + sa[1] + sa[3]) + 'px'});
        const off = w/2 + 26, ca = Math.cos(an.angle), sn = Math.sin(an.angle);
        Object.assign(t.closer.style, {left: (an.x + ca*off) + 'px', top: (an.y + sn*off) + 'px'});
        Object.assign(t.parker.style, {left: (an.x + ca*(off + 22)) + 'px', top: (an.y + sn*(off + 22)) + 'px'});
        Object.assign(t.menuKnob.style, {left: (an.x + ca*(off + 44)) + 'px', top: (an.y + sn*(off + 44)) + 'px'});
        // stacked contents: blades tucked under the plaque's left end, set into the rim one after another, each
        // a little lower than the one before, so the plaque overlaps the first and each overlaps the next
        let along = (w + 34)/2;   // the plaque plate's left tip
        t.tagAt = t.tags.map((g, k) => {
          const tw = g.offsetWidth, plate = tw + 22, mid = -(along - 8 + plate/2), out = -1 - k*0.5;   // tucked 8px under the one before
          along += plate - 8;
          const x = an.x + ca*mid + sn*out, y = an.y + sn*mid - ca*out;
          Object.assign(g.style, {left: (x - tw/2) + 'px', top: (y - 6) + 'px', transform: 'rotate(' + an.angle + 'rad)', display: ''});
          return {x, y, w: plate};
        });
      }
    }
    function render(c){
      const items = [];
      if(G.lamp){ const L = c.lantern, n = L.length; G.lightPos = [L.reduce((a, p) => a + p[0], 0)/n, L.reduce((a, p) => a + p[1], 0)/n]; }
      const benchMetal = theme === 'pearl' || theme === 'nero' ? M.CHAMPAGNE : M.SILVER;
      if(opt.bar !== false) items.push({q: barPoly(c.W), ornate: true, r: 12, rim: 9, rimMat: benchMetal, floorMat: benchMetal, height: 7, thick: 7, seed: 2});
      // the fan: the New blade first (champagne), then one blade per tray in that tray's own frame metal
      const now = clock();
      c.blades.forEach((b, i) => {
        const t = i > 0 ? trays[i - 1] : null, look = t ? lookFor(t) : null;
        const dim = t && (t.closed || t.parked), on = t && t === selected, flash = t && t.flash && now - t.flash < 900 ? 1 - (now - t.flash)/900 : 0;
        items.push({q: b.q, r: 5, rim: 6, rimMat: t ? (look[0] < 10 ? look[0] : M.CHAMPAGNE) : M.CHAMPAGNE, floorMat: dim ? M.TORTOISE : M.PEARL, height: 6, thick: 5, seed: 30 + i,
          glow: on || flash ? (GLOW[look[1]] || GLOW.warm) : [1, 0.9, 0.75, 0.2], backlight: flash});
        let lab = bladeLabels[i];
        if(!lab){ lab = document.createElement('div'); lab.className = 'fc-blade'; root.appendChild(lab); bladeLabels[i] = lab; }
        lab.textContent = t ? activeContent(t).title : '+  New';
        lab.classList.toggle('fc-dim', !!dim);
        lab.style.display = '';
        lab.style.left = (PIVOT[0] + Math.cos(b.angle)*(64 + b.pop)) + 'px'; lab.style.top = (PIVOT[1] + Math.sin(b.angle)*(64 + b.pop) - 7) + 'px';
        lab.style.transform = 'rotate(' + b.angle + 'rad)';
      });
      for(let i = c.blades.length; i < bladeLabels.length; i++) bladeLabels[i].style.display = 'none';
      items.push({q: c.lantern, r: 7, rim: 8, rimMat: M.BRASS, floorMat: M.TORTOISE, height: 10, thick: 8, seed: 9, glow: [1, 0.6, 0.2, 0.9], emissive: [1.0, 0.52, 0.16, 0.7]});
      for(const t of trays){
        if(t.hidden) continue;
        const look = lookFor(t), m = Math.min(t.a, t.b)*2, flash = t.flash && now - t.flash < 900 ? 1 - (now - t.flash)/900 : 0;
        items.push({q: t.q, r: t.r, rim: t.rim, pad: S.FLOOR_PAD, rimMat: look[0], ornStyle: look[2] || 0, floorMat: M.OBSIDIAN, glow: GLOW[look[1]] || GLOW.warm,
          ornate: true, backlight: selected === t ? 1 : flash, focus: selected === t ? 1 : 0, screen: true,
          content: [t.cx - t.a, t.cy - t.b, t.cx + t.a, t.cy + t.b], seed: 5 + trays.indexOf(t)*3, height: 14,
          thick: Math.max(10, Math.min(16, m*0.04)), center: [t.cx, t.cy]});
        (t.tagAt || []).slice().reverse().forEach((g, k) => items.push({q: plaquePoly(g.x, g.y, t.anchor.angle, g.w, 18), r: 4, rim: 3,
          rimMat: look[0] < 10 ? look[0] : M.CHAMPAGNE, floorMat: M.PEARL, height: 2, thick: 2, seed: 70 + k}));
        if(t.anchor) items.push({q: plaquePoly(t.anchor.x, t.anchor.y, t.anchor.angle, t.plaqueW || 120, 24), r: 4, rim: 4, rimMat: look[0] < 10 ? look[0] : M.CHAMPAGNE,
          floorMat: t.locked ? M.TORTOISE : M.OBSIDIAN, height: 3, thick: 3, seed: 60 + trays.indexOf(t)});
      }
      parked.forEach((t, i) => { const look = lookFor(t);
        items.push({q: dockTagPoly(i), r: 5, rim: 5, rimMat: look[0] < 10 ? look[0] : M.CHAMPAGNE, floorMat: M.PEARL, height: 6, thick: 5, seed: 80 + i, glow: GLOW[look[1]] || GLOW.warm}); });
      if(anim){
        // the frame in flight: its own shape, scaled, turned and carried along the arc (the screen is not drawn)
        const t = anim.t, look = lookFor(t), k = Math.min(1, (clock() - anim.t0)/anim.dur), f = flight(anim, k);
        const cs = Math.cos(f.ang), sn = Math.sin(f.ang);
        const q = t.q0.map(([x, y]) => [f.pos[0] + (x*cs - y*sn)*f.sc, f.pos[1] + (x*sn + y*cs)*f.sc]);
        items.push({q, r: Math.max(2, t.r0*f.sc), rim: Math.max(2, t.rim0*f.sc), pad: 0, rimMat: look[0], ornStyle: look[2] || 0,
          floorMat: M.OBSIDIAN, glow: GLOW[look[1]] || GLOW.warm, ornate: f.sc > 0.6, height: 4 + 18*f.sc, thick: Math.max(3, 12*f.sc), seed: 5,
          center: f.pos, backlight: anim.kind === 'open' || anim.kind === 'unpark' ? 0.6*(1 - k) : 0});
      }
      G.draw(items);
    }
    function frame(){
      if(!alive) return;
      const c = ctx();
      const flashing = trays.some(t => t.flash && clock() - t.flash < 900);
      if(dirty || drag || sizing || anim || settle > 0 || flashing){
        physics(c); layoutDOM(); render(c); dirty = false;
      }
      requestAnimationFrame(frame);
    }

    // ---------- start
    function setTheme(name){ theme = name; G.setTheme(name); dirty = true; }
    function renderSoon(){ dirty = true; }
    setTheme(theme);
    const api = {
      get trays(){ return trays; }, get selected(){ return selected; }, gl: G, root,
      find: id => trays.find(t => t.id === id) || null,
      open, importInto, close, reopen, discard, park, unpark, lock, lockAll, reset, select, capture, fullScreen, exportTray, save,
      openPicker, openTrayMenu, setTheme, serialize, toast, pickFile, ask,
      show(t, i){ if(t){ showContent(t, i); scheduleSave(); } },
      active: t => t ? activeContent(t) : null,
      exitFullScreen(){ if(fullTray) exitFull(fullTray); },
      get fullTray(){ return fullTray; },
      // lay trays out from a list (used on first start); each spec: {id, contents:[{type,data}], x, y, w?, h?, family?, look?}
      layout(specs){ for(const s of specs){ const t = buildTray(s); t.home = [s.x, s.y]; trays.push(t); } dirty = true; settle = 120; },
      restore(data){ return restore(data || load()); },
      saveNow: saveCounter,
      start(){ requestAnimationFrame(frame); },
      settle(n){ const c = ctx(), env = physEnv(c); trays.forEach(t => { if(!t.hidden) Ch.attach(t, S); }); for(let k = 0; k < (n || 300); k++){ Ch.step(trays, env); Ch.squeeze(trays, env, S); } },
      destroy(){
        alive = false; canvas.removeEventListener('pointerdown', onCanvasDown); canvas.removeEventListener('contextmenu', onCanvasMenu);
        removeEventListener('pointerdown', onDocDown, true); removeEventListener('blur', onBlur); removeEventListener('keydown', onKey); removeEventListener('resize', onResize);
        document.removeEventListener('fullscreenchange', onFsChange);
        trays.forEach(t => t.stack.forEach(destroyContent)); root.remove();
      },
      // for tests: step time and physics by hand, look inside
      debug: {
        setClock(ms){ clock = () => ms; },
        step(){ const c = ctx(); physics(c); return {pressure: Ch.pressure(trays), moved: settle}; },
        draw(){ const c = ctx(); layoutDOM(); render(c); G.gl.finish(); },
        anim: () => anim, queue: () => queue.length,
        dragTo(id, x, y, frames){ const t = api.find(id); select(t); if(t.locked) return {x: t.cx, y: t.cy};
          drag = {hand: {t, want: [x, y], at: [t.cx, t.cy]}, dx: 0, dy: 0, trail: []}; let blocked = 0;
          for(let k = 0; k < (frames || 300); k++){ const c = ctx(); stepAnim(); const r = Ch.dragStep(trays, physEnv(c), drag.hand); Ch.squeeze(trays, physEnv(c), S); if(r.blocked) blocked++;
            if(Math.hypot(t.cx - x, t.cy - y) < 1.5) break; }
          drag = null; return {x: t.cx, y: t.cy, blocked}; },
        sizeTo(id, w, h, frames){ const t = api.find(id), mn = stackMin(t); select(t); if(t.locked) return {w: t.reqW, h: t.reqH};
          sizing = {t, left: t.cx - t.reqW/2, top: t.cy - t.reqH/2, w: Math.max(w, mn.w), h: Math.max(h, mn.h)};
          for(let k = 0; k < (frames || 30); k++){ const c = ctx(); sizingStep(); Ch.step(trays, physEnv(c)); Ch.squeeze(trays, physEnv(c), S); }
          sizing = null; return {w: Math.round(t.reqW), h: Math.round(t.reqH)}; },
        fling(id, vx, vy){ Ch.fling(api.find(id), vx, vy); },
        info(id){ const t = api.find(id); if(!t) return null; return {id: t.id, active: activeContent(t).title, stack: t.stack.map(c => c.title), types: t.stack.map(c => c.type),
          w: Math.round(t.reqW), h: Math.round(t.reqH), scale: +(t.scale || 1).toFixed(3), min: stackMin(t), natural: t.natural, cx: Math.round(t.cx), cy: Math.round(t.cy),
          locked: t.locked, family: t.family, requested: t.requestedFamily || t.family, corners: t.q.length, hidden: !!t.hidden, closed: !!t.closed, parked: !!t.parked, dent: t.chain ? +t.chain.dent.toFixed(1) : 0}; },
        dents(){ return Object.fromEntries(trays.filter(t => t.chain && !t.hidden).map(t => [t.id, +t.chain.dent.toFixed(1)])); },
        pressure: () => Ch.pressure(trays), blades: () => ctx().blades.map((b, i) => ({i, tip: b.tip.map(Math.round), title: i ? activeContent(trays[i - 1]).title : 'New'})),
        menuItems: () => [...menu.querySelectorAll('button')].map(b => b.textContent), clickMenu(label){ const b = [...menu.querySelectorAll('button')].find(x => x.textContent === label); if(b) b.click(); return !!b; },
        veilItems: () => [...veil.querySelectorAll('button')].map(b => b.textContent.split('\n')[0]), clickVeil(label){ const b = [...veil.querySelectorAll('button')].find(x => x.querySelector('b') ? x.querySelector('b').textContent === label : x.textContent === label); if(b) b.click(); return !!b; },
        hit: (x, y) => { const t = hitTray(x, y); return t ? t.id : null; }, bladeAt: (x, y) => hitBlade(x, y)
      }
    };
    return api;
  }

  root.ForesightCounter = {create, version: 1};
})(window);
