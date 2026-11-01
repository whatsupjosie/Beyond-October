/* Foresight Skin — dresses the Counter in rendered materials.
   Every frame, blade, the lantern, the system bar and the bench are drawn by the
   C++ renderer (foresight_matter.wasm) through ForesightMatter. This file only
   decides which shape and material each piece gets and where its picture goes.

   The tray's element is its content rectangle. The frame is fitted around it and
   bulges outward only, so content is never clipped by a shape. */
(function(){
  'use strict';
  const M = window.ForesightMatter;
  if(!M){ console.warn('Foresight Matter is not loaded; the Counter keeps its plain look.'); return; }
  const S = M.SHAPE, T = M.MAT;
  const RIM_W = 18, GAP = 8, INSET = RIM_W + GAP, HEIGHT = 10;

  // The canonical palette (Iteration Wallet materials pass, 2026-07-23) plus stone and wood.
  // ink: the text colour that reads on that floor.
  const LOOKS = {
    pearl:     {name:'Rearview Pearl',        shape:S.CUSHION,   roundAbs:30, a:1,    rim:T.GOLD,   floor:T.PEARL,            ink:'dark'},
    sapphire:  {name:'Sapphire Glass',        shape:S.CHAMFER,   roundAbs:6,  a:0.12, rim:T.SILVER, floor:T.GLASS_SAPPHIRE,   ink:'light'},
    emerald:   {name:'Emerald Enamel',        shape:S.LONGHEX,   roundAbs:8,  a:0.05, rim:T.GOLD,   floor:T.EMERALD_ENAMEL,   ink:'light'},
    amethyst:  {name:'Amethyst Glass',        shape:S.CHAMFER,   roundAbs:10, a:0.18, rim:T.GOLD,   floor:T.GLASS_AMETHYST,   ink:'light'},
    obsidian:  {name:'Obsidian Lacquer',      shape:S.ROUNDRECT, roundAbs:16,         rim:T.COPPER, floor:T.OBSIDIAN_LACQUER, ink:'light'},
    marble:    {name:'White Marble',          shape:S.CHAMFER,   roundAbs:6,  a:0.10, rim:T.BRASS,  floor:T.MARBLE_WHITE,     ink:'dark'},
    verde:     {name:'Verde Marble',          shape:S.CUSHION,   roundAbs:26, a:1,    rim:T.SILVER, floor:T.MARBLE_GREEN,     ink:'light'},
    granite:   {name:'Black Granite',         shape:S.LONGHEX,   roundAbs:8,  a:0.05, rim:T.BRASS,  floor:T.GRANITE_BLACK,    ink:'light'},
    sandstone: {name:'Sandstone',             shape:S.ROUNDRECT, roundAbs:12,         rim:T.BRONZE, floor:T.SANDSTONE,        ink:'dark'},
    tortoise:  {name:'Tortoiseshell',         shape:S.CUSHION,   roundAbs:34, a:1,    rim:T.COPPER, floor:T.TORTOISE,         ink:'light'},
    nacre:     {name:'Clamshell Nacre',       shape:S.CHAMFER,   roundAbs:8,  a:0.14, rim:T.GOLD,   floor:T.NACRE,            ink:'dark'},
  };
  const ORDER = Object.keys(LOOKS);

  // Default look for each kind of tray. Chosen so the common trays differ at a glance.
  function lookFor(program){
    const id = program.id || '', kind = program.kind || '';
    if(id.startsWith('pubpartner')) return 'pearl';
    if(id === 'twoi' || id === 'twoi_bridge_status') return 'amethyst';
    if(id === 'iteration_wallet') return 'obsidian';
    if(id === 'care_eq') return 'verde';
    if(kind === 'browser') return 'sapphire';
    if(kind === 'video' || kind === 'recordings') return 'granite';
    if(kind === 'file') return 'marble';
    if(kind === 'blank') return 'nacre';
    if(program.portalKind === 'chat') return 'pearl';
    if(program.group === 'Studio Rooms') return 'emerald';
    if(program.group === 'Production Tools') return 'sandstone';
    return 'marble';
  }

  // ---- fitting: smallest frame (by area) whose inner floor holds the content ----
  function fitFrame(look, w, h){
    const hw = w/2, hh = h/2, pts = [];
    for(let i=0;i<=8;i++){ const t=-1+i/4; pts.push([t*hw,-hh],[t*hw,hh],[-hw,t*hh],[hw,t*hh]); }
    const base = {shape:look.shape, round:look.roundAbs||0, a:look.a||0, b:look.b||0};
    const holds = (hx, hy) => {
      const s = Object.assign({}, base, {hx, hy});
      for(const [x,y] of pts) if(M.distance(s, x, y) > -INSET) return false;
      return true;
    };
    let best = null;
    for(let ax=1; ax<=1.6001; ax+=0.05){
      for(let ay=1; ay<=1.6001; ay+=0.05){
        if(ax>1 && ay>1) continue;                       // grow one axis faster than the other, never both extra
        let lo=1, hi=1;
        const ok = k => holds((hw+INSET)*ax*k, (hh+INSET)*ay*k);
        if(!ok(1)){ while(!ok(hi) && hi<3) hi*=1.2; if(!ok(hi)) continue;
          for(let i=0;i<14;i++){ const m=(lo+hi)/2; ok(m)?hi=m:lo=m; } }
        const hx=(hw+INSET)*ax*hi, hy=(hh+INSET)*ay*hi, area=hx*hy;
        if(!best || area<best.area) best={hx,hy,area};
      }
    }
    if(!best) best = {hx:(hw+INSET)*1.5, hy:(hh+INSET)*1.5};
    return Object.assign(base, {hx:best.hx, hy:best.hy});
  }

  // ---- tray frames ----
  const seq = new WeakMap();       // tray -> render sequence number (drop stale results)
  async function frameTray(tray){
    if(!tray || !tray.el || tray.entered) return;
    const look = LOOKS[tray.look] || LOOKS[lookFor(tray.program)];
    tray.el.dataset.ink = look.ink;
    tray.el.dataset.look = tray.look;
    let cv = tray.el.querySelector(':scope > canvas.t-frame');
    if(!cv){ cv = document.createElement('canvas'); cv.className='t-frame'; cv.setAttribute('aria-hidden','true'); tray.el.prepend(cv); }
    const w = tray.el.offsetWidth, h = tray.el.offsetHeight;
    if(w<10 || h<10) return;
    const n = (seq.get(tray)||0)+1; seq.set(tray, n);
    try{
      await M.ready;
      const spec = fitFrame(look, w, h);
      const seed = hashStr(tray.id) % 997;
      // The program's body covers the middle of the floor, so that part is not rendered at all.
      const head = tray.el.querySelector(':scope > .tray-head');
      const headH = head ? head.offsetHeight : 0;
      const hole = [-w/2 + 3, -h/2 + headH + 3, w/2 - 3, h/2 - 3];
      const r = await M.tray(Object.assign({}, spec, {rim:look.rim, floor:look.floor, rimW:RIM_W, height:HEIGHT,
        worldX: seed*37 % 2000, worldY: seed*53 % 2000, seed: seed, hole}));
      if(seq.get(tray)!==n){ r.bmp.close?.(); return; }
      cv.width = r.W; cv.height = r.H;
      cv.getContext('2d').drawImage(r.bmp, 0, 0); r.bmp.close?.();
      // place the frame so its centre sits on the content's centre
      Object.assign(cv.style, {width:r.W+'px', height:r.H+'px', left:(w/2 - r.W/2)+'px', top:(h/2 - r.H/2)+'px'});
      tray.__bulge = {x:r.W - w, y:r.H - h};
      tray.el.classList.add('matter');
    }catch(err){ console.warn('Tray frame could not be rendered:', err); }
  }
  function hashStr(s){ let h=2166136261; for(const c of String(s)){ h^=c.charCodeAt(0); h=Math.imul(h,16777619); } return h>>>0; }

  // Re-render a frame after its tray stops changing size.
  const timers = new WeakMap();
  const ro = new ResizeObserver(entries=>{
    for(const e of entries){
      const tray = (window.trays||[]).find?.(t=>t.el===e.target) || e.target.__tray;
      if(!tray) continue;
      // Until the new frame arrives, stretch the old one so it still surrounds the content.
      const cv = tray.el.querySelector(':scope > canvas.t-frame'), b = tray.__bulge;
      if(cv && b){ const w=tray.el.offsetWidth, h=tray.el.offsetHeight;
        Object.assign(cv.style,{width:(w+b.x)+'px',height:(h+b.y)+'px',left:(-b.x/2)+'px',top:(-b.y/2)+'px'}); }
      clearTimeout(timers.get(tray));
      timers.set(tray, setTimeout(()=>frameTray(tray), 140));
    }
  });
  function attach(tray, saved){
    tray.look = (saved && LOOKS[saved.look]) ? saved.look : lookFor(tray.program);
    tray.el.__tray = tray;
    ro.observe(tray.el);
    frameTray(tray);
  }
  function cycleLook(tray){
    if(!tray) return;
    const i = ORDER.indexOf(tray.look);
    tray.look = ORDER[(i+1) % ORDER.length];
    frameTray(tray);
    return LOOKS[tray.look].name;
  }

  // ---- fan blades: one rendered petal per material, reused ----
  const bladeArt = new Map();
  const BLADE = {len:236, thick:58};
  function bladeLookFor(tray){
    if(!tray) return {rim:T.GOLD, floor:T.MARBLE_WHITE, ink:'dark'};          // the blank blade: plain marble card
    const l = LOOKS[tray.look] || LOOKS.marble; return l;
  }
  function bladeImage(look){
    const key = look.rim+':'+look.floor;
    if(!bladeArt.has(key)){
      bladeArt.set(key, M.ready.then(()=>M.tray({shape:S.PETAL, hx:BLADE.len/2, hy:BLADE.thick/2, rim:look.rim, floor:look.floor,
        rimW:7, height:6, margin:16, seed:11})));
    }
    return bladeArt.get(key);
  }
  function paintBlade(btn, tray){
    const look = bladeLookFor(tray);
    btn.dataset.ink = look.ink;
    let cv = btn.querySelector('canvas.b-art');
    if(!cv){ cv=document.createElement('canvas'); cv.className='b-art'; cv.setAttribute('aria-hidden','true'); btn.prepend(cv); }
    bladeImage(look).then(r=>{
      cv.width=r.W; cv.height=r.H; cv.getContext('2d').drawImage(r.bmp,0,0);
      Object.assign(cv.style,{width:r.W+'px',height:r.H+'px',left:(-r.margin)+'px',top:(BLADE.thick/2 - r.H/2)+'px'});
    }).catch(err=>console.warn('Blade art failed:', err));
  }
  // Angles for n blades around the lantern's pivot: a deck of cards fanned downward-right.
  function fanAngles(n){
    const start = 4, spread = Math.min(104, 18*(n-1));
    if(n===1) return [start];
    return Array.from({length:n}, (_,i)=> start + spread*i/(n-1));
  }

  // ---- bench, system bar, lantern ----
  async function paintBench(){
    const cv = document.getElementById('bench'); if(!cv) return;
    const w = innerWidth, h = innerHeight;
    try{
      await M.ready;
      const r = await M.bench(w, h, T.WALNUT);
      cv.width = r.bmp.width; cv.height = r.bmp.height;
      cv.getContext('2d').drawImage(r.bmp, 0, 0); r.bmp.close?.();
      cv.classList.add('ready');
    }catch(err){ console.warn('Bench could not be rendered:', err); }
  }
  async function paintBar(){
    const bar = document.querySelector('.topbar'); if(!bar) return;
    let cv = bar.querySelector('canvas.bar-art');
    if(!cv){ cv=document.createElement('canvas'); cv.className='bar-art'; cv.setAttribute('aria-hidden','true'); bar.prepend(cv); }
    const w = bar.offsetWidth, h = bar.offsetHeight;
    try{
      await M.ready;
      const r = await M.tray({shape:S.ROUNDRECT, hx:w/2-4, hy:h/2-3, round:10, rim:T.SILVER, floor:T.SILVER, rimW:7, height:6, margin:6, seed:5});
      cv.width=r.W; cv.height=r.H; cv.getContext('2d').drawImage(r.bmp,0,0); r.bmp.close?.();
      Object.assign(cv.style,{width:r.W+'px',height:r.H+'px',left:(w/2-r.W/2)+'px',top:(h/2-r.H/2)+'px'});
      bar.classList.add('matter');
    }catch(err){ console.warn('System bar could not be rendered:', err); }
  }
  async function paintLantern(){
    const lan = document.getElementById('lanternBtn'); if(!lan) return;
    let cv = lan.querySelector('canvas.l-art');
    if(!cv){ cv=document.createElement('canvas'); cv.className='l-art'; cv.setAttribute('aria-hidden','true'); lan.prepend(cv); }
    try{
      await M.ready;
      const r = await M.tray({shape:S.ARCH, hx:30, hy:38, round:8, rim:T.BRASS, floor:T.TORTOISE, rimW:7, height:8, margin:16, seed:9});
      cv.width=r.W; cv.height=r.H; cv.getContext('2d').drawImage(r.bmp,0,0); r.bmp.close?.();
      Object.assign(cv.style,{width:r.W+'px',height:r.H+'px'});
      lan.classList.add('matter');
    }catch(err){ console.warn('Lantern could not be rendered:', err); }
  }

  let resizeTimer = null;
  addEventListener('resize', ()=>{ clearTimeout(resizeTimer); resizeTimer=setTimeout(()=>{ paintBench(); paintBar(); }, 220); });

  // Space trays need between them so their frames do not overlap when tiled.
  const FRAME_GAP = 2*INSET + 30;
  window.ForesightSkin = {FRAME_GAP, LOOKS, ORDER, lookFor, attach, frameTray, cycleLook, paintBlade, fanAngles, BLADE,
    start(){ paintBench(); paintBar(); paintLantern(); }};
})();
