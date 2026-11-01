/* Foresight Frames: how tray frames move, touch, give way and recover.

   Two edge models share one engine. The default follows the v2 tray movement handoff (Josie, 2026-10-14):
   "each straight edge to kind of be on a slider", "like a door that never opens, but could swing from either
   hinge", "never, like, bend in half."

     edges: 'rigid' (default)  every side of the tray is one straight bar. The corners are its hinges. A side
                               can slide in or out and swing about either corner (a door on either hinge); it
                               telescopes a little (a slider) so the outline stays closed; it never bends in
                               the middle. Put another way: a bike chain whose links are the tray's own sides.
     edges: 'chain'            the earlier model: many short links per frame (36), so a side can curve into a
                               dent. Kept as an option because Josie also described the frame as linked bike
                               chain; which one she wants is an open question in the session record.

   Both models share the rest:
     - hit on the side, the frame gives there (rigid: that side slides in, or swings in if hit near one end)
     - pressed against a wall, the frame lies flat along it
     - when the pressure goes, a gentle spring brings the frame back to its own shape
     - the body has weight: a light bump is taken by the frame; a push that keeps coming moves the tray,
       heavier trays less; a flick glides it like a tissue blown across a table, and friction stops it
     - crowded hard (a sustained dent, or a tray dragged through), a tray shrinks, contents and all, down to a
       floor its contents set; with room again it grows back. The selected tray inflates back first and pushes.

   Guarantees:
     - a frame never covers more of the TV box (the window's own screen area) than its own shape does at rest,
       however hard it is pushed (at rest a rounded frame may cover the box's very corners: the shapes rule)
     - the selected tray (and one being dragged or resized) is solid: it never dents, it pushes
     - a locked tray never moves, dents, shrinks or grows: it keeps the very place and shape it was locked in
     - the fan, the lantern and a locked tray are as solid as the walls: a tray dragged or flicked against them stops
       there and slides along them; no tray is ever pushed, swelled or glided into them
     - rigid mode: every side stays one straight segment; the outline keeps exactly the tray's own corners

   The outline is the frame's inner polygon (the shape before the rounded corner radius is added), the same
   polygon the renderer draws with its rim. No DOM dependency; runs under Node for tests.

   API
     attach(t, S)              build t.chain from the tray's own (uncut) shape; call again after resize
     step(trays, env)          advance one frame; returns the largest movement (px) for settling
     settle(trays, env, n)     step until still (or n steps)
     squeeze(trays, env, S)    shrink crowded trays and regrow free ones (call once per frame after step)
     neighbours(t, trays, m)   trays whose frames are within m px of t's
     dragStep(trays, env, hand) one frame of a drag that can pass slowly through a crowd (see below)
     clipPath(t, origin)       CSS path() for the screen, following the outline
     anchorOffset(t, p)        [dx, dy, dAngle]: how the outline near world point p has moved and turned from rest
   env = {bounds:{x0,y0,x1,y1}, obstacles:[polygon...], rigid:(t)=>bool, coast:(t)=>bool, target:(t)=>[x,y]|null,
          locked:(t)=>bool, minScale:(t)=>number, gap, pad}
*/
(function(root){
  'use strict';

  const OPT = {
    edges: 'rigid',       // 'rigid' (sides are straight bars) or 'chain' (many short links); see above
    links: 36,            // chain mode: links per frame; the renderer draws up to 40 points
    sample: 20,           // rigid mode: px between contact points along a side
    sideMin: 0.62,        // rigid mode: a side can slide this much shorter (share of its own length)...
    sideMax: 1.18,        // ...or this much longer, so the outline stays closed as its neighbours move
    cornerBend: 0.55,     // rigid mode: radians a corner hinge may swing from its own angle (~32 degrees)
    substeps: 2,          // physics steps per frame
    iterations: 8,        // constraint passes per step
    gap: 8,               // px kept between two frames' outer edges
    restK: 0.03,          // spring back toward the frame's own shape, per pass: a bubble that holds its shape, easing out of a dent
    linkK: 0.85,          // how hard each pass restores link length
    maxBend: 0.62,        // chain mode: radians a hinge may bend away from its rest angle (~36 degrees)
    bendK: 0.9,           // how hard an over-bent hinge is eased back within its limit
    bodyK: 0.35,          // how readily the body gives way to the contact force on its links (slow, heavy: a bubble, not a puck)
    maxNudge: 6,          // px per step the body can be nudged by contact
    friction: 0.975,      // body velocity kept per step: low, so a tray glides like a tissue blown across a table
    maxSpeed: 30,         // px per step: a hard flick slides far, but never shoots
    boxMargin: 2,         // px of extra clearance kept around the TV box
    wallRoom: 6,          // px more between a TV box and a wall, so a frame flattened on the wall still has room to cover its box
    // crowding (proposed values, not owner-set; tune by eye)
    squeezeAt: 16,        // px of dent, held for crowdFrames, that starts a tray shrinking
    relaxAt: 5,           // px of dent below which a tray counts as free
    crowdFrames: 8,       // frames a dent must last before the tray gives way by shrinking
    calmFrames: 40,       // frames a shrunken tray must be free before it starts to grow back
    squeezeRate: 0.012,   // share of its size a crowded tray gives up per frame
    growRate: 0.004,      // share it takes back per frame once free
    inflateRate: 0.02,    // the selected tray inflates back faster, and pushes
    minSqueeze: 0.6,      // never smaller than this share of its set size (text stays readable), unless its contents say otherwise
  };

  const FLOOR_PAD = 2;   // the screen starts this far inside the rim (same as the shapes module)

  // ---------- small vector helpers ----------
  const sub = (a, b) => [a[0]-b[0], a[1]-b[1]];
  const dot = (a, b) => a[0]*b[0] + a[1]*b[1];
  const crs = (a, b) => a[0]*b[1] - a[1]*b[0];
  const len = a => Math.hypot(a[0], a[1]);

  function signedArea(P){ let s = 0; for(let i = 0; i < P.length; i++){ const a = P[i], b = P[(i+1)%P.length]; s += a[0]*b[1] - b[0]*a[1]; } return s/2; }

  // Evenly spaced points along a closed polygon, by arc length.
  function resample(P, n){
    const L = [], m = P.length; let total = 0;
    for(let i = 0; i < m; i++){ const d = len(sub(P[(i+1)%m], P[i])); L.push(d); total += d; }
    const step = total/n, out = [];
    let seg = 0, along = 0;
    for(let k = 0; k < n; k++){
      const want = k*step;
      while(seg < m - 1 && along + L[seg] < want){ along += L[seg]; seg++; }
      const a = P[seg], b = P[(seg+1)%m], u = L[seg] > 0 ? (want - along)/L[seg] : 0;
      out.push([a[0] + (b[0]-a[0])*u, a[1] + (b[1]-a[1])*u]);
    }
    return {pts: out, link: step};
  }

  // Nearest point on a closed polygon (convex or not) to p. Returns the signed distance (negative
  // inside), the outward unit normal at that point, and which edge (i -> j at parameter u) it is on.
  function nearest(P, p){
    let best = Infinity, bi = 0, bu = 0, bx = 0, by = 0, inside = false;
    for(let i = 0, j = P.length - 1; i < P.length; j = i, i++){
      const a = P[j], b = P[i], e = sub(b, a), w = sub(p, a);
      const ee = dot(e, e), u = ee > 0 ? Math.max(0, Math.min(1, dot(w, e)/ee)) : 0;
      const dx = w[0] - e[0]*u, dy = w[1] - e[1]*u, d2 = dx*dx + dy*dy;
      if(d2 < best){ best = d2; bi = j; bu = u; bx = dx; by = dy; }
      if(((a[1] > p[1]) !== (b[1] > p[1])) && p[0] < (b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1]) + a[0]) inside = !inside;
    }
    const d = Math.sqrt(best), s = inside ? -1 : 1;
    let n;
    if(d > 1e-6) n = [s*bx/d, s*by/d];
    else { const a = P[bi], b = P[(bi+1)%P.length], e = sub(b, a), l = len(e) || 1, o = signedArea(P) > 0 ? 1 : -1; n = [o*e[1]/l, -o*e[0]/l]; }
    return {d: s*d, n, i: bi, j: (bi+1)%P.length, u: bu};
  }

  // Signed distance from local point q to a box of half sizes hx, hy, and its outward gradient.
  function boxField(q, hx, hy){
    const ax = Math.abs(q[0]) - hx, ay = Math.abs(q[1]) - hy;
    const sx = q[0] < 0 ? -1 : 1, sy = q[1] < 0 ? -1 : 1;
    if(ax > 0 && ay > 0){ const d = Math.hypot(ax, ay); return {d, n:[sx*ax/d, sy*ay/d]}; }
    if(ax > ay) return {d: ax, n: [sx, 0]};
    return {d: ay, n: [0, sy]};
  }

  function aabb(P, pad){
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for(const p of P){ if(p[0] < x0) x0 = p[0]; if(p[1] < y0) y0 = p[1]; if(p[0] > x1) x1 = p[0]; if(p[1] > y1) y1 = p[1]; }
    return [x0 - pad, y0 - pad, x1 + pad, y1 + pad];
  }
  const overlaps = (a, b) => a[0] <= b[2] && b[0] <= a[2] && a[1] <= b[3] && b[1] <= a[3];

  // Move point at u along side a->b by (dx, dy), shared between the side's two corners so the point itself moves
  // exactly that far: hit near one end and that end swings (the door on its far hinge); hit in the middle and
  // the whole side slides.
  function move(a, b, u, dx, dy){
    if(u <= 0){ a[0] += dx; a[1] += dy; return; }
    const w = (1 - u)*(1 - u) + u*u, ka = (1 - u)/w, kb = u/w;
    a[0] += dx*ka; a[1] += dy*ka; b[0] += dx*kb; b[1] += dy*kb;
  }

  // Signed distance (box field) from the point at u along a->b, relative to centre (cx, cy).
  function segBox(a, b, u, cx, cy, hx, hy){ return boxField([a[0] + (b[0]-a[0])*u - cx, a[1] + (b[1]-a[1])*u - cy], hx, hy); }
  // Where along a->b the side comes closest to (or deepest into) the box. The box field is convex along a
  // line, so a ternary search finds it exactly. Returns u.
  function closestOnSide(a, b, cx, cy, hx, hy){
    let lo = 0, hi = 1;
    for(let it = 0; it < 22; it++){
      const m1 = lo + (hi - lo)/3, m2 = hi - (hi - lo)/3;
      if(segBox(a, b, m1, cx, cy, hx, hy).d < segBox(a, b, m2, cx, cy, hx, hy).d) hi = m2; else lo = m1;
    }
    return (lo + hi)/2;
  }

  // ---------- attach: build the frame from the tray's own, uncut shape ----------
  function attach(t, S, opt){
    const o = Object.assign({}, OPT, opt);
    const rigid = o.edges !== 'chain';
    const saved = t.cuts; t.cuts = []; S.finalize(t); t.cuts = saved;
    const local = t.q.map(p => [p[0] - t.cx, p[1] - t.cy]);
    const ori = signedArea(local) > 0 ? local : local.slice().reverse();
    // rigid: the corners are the tray's own corners, each side one bar; chain: evenly spaced short links
    const R = rigid ? ori.map(p => [p[0], p[1]]) : resample(ori, o.links).pts;
    const n = R.length;
    // each hinge's turning angle at rest, so it bends relative to its own shape
    const theta = R.map((b, i) => { const a = R[(i - 1 + n) % n], c = R[(i+1) % n], u = sub(b, a), v = sub(c, b); return Math.atan2(crs(u, v), dot(u, v)); });
    const areaPx = Math.abs(signedArea(R));
    const L0 = R.map((p, i) => len(sub(R[(i+1) % n], p)));
    // contact points per side: rigid sides are touched anywhere along their length; chain links at their joints
    const m = L0.map(L => rigid ? Math.max(1, Math.round(L/o.sample)) : 1);
    // rigid mode: how close each corner and each side sits to the TV box at rest. The guard never asks for more
    // room than the frame's own shape gives: at rest the frame may cover the box's very corners (the shapes
    // module allows 1.5% of the box there), so a rigid frame never covers more of the box than it does at rest.
    const restV = R.map(p => boxField(p, t.a, t.b).d);
    const restS = R.map((p, i) => { const q = R[(i+1) % n]; return segBox(p, q, closestOnSide(p, q, 0, 0, t.a, t.b), 0, 0, t.a, t.b).d; });
    // and how far each corner of the box sits outside the frame's outline at rest (the floor's rounding covers it)
    const restC = [[-1,-1],[1,-1],[1,1],[-1,1]].map(([sx, sy]) => nearest(R, [sx*t.a, sy*t.b]).d);
    const prev = t.chain;
    t.chain = {R, P: R.map(p => [p[0] + t.cx, p[1] + t.cy]), L0, theta, m, restV, restS, restC, rigid,
               lo: rigid ? o.sideMin : 0, hi: rigid ? o.sideMax : 1,
               vx: prev ? prev.vx : 0, vy: prev ? prev.vy : 0, crowd: prev ? prev.crowd || 0 : 0, calm: prev ? prev.calm || 0 : 0,
               mass: Math.min(3, Math.max(0.6, areaPx/45000)), dent: 0, fx: 0, fy: 0};
    publish(t, o);
    return t;
  }

  // keep every point of a frame on the counter: the walls are half-planes, so the corners alone decide it
  function walls(t, B){
    const r = t.r;
    for(const p of t.chain.P){ if(p[0] < B.x0 + r) p[0] = B.x0 + r; if(p[0] > B.x1 - r) p[0] = B.x1 - r; if(p[1] < B.y0 + r) p[1] = B.y0 + r; if(p[1] > B.y1 - r) p[1] = B.y1 - r; }
  }

  // The last word on a frame: the walls and its own screen. If keeping the frame clear of its screen would put part
  // of it past a wall, the wall pushes back on the whole tray instead (as a real wall would), moving it away just
  // that far, and then the walls are applied once more. So at a wall a frame never passes the wall and never
  // closes over its own screen.
  function settleOnWalls(t, B, o, pad){
    walls(t, B); guardBox(t, o, pad); guardBox(t, o, pad);   // twice: one side's fix can nudge its neighbour's corner
    const r = t.r; let dx = 0, dy = 0;
    for(const p of t.chain.P){
      if(p[0] < B.x0 + r) dx = Math.max(dx, B.x0 + r - p[0]); if(p[0] > B.x1 - r) dx = Math.min(dx, B.x1 - r - p[0]);
      if(p[1] < B.y0 + r) dy = Math.max(dy, B.y0 + r - p[1]); if(p[1] > B.y1 - r) dy = Math.min(dy, B.y1 - r - p[1]);
    }
    if(dx || dy){ t.cx += dx; t.cy += dy; for(const p of t.chain.P){ p[0] += dx; p[1] += dy; } }
    walls(t, B);
  }

  // ---------- one frame ----------
  function step(trays, env, opt){
    const o = Object.assign({}, OPT, opt, env.gap !== undefined ? {gap: env.gap} : {});
    OBST = (env.obstacles || []).map(simple);
    const live = trays.filter(t => !t.hidden && t.chain);
    const B = env.bounds, obstacles = OBST, pad = env.pad || 0, obBoxes = obstacles.map(ob => [ob, aabb(ob, 0)]);
    const rigidOf = new Map(live.map(t => [t, !!env.rigid(t)]));
    const isRigid = t => rigidOf.get(t);
    const E = Object.assign({}, env, {rigid: isRigid});
    let moved = 0;
    // a solid tray gliding after a flick: it stops against a wall, the fan, the lantern or a locked tray, and against
    // a crowd that cannot get out of its way; it never glides over or through them
    const gliding = live.filter(t => isRigid(t) && env.coast && env.coast(t) && !(env.target && env.target(t)) && !(env.locked && env.locked(t)) && Math.hypot(t.chain.vx, t.chain.vy) > 0.01);
    for(let s = 0; s < o.substeps; s++){
      const glideFrom = gliding.map(t => ({t, x: t.cx, y: t.cy, ov: trayOverlap(t, live)}));
      // the body: kinematic when dragged, still when solid, otherwise it coasts and slows
      for(const t of live){
        const c = t.chain, rigid = isRigid(t), tgt = env.target ? env.target(t) : null;
        if(env.locked && env.locked(t)){ c.vx = 0; c.vy = 0; continue; }   // locked is locked: it stays exactly where and as it is
        const ox = t.cx, oy = t.cy;
        if(tgt){ t.cx = tgt[0]; t.cy = tgt[1]; c.vx = 0; c.vy = 0; }
        else if(rigid && !(env.coast && env.coast(t))){ c.vx = 0; c.vy = 0; }
        else {   // free, or solid but coasting after a flick
          c.vx *= o.friction; c.vy *= o.friction;
          const sp = Math.hypot(c.vx, c.vy); if(sp > o.maxSpeed){ c.vx *= o.maxSpeed/sp; c.vy *= o.maxSpeed/sp; }
          if(sp < 0.01){ c.vx = 0; c.vy = 0; }
          if(rigid && (c.vx || c.vy)){
            const want = [t.cx + c.vx, t.cy + c.vy], got = clearOfFixed(t, want, trays, env, o);
            if(Math.hypot(got[0] - want[0], got[1] - want[1]) > 0.5){ c.vx = 0; c.vy = 0; }   // it met something fixed: it stops there
            t.cx = got[0]; t.cy = got[1];
          } else { t.cx += c.vx; t.cy += c.vy; }
        }
        // keep the TV box itself on the counter
        const mx = t.a + (t.rim || 0) + pad + o.boxMargin + o.wallRoom, my = t.b + (t.rim || 0) + pad + o.boxMargin + o.wallRoom;   // the TV box, with its frame clearance, stays on the counter; the frame meets the walls
        let ex = mx, ey = my;
        if(rigid){ for(const r of c.R){ ex = Math.max(ex, Math.abs(r[0]) + t.r); ey = Math.max(ey, Math.abs(r[1]) + t.r); } }   // a solid frame cannot flatten, so its whole frame stays on the counter
        ex = Math.min(ex, (B.x1 - B.x0)/2); ey = Math.min(ey, (B.y1 - B.y0)/2);   // a frame bigger than the counter stays centred rather than flipping
        const nx = Math.min(B.x1 - ex, Math.max(B.x0 + ex, t.cx)), ny = Math.min(B.y1 - ey, Math.max(B.y0 + ey, t.cy));
        if(nx !== t.cx) c.vx = 0; if(ny !== t.cy) c.vy = 0;
        t.cx = nx; t.cy = ny;
        const dx = t.cx - ox, dy = t.cy - oy;
        if(dx || dy) for(const p of c.P){ p[0] += dx; p[1] += dy; }
        moved = Math.max(moved, Math.hypot(dx, dy));
      }
      for(const t of live){ t.chain.fx = 0; t.chain.fy = 0; }
      for(let it = 0; it < o.iterations; it++){
        // 1. shape memory: solid trays hold their exact shape; others ease back toward it
        for(const t of live){
          const c = t.chain, k = isRigid(t) ? (env.locked && env.locked(t) ? 0 : 1) : o.restK;   // a locked frame keeps the very shape it was locked in
          if(!k) continue;
          for(let i = 0; i < c.P.length; i++){ const p = c.P[i], r = c.R[i]; p[0] += (t.cx + r[0] - p[0])*k; p[1] += (t.cy + r[1] - p[1])*k; }
        }
        // 2. frame against frame
        contacts(live, E, o);
        // 3. walls and fixed furniture (the fan, the lantern): the frame lies flat against them
        for(const t of live){
          if(isRigid(t)) continue;
          const r = t.r, c = t.chain, P = c.P, n = P.length;
          for(const p of P){
            if(p[0] < B.x0 + r){ c.fx += B.x0 + r - p[0]; p[0] = B.x0 + r; } if(p[0] > B.x1 - r){ c.fx -= p[0] - (B.x1 - r); p[0] = B.x1 - r; }
            if(p[1] < B.y0 + r){ c.fy += B.y0 + r - p[1]; p[1] = B.y0 + r; } if(p[1] > B.y1 - r){ c.fy -= p[1] - (B.y1 - r); p[1] = B.y1 - r; }
          }
          if(!obstacles.length) continue;
          const near = obBoxes.filter(([ob, bx]) => overlaps(bx, aabb(P, r + o.gap))).map(([ob]) => ob);   // only furniture this frame is anywhere near
          if(!near.length) continue;
          const pt = [0, 0];
          for(let i = 0; i < n; i++){
            const a = P[i], b = P[(i+1) % n];
            for(let k = 0; k < c.m[i]; k++){
              const u = k/c.m[i]; pt[0] = a[0] + (b[0]-a[0])*u; pt[1] = a[1] + (b[1]-a[1])*u;
              for(const ob of near){
                const h = nearest(ob, pt), depth = r + o.gap - h.d;
                if(depth > 0){ move(a, b, u, h.n[0]*depth, h.n[1]*depth); c.fx += h.n[0]*depth; c.fy += h.n[1]*depth;
                  pt[0] = a[0] + (b[0]-a[0])*u; pt[1] = a[1] + (b[1]-a[1])*u; }
              }
            }
          }
        }
        // 4. sides keep their length (chain: never longer; rigid: within the slider's travel); hinges stay within their bend
        for(const t of live){ if(!isRigid(t)){ for(let k = 0; k < 3; k++){ hinges(t.chain, o); links(t.chain, o); } } }
        // 4b. walls once more, so a side pulled taut cannot end up past a wall
        for(const t of live){ if(!isRigid(t)) walls(t, B); }
        // 5. last word: nothing enters the TV box
        for(const t of live){ if(!isRigid(t)) guardBox(t, o, pad); }
      }
      // a closing contact pass, so the shape settles with frames apart rather than with whatever the
      // last constraint left; then the TV boxes once more
      contacts(live, E, o);
      for(const t of live){ if(isRigid(t)) continue; walls(t, B); guardBox(t, o, pad); }
      // the body answers the contact force: everything that pushed on its frame this step, taken
      // together, nudges the whole tray, slower the heavier it is. A nudge, not a launch: speed only ever
      // comes from a flick, so a tray resting against a wall or a neighbour settles instead of drifting.
      for(const t of live){
        const c = t.chain;
        if(isRigid(t) || (env.target && env.target(t))) continue;
        let fx = c.fx/o.iterations*o.bodyK/c.mass, fy = c.fy/o.iterations*o.bodyK/c.mass;
        const f = Math.hypot(fx, fy); if(f > o.maxNudge){ fx *= o.maxNudge/f; fy *= o.maxNudge/f; }
        if(Math.hypot(fx, fy) < 0.001) continue;
        // a tray squeezed from both sides must not be nudged into the one it cannot move: a nudge that would press
        // it further into any other frame is not taken
        const ov0 = trayOverlap(t, live), x0 = t.cx, y0 = t.cy;
        shove(t, fx, fy, B);
        if(trayOverlap(t, live) > ov0 + 0.25){ const ux = x0 - t.cx, uy = y0 - t.cy; t.cx = x0; t.cy = y0; for(const p of c.P){ p[0] += ux; p[1] += uy; } }
      }
      // a nudge carries the frame with it, so put any corner it carried past a wall back on the wall
      // the walls have the last word: they are impenetrable (Josie: "four solid, invisible walls"); the box guard
      // runs just before them, so at a wall a frame can sit a hair closer to its own screen, never past the wall
      for(const t of live){ if(isRigid(t)) continue; settleOnWalls(t, B, o, pad); }
      // a gliding tray that could only go on by pressing frames into each other stops where it was
      for(const g of glideFrom){
        if(trayOverlap(g.t, live) > g.ov + 0.5){ const ux = g.x - g.t.cx, uy = g.y - g.t.cy; g.t.cx = g.x; g.t.cy = g.y; for(const p of g.t.chain.P){ p[0] += ux; p[1] += uy; } g.t.chain.vx = 0; g.t.chain.vy = 0; }
      }
    }
    for(const t of live){
      const c = t.chain;
      let dent = 0;
      for(let i = 0; i < c.P.length; i++) dent = Math.max(dent, Math.hypot(c.P[i][0] - t.cx - c.R[i][0], c.P[i][1] - t.cy - c.R[i][1]));
      c.dent = dent;
      moved = Math.max(moved, Math.hypot(c.vx, c.vy));
      publish(t, o);
    }
    return moved;
  }

  // Move a tray aside only if that does not press it further into any other frame (or past a wall).
  function shoveClear(u, dx, dy, B, live, lean){
    const ov0 = trayOverlap(u, live), x0 = u.cx, y0 = u.cy;
    shove(u, dx, dy, B);
    if(trayOverlap(u, live) > Math.max(ov0 + 0.25, lean || 0)){ const ux = x0 - u.cx, uy = y0 - u.cy; u.cx = x0; u.cy = y0; for(const p of u.chain.P){ p[0] += ux; p[1] += uy; } return false; }
    return true;
  }
  // How far tray t and any other frame reach into each other (both ways), 0 when apart.
  function trayOverlap(t, live){
    let worst = 0; const bt = aabb(t.chain.P, t.r + 1);
    for(const u of live){ if(u === t) continue; if(!overlaps(bt, aabb(u.chain.P, u.r + 1))) continue;
      worst = Math.max(worst, pairOverlap(t, u), pairOverlap(u, t)); }
    return worst;
  }
  function pairOverlap(A, Bt){
    const reach = A.r + Bt.r, needBox = A.r + (Bt.rim || 0), bb = aabb(Bt.chain.P, reach + 1), PA = A.chain.P, n = PA.length, p = [0, 0];
    let worst = 0;
    for(let i = 0; i < n; i++){
      const pa = PA[i], pb = PA[(i+1) % n], m = A.chain.m[i];
      if(Math.max(pa[0], pb[0]) < bb[0] || Math.min(pa[0], pb[0]) > bb[2] || Math.max(pa[1], pb[1]) < bb[1] || Math.min(pa[1], pb[1]) > bb[3]) continue;
      for(let k = 0; k < m; k++){
        const u = k/m; p[0] = pa[0] + (pb[0]-pa[0])*u; p[1] = pa[1] + (pb[1]-pa[1])*u;
        if(p[0] < bb[0] || p[0] > bb[2] || p[1] < bb[1] || p[1] > bb[3]) continue;
        worst = Math.max(worst, reach - nearest(Bt.chain.P, p).d);
        worst = Math.max(worst, needBox - boxField([p[0] - Bt.cx, p[1] - Bt.cy], Bt.a, Bt.b).d);
      }
    }
    return worst;
  }
  function contacts(live, env, o){
    const boxes = live.map(t => aabb(t.chain.P, t.r + o.gap));
    for(let a = 0; a < live.length; a++) for(let b = a + 1; b < live.length; b++){
      if(!overlaps(boxes[a], boxes[b])) continue;
      press(live[a], live[b], env, o); press(live[b], live[a], env, o);
    }
  }

  // Points of A's frame that reach into B. The push is shared by weight; a solid frame takes none of it.
  // A's point moves out (along a rigid side, shared by the side's two corners, see move()); on B's side the push
  // lands on the two corners of the side it hit, split by where along that side it landed: hit near one end and
  // that end swings in, hit in the middle and the side slides in.
  function press(A, Bt, env, o){
    const ra = env.rigid(A), rb = env.rigid(Bt);
    if(ra && rb) return;
    const cA = A.chain, cB = Bt.chain, PA = cA.P, PB = cB.P, reach = A.r + Bt.r + o.gap;
    const wA = ra ? 0 : rb ? 1 : cB.mass/(cA.mass + cB.mass), wB = 1 - wA;
    // a screen is solid to everyone: a frame that reaches another tray's TV box shoves that whole tray
    const needBox = A.r + (Bt.rim || 0) + 2;
    const bb = aabb(PB, reach + 1), hx = Bt.a + needBox + 1, hy = Bt.b + needBox + 1;
    const n = PA.length, p = [0, 0];
    for(let i = 0; i < n; i++){
      const a = PA[i], b = PA[(i+1) % n], m = cA.m[i];
      // most sides are nowhere near the other frame: skip them before the exact (and costly) distance test
      if(Math.max(a[0], b[0]) < bb[0] || Math.min(a[0], b[0]) > bb[2] || Math.max(a[1], b[1]) < bb[1] || Math.min(a[1], b[1]) > bb[3]) continue;
      for(let k = 0; k < m; k++){
        const u = k/m;
        p[0] = a[0] + (b[0]-a[0])*u; p[1] = a[1] + (b[1]-a[1])*u;
        if(p[0] < bb[0] || p[0] > bb[2] || p[1] < bb[1] || p[1] > bb[3]) continue;
        if(Math.abs(p[0] - Bt.cx) < hx && Math.abs(p[1] - Bt.cy) < hy){
          const fb = boxField([p[0] - Bt.cx, p[1] - Bt.cy], Bt.a, Bt.b), dBox = needBox - fb.d;
          if(dBox > 0){
            if(wA > 0) move(a, b, u, fb.n[0]*dBox*wA, fb.n[1]*dBox*wA);
            if(wB > 0) shove(Bt, -fb.n[0]*dBox*wB, -fb.n[1]*dBox*wB, env.bounds);
            p[0] = a[0] + (b[0]-a[0])*u; p[1] = a[1] + (b[1]-a[1])*u;
          }
        }
        const h = nearest(PB, p), depth = reach - h.d;
        if(depth <= 0) continue;
        if(wA > 0){ move(a, b, u, h.n[0]*depth*wA, h.n[1]*depth*wA); cA.fx += h.n[0]*depth*wA; cA.fy += h.n[1]*depth*wA; }
        if(wB > 0){
          const qi = PB[h.i], qj = PB[h.j], f = depth*wB;
          cB.fx -= h.n[0]*f; cB.fy -= h.n[1]*f;
          qi[0] -= h.n[0]*f*(1 - h.u); qi[1] -= h.n[1]*f*(1 - h.u);
          qj[0] -= h.n[0]*f*h.u;       qj[1] -= h.n[1]*f*h.u;
        }
      }
    }
  }

  // Move a whole tray, frame and all, but only as far as its TV box stays on the counter. What the
  // wall refuses is simply not done: the frames stay pressed, and overlap() reports it.
  // Nor is a tray shoved into the fan or the lantern (the obstacles of the step under way): it goes only as far as
  // keeps it no closer to them than it already was, or a gap less a few px.
  let OBST = [];
  // The fan and lantern arrive as one many-sided outline; for the physics a simpler one does (corners kept, points
  // that lie within 2.5 px of a straight run dropped), made once per outline.
  const SIMPLE = new WeakMap();
  function simple(P){
    let q = SIMPLE.get(P); if(q) return q;
    const keep = new Array(P.length).fill(false);
    const dp = (i, j) => { let worst = -1, k = -1; const a = P[i], b = P[j % P.length], e = sub(b, a), l = len(e) || 1;
      for(let m = i + 1; m < j; m++){ const d = Math.abs(crs(e, sub(P[m], a)))/l; if(d > worst){ worst = d; k = m; } }
      if(worst > 2.5){ keep[k] = true; dp(i, k); dp(k, j); } };
    keep[0] = true; dp(0, P.length);
    q = P.filter((_, i) => keep[i]); if(q.length < 3) q = P;
    SIMPLE.set(P, q); return q;
  }
  function shove(t, dx, dy, B){
    const ex = t.a + (t.rim || 0) + 2 + OPT.boxMargin + OPT.wallRoom, ey = t.b + (t.rim || 0) + 2 + OPT.boxMargin + OPT.wallRoom;
    let nx = Math.min(B.x1 - ex, Math.max(B.x0 + ex, t.cx + dx)), ny = Math.min(B.y1 - ey, Math.max(B.y0 + ey, t.cy + dy));
    if(OBST.length && t.chain){
      const floor0 = OPT.gap - 6, span = t.chain.span || (t.chain.span = Math.max(...t.chain.R.map(r => Math.hypot(r[0], r[1]))) + t.r);
      for(const ob of OBST){
        if(nearest(ob, [nx, ny]).d - span > floor0 + 1) continue;   // nowhere near it: the cheap test settles most shoves
        const floor = Math.min(floor0, polyGap(restWorld(t), t.r, ob, 0, floor0).d);
        if(polyGap(restWorld(t, [nx, ny]), t.r, ob, 0, floor).d >= floor - 0.01) continue;
        const hx = t.cx + (nx - t.cx)*0.5, hy = t.cy + (ny - t.cy)*0.5;   // half as far, or not at all
        if(polyGap(restWorld(t, [hx, hy]), t.r, ob, 0, floor).d >= floor - 0.01){ nx = hx; ny = hy; } else { nx = t.cx; ny = t.cy; }
      }
    }
    const mx = nx - t.cx, my = ny - t.cy;
    if(!mx && !my) return;
    t.cx = nx; t.cy = ny;
    for(const q of t.chain.P){ q[0] += mx; q[1] += my; }
  }

  // Side lengths. Chain: like real chain, a link cannot stretch but can go slack (no wrinkles from a dent).
  // Rigid: a side is on a slider, so it can run a little shorter or longer, within its travel.
  function links(c, o){
    const P = c.P, n = P.length;
    for(let i = 0; i < n; i++){
      const a = P[i], b = P[(i+1)%n], dx = b[0]-a[0], dy = b[1]-a[1], L = Math.hypot(dx, dy) || 1e-6;
      const hi = c.L0[i]*c.hi, lo = c.L0[i]*c.lo;
      let want;
      if(L > hi) want = hi; else if(L < lo) want = lo; else continue;
      const k = (L - want)/L*0.5*o.linkK;
      a[0] += dx*k; a[1] += dy*k; b[0] -= dx*k; b[1] -= dy*k;
    }
  }

  // A hinge bent past its limit is eased back toward its own resting bend. Each hinge remembers where
  // it sits relative to its two neighbours at rest (an offset from the midpoint of the chord between
  // them, in that chord's own frame); an over-bent hinge is moved back toward that offset in the
  // chord's current frame. This keeps dents rounded-but-angled and stops the frame folding over itself.
  function hinges(c, o){
    const P = c.P, R = c.R, n = P.length, lim = c.rigid ? o.cornerBend : o.maxBend;
    for(let i = 0; i < n; i++){
      const ia = (i - 1 + n) % n, ic = (i + 1) % n, a = P[ia], b = P[i], cc = P[ic];
      const u = sub(b, a), v = sub(cc, b);
      const ang = Math.atan2(crs(u, v), dot(u, v)), excess = ang - c.theta[i];
      const over = Math.abs(excess) - lim;
      if(over <= 0) continue;
      const ra = R[ia], rb = R[i], rc = R[ic];
      const rch = sub(rc, ra), rl = len(rch) || 1, rx = [rch[0]/rl, rch[1]/rl], ry = [-rx[1], rx[0]];
      const roff = sub(rb, [(ra[0]+rc[0])/2, (ra[1]+rc[1])/2]), ox = dot(roff, rx)/rl, oy = dot(roff, ry)/rl;
      const ch = sub(cc, a), cl = len(ch) || 1, cx = [ch[0]/cl, ch[1]/cl], cy = [-cx[1], cx[0]];
      const mid = [(a[0]+cc[0])/2, (a[1]+cc[1])/2];
      const want = [mid[0] + (cx[0]*ox + cy[0]*oy)*cl, mid[1] + (cx[1]*ox + cy[1]*oy)*cl];
      const f = Math.min(1, over/Math.max(Math.abs(excess), 1e-3) + 0.15)*o.bendK;
      b[0] += (want[0] - b[0])*f; b[1] += (want[1] - b[1])*f;
    }
  }

  // Nothing of the frame may enter the TV box, and the frame must keep surrounding it. Each corner stays on its
  // own side: measured along the ray from the tray's centre through where that corner sits at rest, it must
  // stay beyond the box's edge (less the room the floor adds back). So however hard a frame is crushed, into
  // a corner or between two trays, it can flatten and dent but never fold across its own screen. A rigid side
  // is checked along its whole length too, since its two corners can be clear while its middle cuts a corner
  // of the box.
  function guardBox(t, o, pad){
    const need = (t.rim || 0) + (pad || 0) - t.r + o.boxMargin, c = t.chain, P = c.P, n = P.length;
    for(let i = 0; i < n; i++){
      const p = P[i], q = [p[0] - t.cx, p[1] - t.cy], needV = c.rigid ? Math.min(need, c.restV[i]) : need;
      // not inside the box
      const f = boxField(q, t.a, t.b);
      if(f.d < needV){ const k = needV - f.d; p[0] += f.n[0]*k; p[1] += f.n[1]*k; q[0] = p[0] - t.cx; q[1] = p[1] - t.cy; }
      // and on its own side of it
      const r = c.R[i], rl = len(r) || 1, d = [r[0]/rl, r[1]/rl];
      const exit = Math.min(Math.abs(d[0]) > 1e-6 ? t.a/Math.abs(d[0]) : Infinity, Math.abs(d[1]) > 1e-6 ? t.b/Math.abs(d[1]) : Infinity);
      const sMin = Math.max(0, Math.min(exit + need, rl)), sNow = dot(q, d);   // never further out than the corner sits at rest
      if(sNow < sMin){ const k = sMin - sNow; p[0] += d[0]*k; p[1] += d[1]*k; }
    }
    if(!c.rigid) return;
    // the box's own corners: a straight side cutting across a corner of the box must leave it within reach of the
    // floor's rounding (a side can be clear of the box's edges and still cut off its corner)
    const fr = Math.max(1, t.r - (t.rim || 0) - FLOOR_PAD) - o.boxMargin;
    for(let k = 0; k < 4; k++){
      const sx = k === 0 || k === 3 ? -1 : 1, sy = k < 2 ? -1 : 1, q = [t.cx + sx*t.a, t.cy + sy*t.b];
      const h = nearest(P, q), allow = Math.max(fr, c.restC[k]);
      if(h.d > allow){ const kk = h.d - allow; move(P[h.i], P[h.j], h.u, h.n[0]*kk, h.n[1]*kk); }
    }
    for(let i = 0; i < n; i++){
      const a = P[i], b = P[(i+1) % n], needS = Math.min(need, c.restS[i]);
      const ax = a[0] - t.cx, ay = a[1] - t.cy, bx = b[0] - t.cx, by = b[1] - t.cy, hx = t.a + needS, hy = t.b + needS;
      // a side wholly beyond one edge of the box (plus clearance) cannot come too close anywhere along it
      if((ax > hx && bx > hx) || (ax < -hx && bx < -hx) || (ay > hy && by > hy) || (ay < -hy && by < -hy)) continue;
      const u = closestOnSide(a, b, t.cx, t.cy, t.a, t.b), f = segBox(a, b, u, t.cx, t.cy, t.a, t.b);
      if(f.d < needS){ const k = needS - f.d; move(a, b, u, f.n[0]*k, f.n[1]*k); }
    }
  }

  // What the renderer and the page read: the outline, the floor, and a flag that the TV box is whole.
  function publish(t, o){
    const P = t.chain.P.map(p => [p[0], p[1]]);
    t.q = P; t.poly = P;
    const fr = Math.max(1, t.r - (t.rim || 0) - (o && o.pad !== undefined ? o.pad : FLOOR_PAD));
    t.floor = {q: P, r: fr, poly: P};
    t.ok = true;
  }

  // ---------- crowding: shrink when crushed, grow back with room ----------
  // A tray crushed for a while (a dent held past squeezeAt, or a tray being dragged through it) gives up a little
  // of its size each frame, contents and all, down to a floor: never below minSqueeze of its set size, nor below
  // what its contents need (env.minScale). Free again for a while, it grows back slowly. The selected tray (solid)
  // inflates back quickly and pushes the others; if they have nowhere left to go it stops. A locked tray keeps
  // its size. Returns true when any tray changed size. Needs the shapes module (S) to refit the frame.
  function squeeze(trays, env, S, opt){
    const o = Object.assign({}, OPT, opt);
    let changed = false;
    for(const t of trays){
      if(t.hidden || !t.chain || !t.reqW) continue;
      const c = t.chain;
      if(env.locked && env.locked(t)){ c.crowd = 0; continue; }
      if(env.target && env.target(t)) continue;   // the tray in the hand keeps its size
      const s0 = t.scale || 1, solid = !!env.rigid(t), asked = (t.squeezeReq || 0) > 0;
      const floor = Math.min(1, Math.max(0.3, env.minScale ? env.minScale(t) || o.minSqueeze : o.minSqueeze));   // the contents say how far they can go (a video further than a page of text)
      if(asked) t.squeezeReq--;
      let s = s0;
      if(!solid && (asked || c.dent > o.squeezeAt || strain([t]) > 0.15)){
        c.crowd = (c.crowd || 0) + 1; c.calm = 0;
        if(asked || c.crowd > o.crowdFrames) s = Math.max(floor, s0*(1 - o.squeezeRate));
      } else if(solid || (c.dent < o.relaxAt && strain([t]) < 0.02)){
        c.crowd = 0; c.calm = (c.calm || 0) + 1;
        if(s0 < 1 && (solid || c.calm > o.calmFrames)) s = Math.min(1, s0*(1 + (solid ? o.inflateRate : o.growRate)));
      } else { c.crowd = 0; c.calm = 0; }   // touching but not crushed: hold
      if(s === s0) continue;
      if(s > s0 && solid){
        // inflating pushes the others; if they have nowhere to go, stop
        const before = overlap(trays, o), fixedGap = () => Math.min(o.gap, ...(env.obstacles || []).map(ob => polyGap(restWorld(t), t.r, ob, 0, o.gap).d),
          ...trays.filter(u => u !== t && !u.hidden && u.chain && env.locked && env.locked(u)).map(u => polyGap(restWorld(t), t.r, u.chain.P, u.r, o.gap).d));
        const fg0 = fixedGap(); rescale(t, S, s, o);
        for(let k = 0; k < 3; k++) step(trays, env, opt);
        // nor may it swell into the fan, the lantern or a locked tray
        if(overlap(trays, o) > Math.max(before, 4) + 0.5 || fixedGap() < Math.min(fg0, o.gap) - 0.5){ rescale(t, S, s0, o); c.calm = -60; continue; }
      } else rescale(t, S, s, o);
      // a refitted frame has a new corner radius, so it meets the walls and its own box at a new place
      settleOnWalls(t, env.bounds, o, env.pad || 0); publish(t, o);
      changed = true;
    }
    return changed;
  }
  // Refit a tray's frame at a new share of its set size, keeping any dent it has (scaled with it).
  function rescale(t, S, s, opt){
    const c = t.chain, k = s/(t.scale || 1), cx = t.cx, cy = t.cy;
    const P = c.P.map(p => [cx + (p[0] - cx)*k, cy + (p[1] - cy)*k]);
    t.scale = s; S.setBox(t, t.reqW*s, t.reqH*s);
    attach(t, S, Object.assign({}, opt, {edges: c.rigid ? 'rigid' : 'chain'}));
    if(t.chain.P.length === P.length){ t.chain.P = P; publish(t, opt); }
  }
  // Trays whose frames come within margin px of t's frame (for a drag that needs its neighbours to give way).
  function neighbours(t, trays, margin){
    const out = []; if(!t.chain) return out;
    const A = aabb(t.chain.P, t.r + (margin || 0));
    for(const u of trays){
      if(u === t || u.hidden || !u.chain) continue;
      if(!overlaps(A, aabb(u.chain.P, u.r))) continue;
      const reach = t.r + u.r + (margin || 0);
      if(u.chain.P.some(p => nearest(t.chain.P, p).d < reach) || t.chain.P.some(p => nearest(u.chain.P, p).d < reach)) out.push(u);
    }
    return out;
  }

  // ---------- fixed things: walls, the fan, the lantern, locked trays ----------
  // A solid tray (one in the hand, or the selected one gliding after a flick) never goes past a wall, into the fan or
  // the lantern, or into a locked tray: it is held against them and slides along them.

  // Room between two rounded convex outlines (world coords, corner radii ra and rb): {d, n}. d is the room between
  // their outer edges (negative where they overlap), n the unit direction from A to B along which to part them.
  // With `need`, two outlines found further apart than that are reported only as being at least that far apart
  // (d >= need), which is all a caller asking "are they within need?" wants, and is much quicker.
  function polyGap(PA, ra, PB, rb, need){
    let minOv = Infinity, ax = null, sep = false;
    const cA = centroid(PA), cB = centroid(PB);
    for(const P of [PA, PB]){
      for(let i = 0, n = P.length; i < n; i++){
        const a = P[i], b = P[(i+1) % n], ex = b[0]-a[0], ey = b[1]-a[1], l = Math.hypot(ex, ey); if(l < 1e-9) continue;
        const nx = ey/l, ny = -ex/l;
        let a0 = Infinity, a1 = -Infinity, b0 = Infinity, b1 = -Infinity;
        for(const p of PA){ const s = p[0]*nx + p[1]*ny; if(s < a0) a0 = s; if(s > a1) a1 = s; }
        for(const p of PB){ const s = p[0]*nx + p[1]*ny; if(s < b0) b0 = s; if(s > b1) b1 = s; }
        const ov = Math.min(a1 - b0, b1 - a0);
        if(ov < 0){ if(need !== undefined && -ov - ra - rb >= need) return {d: -ov - ra - rb, n: (cB[0]-cA[0])*nx + (cB[1]-cA[1])*ny >= 0 ? [nx, ny] : [-nx, -ny]};
          sep = true; break; }
        if(ov < minOv){ minOv = ov; const s = (cB[0]-cA[0])*nx + (cB[1]-cA[1])*ny; ax = s >= 0 ? [nx, ny] : [-nx, -ny]; }
      }
      if(sep) break;
    }
    if(!sep) return {d: -minOv - ra - rb, n: ax || [1, 0]};
    let best = Infinity, from = null, to = null;   // apart: the nearest pair of points, one on each outline
    const scan = (P, Q, flip) => {
      for(const p of P) for(let i = 0, n = Q.length; i < n; i++){
        const a = Q[i], b = Q[(i+1) % n], e = sub(b, a), ee = dot(e, e), u = ee > 0 ? Math.max(0, Math.min(1, dot(sub(p, a), e)/ee)) : 0;
        const qx = a[0] + e[0]*u, qy = a[1] + e[1]*u, d = Math.hypot(p[0]-qx, p[1]-qy);
        if(d < best){ best = d; from = flip ? [qx, qy] : p; to = flip ? p : [qx, qy]; }
      }
    };
    scan(PA, PB, false); scan(PB, PA, true);
    const v = sub(to, from), l = len(v);
    if(l > 1e-9) return {d: best - ra - rb, n: [v[0]/l, v[1]/l]};
    const w = sub(cB, cA), wl = len(w) || 1;
    return {d: best - ra - rb, n: [w[0]/wl, w[1]/wl]};
  }
  function centroid(P){ let x = 0, y = 0; for(const p of P){ x += p[0]; y += p[1]; } return [x/P.length, y/P.length]; }
  const restWorld = (t, at) => { const cx = at ? at[0] : t.cx, cy = at ? at[1] : t.cy; return t.chain.R.map(r => [cx + r[0], cy + r[1]]); };
  // How far a solid tray's centre may go toward each wall: its whole frame stays on the counter.
  function solidWallBox(t, B){
    let ex = 0, ey = 0;
    for(const r of t.chain.R){ ex = Math.max(ex, Math.abs(r[0]) + t.r); ey = Math.max(ey, Math.abs(r[1]) + t.r); }
    ex = Math.min(ex, (B.x1 - B.x0)/2); ey = Math.min(ey, (B.y1 - B.y0)/2);
    return [B.x0 + ex, B.y0 + ey, B.x1 - ex, B.y1 - ey];
  }
  const clampTo = (w, x, y) => [Math.min(w[2], Math.max(w[0], x)), Math.min(w[3], Math.max(w[1], y))];
  // Where solid tray t can be put near `at`: on the counter, a full gap clear of the fan, the lantern and every locked
  // tray. Whatever it met pushes it back out along the contact, so it slides along rather than sinking in.
  function clearOfFixed(t, at, trays, env, o){
    const fixed = [];
    for(const ob of env.obstacles || []) fixed.push([ob, 0]);
    for(const u of trays){ if(u !== t && !u.hidden && u.chain && env.locked && env.locked(u)) fixed.push([u.chain.P, u.r]); }
    const W = solidWallBox(t, env.bounds);
    let p = clampTo(W, at[0], at[1]);
    for(let it = 0; it < 8; it++){
      let worst = 0;
      for(const [F, rf] of fixed){
        const g = polyGap(restWorld(t, p), t.r, F, rf), pen = o.gap - g.d;
        if(pen > 0.05){ p = clampTo(W, p[0] - g.n[0]*pen, p[1] - g.n[1]*pen); worst = Math.max(worst, pen); }
      }
      if(worst < 0.25) break;
    }
    return p;
  }

  // ---------- room for a tray ----------
  // How much room tray t would have at centre `at`, at share `s` of its set size (1 = as it is): the least gap
  // between its rest outline and any other open tray's frame, the fan, the lantern or a wall (negative where it
  // would overlap). Used to open a tray where it fits, at a size that fits, without pressing into anything.
  function roomAt(t, at, s, trays, env){
    const k = s/(t.scale || 1), R = t.chain.R.map(r => [at[0] + r[0]*k, at[1] + r[1]*k]), rr = t.r*k, B = env.bounds;
    let worst = Infinity;
    for(const p of R){ worst = Math.min(worst, p[0] - rr - B.x0, B.x1 - p[0] - rr, p[1] - rr - B.y0, B.y1 - p[1] - rr); }
    for(const ob of env.obstacles || []) worst = Math.min(worst, polyGap(R, rr, ob, 0, 40).d);
    for(const u of trays){ if(u === t || u.hidden || !u.chain) continue; worst = Math.min(worst, polyGap(R, rr, u.chain.P, u.r, 40).d); }
    return worst;
  }

  // ---------- dragging through a crowd ----------
  // Everything a move might need undoing: where each tray is, its frame, its speed.
  function snapshot(trays){ return trays.filter(t => t.chain).map(t => ({t, cx: t.cx, cy: t.cy, vx: t.chain.vx, vy: t.chain.vy, P: t.chain.P.map(p => [p[0], p[1]])})); }
  function restore(snap){ for(const s of snap){ s.t.cx = s.cx; s.t.cy = s.cy; s.t.chain.vx = s.vx; s.t.chain.vy = s.vy; s.t.chain.P = s.P.map(p => [p[0], p[1]]); publish(s.t); } }
  // One frame of a drag. hand = {t, want:[x,y] (where the pointer wants the tray), at:[x,y] (where it is)}; env.target
  // must return hand.at for hand.t. The tray moves toward the pointer, a step at a time. A step that would push
  // frames into each other is undone, the trays in the way are asked to give way (squeeze() shrinks them over the
  // next frames, and the push slides them aside), and the next frame tries again with a shorter step. So a tray
  // can be drawn slowly through a full counter, and a drag only stops for good when nothing can give way.
  // How far a tray's TV box can move from where it is in direction n (unit) before a wall stops it.
  function roomToWall(u, n, B){
    const ex = u.a + (u.rim || 0) + 2 + OPT.boxMargin + OPT.wallRoom, ey = u.b + (u.rim || 0) + 2 + OPT.boxMargin + OPT.wallRoom;
    let d = Infinity;
    if(n[0] > 1e-6) d = Math.min(d, (B.x1 - ex - u.cx)/n[0]); if(n[0] < -1e-6) d = Math.min(d, (B.x0 + ex - u.cx)/n[0]);
    if(n[1] > 1e-6) d = Math.min(d, (B.y1 - ey - u.cy)/n[1]); if(n[1] < -1e-6) d = Math.min(d, (B.y0 + ey - u.cy)/n[1]);
    return Math.max(0, d);
  }
  // How far a frame reaches from its centre along unit direction n.
  function reachAlong(u, n){ let m = 0; for(const r of u.chain.R) m = Math.max(m, Math.abs(r[0]*n[0] + r[1]*n[1])); return m*(u.scale ? 1 : 1) + u.r; }
  // A dragged tray parts the others like a bubble moving through bubbles: those in its path slide aside, toward
  // whichever of its flanks has more room, and those alongside it drift back into the space it leaves behind. So
  // the counter never jams with everything shoved against one wall while the other half stands empty.
  function flowAround(trays, env, hand, amount){
    const t = hand.t, dx = hand.want[0] - t.cx, dy = hand.want[1] - t.cy, L = Math.hypot(dx, dy);
    if(L < 0.5 || amount <= 0) return;
    const dir = [dx/L, dy/L], perp = [-dir[1], dir[0]], B = env.bounds;
    const tSide = reachAlong(t, perp), tLong = reachAlong(t, dir), live = trays.filter(u => !u.hidden && u.chain);
    // room beside the dragged tray on each flank, out to the walls
    const flank = side => roomToWall(t, [perp[0]*side, perp[1]*side], B);
    const roomPos = flank(1), roomNeg = flank(-1);
    for(const u of trays){
      if(u === t || u.hidden || !u.chain || (env.locked && env.locked(u))) continue;
      const rel = [u.cx - t.cx, u.cy - t.cy], ahead = rel[0]*dir[0] + rel[1]*dir[1], side = rel[0]*perp[0] + rel[1]*perp[1];
      const uSide = reachAlong(u, perp), uLong = reachAlong(u, dir);
      if(ahead < -(tLong + uLong) || ahead > tLong + uLong + 60) continue;   // well behind or well ahead: not involved yet
      const clear = tSide + uSide + 6;                                        // how far to the side it must be to let it pass
      const k = amount/Math.sqrt(u.chain.mass);
      if(Math.abs(side) < clear && ahead > 0){
        // in the path: slide aside, to its own side unless that flank has no room for it and the other has more
        let sgn = Math.sign(side) || (roomPos >= roomNeg ? 1 : -1);
        const need = 2*uSide*0.7;
        if((sgn > 0 ? roomPos : roomNeg) < need && (sgn > 0 ? roomNeg : roomPos) > (sgn > 0 ? roomPos : roomNeg)) sgn = -sgn;
        const m = Math.min(k*1.2, clear - Math.abs(side));
        shoveClear(u, perp[0]*sgn*m, perp[1]*sgn*m, B, live);
      } else if(Math.abs(side) >= clear - 12 && ahead > -(tLong + uLong) && ahead < tLong + uLong){
        // alongside: drift back into the space it is leaving
        shoveClear(u, -dir[0]*k*0.6, -dir[1]*k*0.6, B, live);
      }
    }
  }
  // When a drag is held up, the trays in the way look for somewhere to go: each tries a ring of directions and
  // distances and takes the nearest spot where it would overlap the least (others' frames, the tray coming
  // through, the walls), then glides toward it a few px a frame. So a full counter rearranges itself around the
  // tray coming through instead of jamming, and every tray still moves continuously (nothing jumps).
  function box4(P, pad, sh){ let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity; for(const p of P){ if(p[0] < x0) x0 = p[0]; if(p[0] > x1) x1 = p[0]; if(p[1] < y0) y0 = p[1]; if(p[1] > y1) y1 = p[1]; }
    const cx = (x0 + x1)/2, cy = (y0 + y1)/2, hx = (x1 - x0)/2*sh + pad, hy = (y1 - y0)/2*sh + pad; return [cx - hx, cy - hy, cx + hx, cy + hy]; }
  const ovA = (a, b) => Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]))*Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  function makeWay(trays, env, hand, o){
    const t = hand.t, dx = hand.want[0] - t.cx, dy = hand.want[1] - t.cy, L = Math.hypot(dx, dy);
    if(L < 0.5) return;
    const look = Math.min(L, 80), B = env.bounds, sh = 0.86;
    const tb = box4(t.chain.P, t.r + o.gap/2, sh), fut = [tb[0] + dx/L*look, tb[1] + dy/L*look, tb[2] + dx/L*look, tb[3] + dy/L*look];
    const sweep = [Math.min(tb[0], fut[0]), Math.min(tb[1], fut[1]), Math.max(tb[2], fut[2]), Math.max(tb[3], fut[3])];
    const others = trays.filter(u => u !== t && !u.hidden && u.chain);
    const boxes = new Map(others.map(u => [u, box4(u.chain.P, u.r + o.gap/2, sh)]));
    const furniture = (env.obstacles || []).map(ob => box4(ob, o.gap, 1));   // the fan, the lantern, the dock: never a place to go
    for(const u of others){
      if(env.locked && env.locked(u)) continue;
      const ub = boxes.get(u); if(!ovA(ub, sweep)) continue;
      const cost = (ox, oy) => { const b = [ub[0] + ox, ub[1] + oy, ub[2] + ox, ub[3] + oy]; let c = ovA(b, sweep)*3;
        for(const v of others){ if(v !== u) c += ovA(b, boxes.get(v)); } for(const f of furniture) c += 3*ovA(b, f); return c + 60*Math.hypot(ox, oy); };
      let best = [0, 0], bestC = cost(0, 0);
      for(let k = 0; k < 16; k++){
        const a = k*Math.PI/8, n = [Math.cos(a), Math.sin(a)], room = roomToWall(u, n, B);
        for(const d of [24, 48, 90, 140, 200, 280, 380, 500]){
          if(d > room) break;
          const c = cost(n[0]*d, n[1]*d); if(c < bestC){ bestC = c; best = [n[0]*d, n[1]*d]; }
        }
      }
      const bl = Math.hypot(best[0], best[1]); if(bl < 1) continue;
      const m = Math.min(bl, 7/Math.sqrt(u.chain.mass));
      shoveClear(u, best[0]/bl*m, best[1]/bl*m, B, trays.filter(v => !v.hidden && v.chain));
    }
  }
  function dragStep(trays, env, hand, opt){
    const o = Object.assign({}, OPT, opt), t = hand.t;
    OBST = (env.obstacles || []).map(simple);
    // where the hand wants it, but never past a wall, into the fan or the lantern, or into a locked tray
    const goal = clearOfFixed(t, hand.want, trays, env, o);
    const dx = goal[0] - hand.at[0], dy = goal[1] - hand.at[1], dist = Math.hypot(dx, dy);
    const L = hand.stepLen || 16, k = dist > L ? L/dist : 1, from = hand.at.slice();
    const fix = p => clearOfFixed(t, p, trays, env, o);
    if(dist < 0.25){ const moved = step(trays, env, opt); return {moved, blocked: false}; }
    const snap = snapshot(trays), before = pressure(trays, o);
    // the others start making way before the tray reaches them, harder while it is held up
    const g2 = Object.assign({}, hand, {want: goal});
    flowAround(trays, env, g2, Math.min(dist, L)*0.5 + (hand.blocked ? 3 : 0));
    hand.at = fix([from[0] + dx*k, from[1] + dy*k]);
    let moved = step(trays, env, opt);
    // A drag is held back only by frames passing into each other. A frame forced past its own stops (a side past
    // its travel, a corner past its swing) is not a reason to stop the hand: that tray is crushed, so it shrinks.
    const after = pressure(trays, o);
    for(const u of trays){ if(u !== t && !u.hidden && u.chain && strain([u]) > 0.15) u.squeezeReq = Math.max(u.squeezeReq || 0, 6); }
    // (measured against where the counter stood when the drag began, so overlap cannot creep up a little at a time)
    if(hand.base === undefined) hand.base = Math.max(4, before.overlap);
    if(after.overlap > hand.base + 0.5 && after.overlap > before.overlap + 0.05){
      restore(snap); hand.at = from;
      // straight on is blocked: try sliding along whatever is in the way, as a hand would steer around it, taking
      // the first angle that still gets closer and does not press frames into each other
      // (held up frame after frame, one angle a frame, in turn, so a long wait costs little time per frame)
      const base = Math.atan2(dy, dx), sl = Math.max(3, Math.min(L, dist)*0.7), angles = [0.5, -0.5, 1.0, -1.0];
      const turn = (hand.blocked || 0) > 2 ? [angles[(hand.blocked || 0) % 4]] : angles;
      for(const da of turn){
        const a = base + da, nxt = fix([from[0] + Math.cos(a)*sl, from[1] + Math.sin(a)*sl]);
        if(Math.hypot(goal[0] - nxt[0], goal[1] - nxt[1]) >= dist - 0.5) continue;
        hand.at = nxt;
        const mv = step(trays, env, opt), pa = pressure(trays, o);
        if(!(pa.overlap > hand.base + 0.5 && pa.overlap > before.overlap + 0.05)){ hand.blocked = (hand.blocked || 0) + 1; return {moved: mv, blocked: false, slid: true}; }
        restore(snap); hand.at = from;
      }
      const pressed = neighbours(t, trays, o.gap + 6);
      for(const u of pressed) u.squeezeReq = Math.max(u.squeezeReq || 0, 10);
      hand.stepLen = Math.max(2, L/2); hand.blocked = (hand.blocked || 0) + 1;
      // Tank tread (Josie: "roll over each other ... like tank tread"): each tray pressed against it rolls a few px
      // round it, along its edge, the way back past it into the space it is leaving if there is room that way, else
      // the other way; never into a wall, the fan or another frame
      const live = trays.filter(u => !u.hidden && u.chain), dir = [dx/dist, dy/dist];
      for(const u of pressed){
        if(env.locked && env.locked(u)) continue;
        const r = [u.cx - t.cx, u.cy - t.cy], rl = len(r) || 1, rn = [r[0]/rl, r[1]/rl];
        let tv = [-rn[1], rn[0]]; if(dot(tv, dir) > 0) tv = [-tv[0], -tv[1]];
        const st = 6/Math.sqrt(u.chain.mass), lean = 3;   // it may lean on the next tray (which the frames then push along), never pass into it
        if(!shoveClear(u, tv[0]*st + rn[0]*0.6, tv[1]*st + rn[1]*0.6, env.bounds, live, lean)) shoveClear(u, -tv[0]*st + rn[0]*0.6, -tv[1]*st + rn[1]*0.6, env.bounds, live, lean);
        // and the jam condenses: what it is pressed against squeezes a little too
        for(const v of neighbours(u, trays, o.gap + 6)) if(v !== t && !(env.locked && env.locked(v))) v.squeezeReq = Math.max(v.squeezeReq || 0, 6);
      }
      // the trays in the way look for somewhere to go; if that only presses them into others, they stay put
      if((hand.blocked || 0) % 3 === 1) makeWay(trays, env, g2, o);
      moved = step(trays, env, opt);   // the others still settle while the tray waits
      const ov2 = pressure(trays, o).overlap;
      if(ov2 > hand.base + 0.5 && ov2 > before.overlap + 0.05){ restore(snap); moved = 0; }
      return {moved, blocked: true};
    }
    hand.stepLen = Math.min(48, L*1.3); hand.blocked = 0;
    return {moved, blocked: false};
  }

  // ---------- settling and page helpers ----------
  function settle(trays, env, n){ for(let k = 0; k < (n || 400); k++){ if(step(trays, env) < 0.02 && k > 10) return k; } return n || 400; }

  // The screen's clip: the outline grown out to the floor edge, as a polygon path relative to origin.
  function clipPath(t, origin){
    const P = t.chain ? t.chain.P : t.q, n = P.length;
    const grow = t.floor ? t.floor.r : 1, o = signedArea(P) > 0 ? 1 : -1;
    let d = '';
    for(let i = 0; i < n; i++){
      const a = P[(i - 1 + n) % n], b = P[i], c = P[(i+1)%n];
      const e1 = sub(b, a), e2 = sub(c, b), l1 = len(e1) || 1, l2 = len(e2) || 1;
      // outward normals of the two sides meeting here, and their mitred average
      const n1 = [o*e1[1]/l1, -o*e1[0]/l1], n2 = [o*e2[1]/l2, -o*e2[0]/l2];
      let m = [n1[0] + n2[0], n1[1] + n2[1]]; const ml = len(m) || 1; m = [m[0]/ml, m[1]/ml];
      const k = grow/Math.max(0.35, dot(m, n1));
      d += (i ? 'L' : 'M') + (b[0] + m[0]*k - origin[0]).toFixed(1) + ' ' + (b[1] + m[1]*k - origin[1]).toFixed(1);
    }
    return "path('" + d + "Z')";
  }

  // How the outline near world point p has moved from where it would be at rest: [dx, dy, dAngle]. The point is
  // found on the rest outline (on whichever side it is nearest) and carried with that side, so a plaque on a
  // side that slides in moves in with it, and one on a side that swings turns with it.
  function anchorOffset(t, p){
    const c = t.chain; if(!c) return [0, 0, 0];
    const R = c.R, P = c.P, n = R.length;
    let bi = 0, bu = 0, bd = Infinity;
    for(let i = 0; i < n; i++){
      const a = [t.cx + R[i][0], t.cy + R[i][1]], b = [t.cx + R[(i+1)%n][0], t.cy + R[(i+1)%n][1]], e = sub(b, a), ee = dot(e, e);
      const u = ee > 0 ? Math.max(0, Math.min(1, dot(sub(p, a), e)/ee)) : 0, d = len(sub(p, [a[0] + e[0]*u, a[1] + e[1]*u]));
      if(d < bd){ bd = d; bi = i; bu = u; }
    }
    const j = (bi + 1) % n, da = [P[bi][0] - t.cx - R[bi][0], P[bi][1] - t.cy - R[bi][1]], db = [P[j][0] - t.cx - R[j][0], P[j][1] - t.cy - R[j][1]];
    const er = sub(R[j], R[bi]), ep = sub(P[j], P[bi]);
    const dAng = c.rigid || n < 24 ? Math.atan2(crs(er, ep), dot(er, ep)) : 0;
    return [da[0]*(1 - bu) + db[0]*bu, da[1]*(1 - bu) + db[1]*bu, dAng];
  }

  // A flick: when a dragged tray is let go, it keeps the speed it was moving at (px per frame), less
  // for heavier trays. A slow release barely moves it; a fast one slides it across the counter.
  function fling(t, vxFrame, vyFrame, opt){
    const o = Object.assign({}, OPT, opt), c = t.chain; if(!c) return;
    const k = 1/(o.substeps*Math.sqrt(c.mass));
    c.vx = vxFrame*k; c.vy = vyFrame*k;
  }

  // How far (px) any frame reaches into another past the gap: 0 when every frame has room. The page
  // uses this to stop a drag or a resize when there is nowhere left for the others to go.
  function overlap(trays, opt){
    const live = trays.filter(t => !t.hidden && t.chain);
    let worst = 0;
    for(let a = 0; a < live.length; a++) for(let b = 0; b < live.length; b++){
      if(a === b) continue;
      const A = live[a], Bt = live[b];
      if(!overlaps(aabb(A.chain.P, 0), aabb(Bt.chain.P, A.r + Bt.r + 1))) continue;   // nowhere near: cannot overlap
      worst = Math.max(worst, pairOverlap(A, Bt));
    }
    return worst;
  }

  // How far any frame is past what it can take (0 = within its limits). Chain: a link longer than itself (slack is
  // allowed). Rigid: a side past either end of its slider, or a corner swung past its stop (as a share of the stop).
  // A frame squeezed with nowhere left to give would have to break one of these; the page treats that as blocked.
  function strain(trays){
    let worst = 0;
    for(const t of trays){ if(t.hidden || !t.chain) continue; const c = t.chain, P = c.P, n = P.length;
      for(let i = 0; i < n; i++){ const d = Math.hypot(P[(i+1)%n][0] - P[i][0], P[(i+1)%n][1] - P[i][1]);
        worst = Math.max(worst, d/(c.L0[i]*c.hi) - 1); if(c.lo > 0) worst = Math.max(worst, c.L0[i]*c.lo/Math.max(d, 1e-6) - 1);
        if(c.rigid){   // and a corner swung past its limit (a door forced past its stop)
          const a = P[(i - 1 + n) % n], b = P[i], e = P[(i+1) % n], u = [b[0]-a[0], b[1]-a[1]], v = [e[0]-b[0], e[1]-b[1]];
          const ex = Math.abs(Math.atan2(crs(u, v), dot(u, v)) - c.theta[i]);
          worst = Math.max(worst, (ex - OPT.cornerBend)/OPT.cornerBend); } } }
    return worst;
  }
  function pressure(trays, opt){ return {overlap: overlap(trays, opt), strain: strain(trays)}; }
  function blocked(trays, opt){ return overlap(trays, opt) > 4 || strain(trays) > 0.10; }
  // Did a move make things worse? A crowded counter can rest under some pressure; what the page refuses
  // is a drag or resize that pushes frames further into each other than they already were.
  function worsened(before, after){
    // frames passing into each other, or a frame crushed past what it can take (a tray with nowhere
    // left to go), both stop the move; ordinary denting is allowed
    return (after.overlap > 4 && after.overlap > before.overlap + 0.5) || (after.strain > 0.15 && after.strain > before.strain + 0.005);
  }

  const api = {OPT, roomAt, attach, step, settle, squeeze, rescale, neighbours, dragStep, snapshot, restore, fling, overlap, strain, blocked, pressure, worsened, clipPath, anchorOffset,
               _internal: {resample, nearest, boxField, signedArea, move, closestOnSide}};
  if(typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.ForesightChain = api; root.ForesightFrames = api; }
})(typeof window !== 'undefined' ? window : globalThis);
