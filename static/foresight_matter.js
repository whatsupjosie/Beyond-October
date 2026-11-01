/* Foresight Matter — the material renderer for the Counter.
   The pixels come from C++ (foresight_matter.cpp) compiled to WebAssembly
   (foresight_matter.wasm). Rendering runs in background workers so dragging and
   typing never wait on it. Results come back as ImageBitmaps.

   Public API (window.ForesightMatter):
     ready                       Promise that resolves when the renderer is loaded
     SHAPE, MAT                  enums matching the C++ source
     LIGHT                       the one global light {az, el}
     fit(spec, cw, ch, inset)    grow a shape until a cw x ch content rectangle,
                                 inset by `inset` px, sits fully inside it
     tray(params)                Promise<ImageBitmap> of a tray frame with its cast shadow
     bench(w, h, mat)            Promise<ImageBitmap> of the workbench surface
     distance(spec, x, y)        signed distance to a shape (negative inside)
*/
(function(){
  'use strict';
  const SHAPE = {ROUNDRECT:0, CHAMFER:1, GEM:2, LONGHEX:3, ELLIPSE:4, SHELL:5, PETAL:6, PILL:7, CUSHION:8, ARCH:9};
  const MAT = {GOLD:0, BRASS:1, COPPER:2, SILVER:3, BRONZE:4,
    MARBLE_WHITE:10, MARBLE_ROSE:11, MARBLE_GREEN:12, MARBLE_BLACK:13,
    GRANITE:20, GRANITE_BLACK:21, SANDSTONE:30, WALNUT:40, OAK:41, MAHOGANY:42,
    NACRE:50, PEARL:51, TORTOISE:60, GLASS_AMETHYST:70, GLASS_EMERALD:71, GLASS_SAPPHIRE:72, GLASS_SMOKE:73,
    EMERALD_ENAMEL:74, OBSIDIAN_LACQUER:75, LEATHER:80};
  const LIGHT = {az:135, el:48};          // one light for the whole Counter (upper left)
  const MAX_PIXELS = 2560 * 1600;          // size of the C++ output buffer
  const scriptUrl = (document.currentScript && document.currentScript.src) || location.href;
  const WASM_URL = new URL('foresight_matter.wasm', scriptUrl).href;

  // ---- worker: owns one wasm instance, renders on request ----
  const WORKER_SRC = `
    let ex = null;
    const ready = (async () => {
      const res = await fetch(${JSON.stringify(WASM_URL)});
      if (!res.ok) throw new Error('wasm HTTP ' + res.status);
      const { instance } = await WebAssembly.instantiate(await res.arrayBuffer(), { env: {} });
      ex = instance.exports;
    })();
    self.onmessage = async (e) => {
      const { id, op, a } = e.data;
      try {
        await ready;
        let W, H, rc;
        if (op === 'tray') { W = a[0]; H = a[1]; rc = ex.fm_render_tray(...a); }
        else if (op === 'bench') { W = a[0]; H = a[1]; rc = ex.fm_render_bench(...a); }
        else if (op === 'ping') { self.postMessage({ id, ok: true }); return; }
        if (rc !== 0) throw new Error('render refused (' + W + 'x' + H + ')');
        const px = new Uint8ClampedArray(ex.memory.buffer, ex.fm_buffer(), W * H * 4).slice();
        const bmp = await createImageBitmap(new ImageData(px, W, H));
        self.postMessage({ id, ok: true, bmp }, [bmp]);
      } catch (err) { self.postMessage({ id, ok: false, error: String(err && err.message || err) }); }
    };`;

  const workers = [];
  const pending = new Map();
  let nextId = 1, rr = 0;
  function spawn(){
    const url = URL.createObjectURL(new Blob([WORKER_SRC], {type:'text/javascript'}));
    const w = new Worker(url);
    w.onmessage = e => {
      const p = pending.get(e.data.id); if(!p) return;
      pending.delete(e.data.id);
      e.data.ok ? p.resolve(e.data.bmp) : p.reject(new Error(e.data.error));
    };
    return w;
  }
  const count = Math.max(1, Math.min(3, (navigator.hardwareConcurrency || 2) - 1));
  for (let i = 0; i < count; i++) workers.push(spawn());
  function call(op, a){
    return new Promise((resolve, reject) => {
      const id = nextId++; pending.set(id, {resolve, reject});
      workers[(rr++) % workers.length].postMessage({id, op, a});
    });
  }

  // ---- main-thread instance for geometry queries (fit / hit-test) ----
  let geo = null;
  const ready = (async () => {
    const res = await fetch(WASM_URL);
    if (!res.ok) throw new Error('Foresight Matter: wasm HTTP ' + res.status);
    const { instance } = await WebAssembly.instantiate(await res.arrayBuffer(), {env:{}});
    geo = instance.exports;
    await call('ping', []);
    return true;
  })();

  function distance(s, x, y){
    return geo.fm_shape_distance(s.shape, s.hx, s.hy, s.round||0, s.a||0, s.b||0, x, y);
  }
  // Points along the edge of the content rectangle (corners first).
  function rectSamples(cw, ch){
    const pts = [];
    const n = 8;
    for (let i = 0; i <= n; i++){
      const t = -1 + 2*i/n;
      pts.push([t*cw, -ch], [t*cw, ch], [-cw, t*ch], [cw, t*ch]);
    }
    return pts;
  }
  // Grow the shape (keeping its proportions relative to the content) until the
  // content rectangle, inset by `inset`, is inside it. The frame bulges outward;
  // the content rectangle never shrinks.
  function fit(spec, cw, ch, inset){
    const hw = cw/2, hh = ch/2, pts = rectSamples(hw, hh);
    const aspectX = spec.ax || 1, aspectY = spec.ay || 1;
    const ok = k => {
      const s = Object.assign({}, spec, {hx:(hw+inset)*aspectX*k, hy:(hh+inset)*aspectY*k});
      if (spec.roundFrac) s.round = Math.min(s.hx, s.hy) * spec.roundFrac;
      for (const [x,y] of pts) if (distance(s, x, y) > -inset) return null;
      return s;
    };
    let lo = 1, hi = 1;
    if (ok(1)) return ok(1);
    while (!ok(hi) && hi < 4) hi *= 1.25;
    for (let i = 0; i < 18; i++){ const m = (lo+hi)/2; ok(m) ? hi = m : lo = m; }
    return ok(hi) || Object.assign({}, spec, {hx:(hw+inset)*2, hy:(hh+inset)*2});
  }

  // A tray frame. spec: {shape, hx, hy, round, a, b}; returns {bmp, margin, W, H}
  async function tray(p){
    const margin = p.margin ?? Math.round(18 + (p.height ?? 10) * 2.2);
    let W = Math.ceil(p.hx*2 + margin*2), H = Math.ceil(p.hy*2 + margin*2);
    if (W*H > MAX_PIXELS) throw new Error('tray too large to render');
    const bmp = await call('tray', [W, H, margin, p.shape, p.hx, p.hy, p.round||0, p.a||0, p.b||0,
      p.rim ?? MAT.GOLD, p.floor ?? MAT.MARBLE_WHITE, p.rimW ?? 18, p.height ?? 10,
      LIGHT.az, LIGHT.el, p.worldX||0, p.worldY||0, p.seed ?? 3,
      ...(p.hole || [0,0,0,0])]);                       // [x0,y0,x1,y1] relative to the centre; left transparent
    return {bmp, margin, W, H};
  }
  async function bench(w, h, mat){
    let W = Math.round(w), H = Math.round(h), scale = 1;
    if (W*H > MAX_PIXELS){ scale = Math.sqrt(MAX_PIXELS/(W*H)); W = Math.floor(W*scale); H = Math.floor(H*scale); }
    const bmp = await call('bench', [W, H, mat ?? MAT.WALNUT, LIGHT.az, LIGHT.el, 7]);
    return {bmp, scale};
  }

  window.ForesightMatter = {ready, SHAPE, MAT, LIGHT, fit, tray, bench, distance};
})();
