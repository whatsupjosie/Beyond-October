/* Foresight Shapes — tray silhouettes, the TV-box rule, and collision morphing.

   A tray is a rounded convex polygon: a frame. The whole inside of the frame is
   the screen — the program's content fills it edge to edge and the frame covers
   the content's edges like a bezel. Nothing rectangular is ever shown.

   The "TV box" is an invisible measure, not something on screen: the standard
   rectangle that must stay inside the frame for the tray to still work as a
   window. It decides how big the frame is and how far the frame may flex when
   trays press together. The polygon is irregular (rhombus, trapezoid, pentagon,
   hexagon, heptagon, octagon or ellipse; never a square or rectangle), its
   corners are always rounded, and its angles are kept wide.

   When trays press against each other (or against the Counter's edges) they do
   not overlap: each one is cut by a flat contact face, so its border flattens and
   new sides sprout where it touches. A tray gives way like this only until its
   TV box would start to collapse; past that point it is pushed away instead.

   Tray Design Rules carried over from the v18 shape library
   (polygon_shape_library.py): allowed families only; squares, rectangles and
   regular polygons banned; no two sides the same length; shapes kept plump.

   Works in the browser (window.ForesightShapes) and in Node (module.exports). */
(function(root){
  'use strict';

  // ---------- tunables (all in CSS pixels unless noted) ----------
  const RULES = {
    REST_COVERAGE: 0.985,    // share of the TV box inside the frame when a tray is at rest
    MIN_COVERAGE: 0.94,      // a squeezed frame flexes only this far into the TV box — very little
    CORE_FRAC: 0.90,         // the middle of the TV box (this fraction of each side) is never covered
    TITLE_BAND: 34,          // the top band of the TV box (the title bar) is protected across the core's width
    GAP: 18,                 // space left between two trays that press together (room for their walls and shadows)
    WALL_GAP: 10,            // space left between a tray and the Counter's edge
    SIDE_MATCH_TOLERANCE: 0.06,   // v18: two sides within 6% count as "the same length"
    ANGLE_UNIFORM_TOLERANCE: 4,   // v18: all angles within 4 degrees = a regular polygon
    PARALLEL_TOLERANCE: 6,        // v18: degrees; a quad with two parallel pairs is a rectangle
    MIN_ANGLE: {rhombus:70, trapezoid:65, pentagon:88, hexagon:95, heptagon:100, octagon:105, ellipse:0},
    VERTS: {rhombus:4, trapezoid:4, pentagon:5, hexagon:6, heptagon:7, octagon:8, ellipse:22},
    MAX_RHOMBUS_ASPECT: 1.35,     // a wider TV box would make a rhombus too sharp; use a hexagon instead
    MIN_SCALE: 0.55,              // a crowded tray may shrink to this share of its requested size, no further
  };
  const FAMILIES = Object.keys(RULES.VERTS);

  // ---------- small vector helpers ----------
  const dot = (a,b) => a[0]*b[0] + a[1]*b[1];
  const sub = (a,b) => [a[0]-b[0], a[1]-b[1]];
  const add = (a,b) => [a[0]+b[0], a[1]+b[1]];
  const mul = (a,s) => [a[0]*s, a[1]*s];
  const cross = (a,b) => a[0]*b[1] - a[1]*b[0];
  const len = a => Math.hypot(a[0], a[1]);
  const norm = a => { const l = len(a) || 1; return [a[0]/l, a[1]/l]; };

  // ---------- seeded random (stable per tray id) ----------
  function rng(seed){
    let h = 1779033703 ^ String(seed).length;
    for(const ch of String(seed)){ h = Math.imul(h ^ ch.charCodeAt(0), 3432918353); h = (h << 13) | (h >>> 19); }
    let s = h >>> 0;
    return () => { s += 0x6D2B79F5; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }

  // ---------- convex polygon basics (vertices as [x,y]; positive signed area) ----------
  function area(P){ let s = 0; for(let i=0;i<P.length;i++){ const a=P[i], b=P[(i+1)%P.length]; s += a[0]*b[1] - b[0]*a[1]; } return s/2; }
  function orient(P){ return area(P) < 0 ? P.slice().reverse() : P; }
  function centroid(P){
    let A = 0, cx = 0, cy = 0;
    for(let i=0;i<P.length;i++){ const a=P[i], b=P[(i+1)%P.length], c=a[0]*b[1]-b[0]*a[1]; A+=c; cx+=(a[0]+b[0])*c; cy+=(a[1]+b[1])*c; }
    if(Math.abs(A) < 1e-9){ let x=0,y=0; for(const p of P){x+=p[0];y+=p[1];} return [x/P.length, y/P.length]; }
    return [cx/(3*A), cy/(3*A)];
  }
  // Outward unit normal of edge i (from P[i] to P[i+1]).
  function edgeNormal(P, i){ const e = sub(P[(i+1)%P.length], P[i]); return norm([e[1], -e[0]]); }
  // Keep the part of P where dot(n, p) <= c.
  function clip(P, n, c){
    const out = [];
    for(let i=0;i<P.length;i++){
      const a = P[i], b = P[(i+1)%P.length];
      const da = dot(n,a) - c, db = dot(n,b) - c;
      if(da <= 0) out.push(a);
      if((da < 0 && db > 0) || (da > 0 && db < 0)){ const t = da/(da-db); out.push([a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t]); }
    }
    return dedupe(out);
  }
  function dedupe(P){
    const out = [];
    for(const p of P){ const q = out[out.length-1]; if(!q || Math.hypot(p[0]-q[0], p[1]-q[1]) > 1e-6) out.push(p); }
    if(out.length > 1){ const a = out[0], b = out[out.length-1]; if(Math.hypot(a[0]-b[0], a[1]-b[1]) <= 1e-6) out.pop(); }
    return out;
  }
  function intersect(A, B){ let R = A; for(let i=0;i<B.length && R.length>2;i++){ const n = edgeNormal(B,i); R = clip(R, n, dot(n, B[i])); } return R.length > 2 ? R : []; }
  // Shrink a convex polygon by d (every edge moves inward by d).
  function inset(P, d){ let R = P; for(let i=0;i<P.length && R.length>2;i++){ const n = edgeNormal(P,i); R = clip(R, n, dot(n,P[i]) - d); } return R.length > 2 ? R : []; }
  // Grow a convex polygon by d (every edge moves outward by d; corners stay sharp).
  function offset(P, d){
    const n = P.length, out = [];
    for(let i=0;i<n;i++){
      const n0 = edgeNormal(P,(i-1+n)%n), n1 = edgeNormal(P,i);
      const bis = norm(add(n0,n1)), c = dot(bis, n1) || 1;
      out.push(add(P[i], mul(bis, d / c)));
    }
    return out;
  }
  function support(P, n){ let m = -Infinity; for(const p of P){ const v = dot(n,p); if(v > m) m = v; } return m; }
  function translate(P, t){ return P.map(p => [p[0]+t[0], p[1]+t[1]]); }
  function scale(P, s){ return P.map(p => [p[0]*s, p[1]*s]); }
  function rect(cx, cy, hw, hh){ return [[cx-hw,cy-hh],[cx+hw,cy-hh],[cx+hw,cy+hh],[cx-hw,cy+hh]]; }
  // Signed distance to a polygon (negative inside). Ported from the renderer's sdPolygon.
  function sdPolygon(P, p){
    let d = dot(sub(p,P[0]), sub(p,P[0])), s = 1;
    for(let i=0, j=P.length-1; i<P.length; j=i, i++){
      const e = sub(P[j],P[i]), w = sub(p,P[i]);
      const t = Math.max(0, Math.min(1, dot(w,e)/dot(e,e)));
      const b = sub(w, mul(e,t)); d = Math.min(d, dot(b,b));
      const c1 = p[1] >= P[i][1], c2 = p[1] < P[j][1], c3 = e[0]*w[1] > e[1]*w[0];
      if((c1&&c2&&c3) || (!c1&&!c2&&!c3)) s = -s;
    }
    return s * Math.sqrt(d);
  }
  function sdRounded(Q, r, p){ return sdPolygon(Q, p) - r; }

  // ---------- rule checks (v18 Tray Design Rules + wide angles) ----------
  function sides(P){ return P.map((p,i) => len(sub(P[(i+1)%P.length], p))); }
  function angles(P){
    return P.map((p,i) => {
      const a = sub(P[(i-1+P.length)%P.length], p), b = sub(P[(i+1)%P.length], p);
      const c = Math.max(-1, Math.min(1, dot(a,b)/((len(a)||1e-9)*(len(b)||1e-9))));
      return Math.acos(c) * 180 / Math.PI;
    });
  }
  function isConvex(P){ let sign = 0; for(let i=0;i<P.length;i++){ const c = cross(sub(P[(i+1)%P.length],P[i]), sub(P[(i+2)%P.length],P[(i+1)%P.length])); if(Math.abs(c) < 1e-9) continue; const s = Math.sign(c); if(sign && s !== sign) return false; sign = s; } return true; }
  function parallelPairs(P){
    const b = P.map((p,i) => { const e = sub(P[(i+1)%P.length], p); return ((Math.atan2(e[1],e[0]) * 180/Math.PI) % 180 + 180) % 180; });
    let pairs = 0;
    for(let i=0;i<b.length;i++) for(let j=i+1;j<b.length;j++){ let d = Math.abs(b[i]-b[j]) % 180; d = Math.min(d, 180-d); if(d <= RULES.PARALLEL_TOLERANCE) pairs++; }
    return pairs;
  }
  // Returns null when the polygon obeys the rules, otherwise the reason it does not.
  function ruleViolation(P, family){
    if(!FAMILIES.includes(family)) return 'unknown family '+family;
    if(P.length !== RULES.VERTS[family]) return family+' needs '+RULES.VERTS[family]+' vertices';
    if(!isConvex(P)) return 'not convex';
    const ang = angles(P);
    const minA = RULES.MIN_ANGLE[family];
    if(Math.min(...ang) < minA) return 'an angle is sharper than '+minA+' degrees';
    if(family === 'ellipse') return null;
    const s = sides(P);
    for(let i=0;i<s.length;i++) for(let j=i+1;j<s.length;j++){
      if(Math.abs(s[i]-s[j]) / (Math.max(s[i],s[j]) || 1e-9) < RULES.SIDE_MATCH_TOLERANCE) return 'two sides are the same length';
    }
    if(Math.max(...ang) - Math.min(...ang) < RULES.ANGLE_UNIFORM_TOLERANCE) return 'regular polygon';
    if(P.length === 4 && parallelPairs(P) >= 2) return 'rectangle or square';
    return null;
  }

  // ---------- generating a silhouette around a TV box ----------
  // Units: the TV box has half-height 1 and half-width = aspect. The polygon is
  // generated plump around it; fitTo() later scales it to the real box.
  // Distinct values spread evenly between lo and hi, shuffled, lightly jittered.
  // Spreading them (rather than sampling) is what keeps every side a different
  // length without making the outline gaunt — the same idea as v18's radii spread.
  function spread(n, lo, hi, rand){
    const v = Array.from({length:n}, (_,i) => lo + (hi-lo) * (n === 1 ? 0.5 : i/(n-1)));
    for(let i=n-1;i>0;i--){ const j = Math.floor(rand()*(i+1)); [v[i],v[j]] = [v[j],v[i]]; }
    return v.map(x => x + (rand()-0.5) * (hi-lo) / (n*3));
  }
  function emit(family, aspect, rand){
    const A = aspect, B = 1;
    if(family === 'rhombus'){
      // A diamond whose four reaches all differ, with its tips shifted off-centre.
      const [rt, rr, rb, rl] = spread(4, 1.55, 2.05, rand);
      const [ot, or_, ob, ol] = spread(4, -0.16, 0.16, rand);
      return [[ot*A, -rt*B], [rr*A, or_*B], [ob*A, rb*B], [-rl*A, ol*B]];
    }
    if(family === 'trapezoid'){
      // Flat top and bottom (one parallel pair only), slanted, unequal sides.
      const top = 0.86 + rand()*0.12, sk = (rand()-0.5)*0.22;
      const [bl, br] = spread(2, 1.30, 1.50, rand);
      return [[-(top-sk)*A, -1.24*B], [(top+sk)*A, -1.24*B], [br*A, 1.2*B], [-bl*A, 1.2*B]];
    }
    // Radial families: vertices on a superellipse (plumper than an ellipse, so
    // angles stay wide), uneven but distinct angular steps, with one edge lying
    // across the top so the title has a straight run to sit on.
    const n = RULES.VERTS[family];
    const p = family === 'ellipse' ? 2 : 2.3 + rand()*0.6;
    const steps = family === 'ellipse' ? Array(n).fill(1) : spread(n, 0.72, 1.32, rand);
    const total = steps.reduce((x,y)=>x+y, 0);
    const start = -Math.PI/2 - (steps[0]/total)*Math.PI + (rand()-0.5)*0.10;
    const radii = family === 'ellipse' ? Array(n).fill(1) : spread(n, 0.93, 1.0, rand);
    const out = []; let t = start;
    for(let i=0;i<n;i++){
      const c = Math.cos(t), s = Math.sin(t);
      const r = Math.pow(Math.pow(Math.abs(c), p) + Math.pow(Math.abs(s), p), -1/p);
      out.push([c * r * radii[i] * A * 1.18, s * r * radii[i] * B * 1.18]);
      t += (steps[i]/total) * Math.PI * 2;
    }
    return out;
  }
  function generate(family, aspect, seed){
    if(family === 'rhombus' && aspect > RULES.MAX_RHOMBUS_ASPECT) family = 'hexagon';
    const rand = rng(seed + ':' + family);
    let fallback = null;
    for(let tries=0; tries<600; tries++){
      const P = orient(emit(family, aspect, rand));
      const why = ruleViolation(P, family);
      if(!why) return {family, unit:P};
      if(!fallback && isConvex(P)) fallback = P;
    }
    // A family that cannot meet the rules at this aspect steps up to one more side.
    const next = {rhombus:'pentagon', trapezoid:'pentagon', pentagon:'hexagon', hexagon:'heptagon', heptagon:'octagon', octagon:'ellipse'}[family];
    if(next) return generate(next, aspect, seed);
    return {family, unit: fallback};
  }

  // ---------- sizing: how big the polygon must be around a given TV box ----------
  // Corner radius. Always large enough that the floor inside the rim is rounded too
  // (the floor's own radius is r - rim - FLOOR_PAD, at least 6px).
  function cornerRadius(P){
    const xs = P.map(p=>p[0]), ys = P.map(p=>p[1]);
    const m = Math.min(Math.max(...xs)-Math.min(...xs), Math.max(...ys)-Math.min(...ys));
    return Math.max(rimWidth(P) + FLOOR_PAD + 6, Math.min(62, m * 0.15));   // rounder, softer corners (was min 40, 8.5%)
  }
  function rimWidth(P){
    const xs = P.map(p=>p[0]), ys = P.map(p=>p[1]);
    const m = Math.min(Math.max(...xs)-Math.min(...xs), Math.max(...ys)-Math.min(...ys));
    return Math.max(14, Math.min(23, m * 0.044));   // picture-frame width, a third slimmer than the 20-34 it was (originally 13-24)
  }
  const FLOOR_PAD = 2;     // the screen starts just inside the rim
  // The floor: where content may show. The tray's rounded outline is q (P inset
  // by r) grown by r; the floor is the same q grown by r - rim - FLOOR_PAD, so the
  // page's clip path and the renderer's floor are exactly the same shape.
  // Returns {poly (sharp outline, for area sums), q, r}.
  function floorOf(P, r, rim){
    return {poly: inset(P, rim + FLOOR_PAD), q: inset(P, r), r: Math.max(1, r - rim - FLOOR_PAD)};
  }
  // Fraction of the box (centred at c with half sizes a,b) inside the floor.
  function coverage(floorPoly, c, a, b){
    if(!floorPoly.length) return 0;
    const box = orient(rect(c[0], c[1], a, b));
    const I = intersect(box, floorPoly);
    return I.length ? area(I) / (4*a*b) : 0;
  }
  // The core of the TV box must lie inside the floor. Checked against the floor's
  // outline with a 2px allowance: a rounded corner may graze the core, never cut it.
  // The protected core: the middle CORE_FRAC of the box, stretched up to the box's
  // top edge so the title bar (TITLE_BAND) is never cut — only the box's corners can be trimmed.
  function corePoints(c, a, b){
    const ca = a * RULES.CORE_FRAC, cb = b * RULES.CORE_FRAC, top = -b;
    return [[c[0]-ca,c[1]+top],[c[0]+ca,c[1]+top],[c[0]+ca,c[1]+cb],[c[0]-ca,c[1]+cb]];
  }
  function coreInside(floor, c, a, b){
    if(!floor.poly.length) return false;
    for(const p of corePoints(c, a, b)){
      if(sdPolygon(floor.poly, p) > 2) return false;
    }
    return true;
  }
  // Smallest scale of the unit polygon that shows REST_COVERAGE of an a x b (half size) box.
  function fitTo(unit, a, b){
    const s0 = b;   // unit polygon has half-height 1 for the box
    const ok = k => {
      const P = scale(unit, s0*k), r = cornerRadius(P), rim = rimWidth(P), f = floorOf(P, r, rim);
      return coreInside(f, [0,0], a, b) && coverage(f.poly, [0,0], a, b) >= RULES.REST_COVERAGE;
    };
    let lo = 0.5, hi = 1;
    while(!ok(hi) && hi < 6) hi *= 1.25;
    for(let i=0;i<22;i++){ const m = (lo+hi)/2; ok(m) ? hi = m : lo = m; }
    const P = scale(unit, s0*hi);
    return {poly:P, r:cornerRadius(P), rim:rimWidth(P)};
  }

  // ---------- trays and collisions ----------
  // A tray: {id, cx, cy, a, b (TV box half sizes), family, unit, base (local poly), r, rim, pinned}
  function makeTray(id, family, cx, cy, w, h){
    const t = {id, cx, cy, a:w/2, b:h/2, family, reqW:w, reqH:h, scale:1, pressure:0};
    setBox(t, w, h);
    return t;
  }
  // Size the TV box. The tray's silhouette is made once, when it is created (or reset to a new family), and kept:
  // a later size change stretches that same silhouette to the new box rather than generating a different one.
  // (Owner decision, 2026-10-14: resizing changes the size only, not the shape; stretching is allowed, so no
  // fixed aspect ratio is imposed.) The original unit outline is kept, so stretching is exactly reversible.
  function setBox(t, w, h){
    t.a = w/2; t.b = h/2;
    const aspect = t.a/t.b;
    if(!t.unit0){
      const g = generate(t.requestedFamily || t.family, aspect, t.id);
      t.requestedFamily = t.requestedFamily || t.family;
      t.family = g.family; t.unit0 = g.unit; t.aspect0 = aspect;
    }
    // the same outline, stretched across to the box's new proportions (unit outlines have half-height 1)
    const k = aspect/t.aspect0;
    t.unit = Math.abs(k - 1) < 1e-9 ? t.unit0 : t.unit0.map(p => [p[0]*k, p[1]]);
    t.aspect = aspect;
    const f = fitTo(t.unit, t.a, t.b);
    t.base = f.poly; t.r = f.r; t.rim = f.rim;
    return t;
  }
  // Start a tray's silhouette over, from its family, at its current box (used by Reset when the family changes).
  function reshape(t, family){ t.unit0 = null; t.requestedFamily = family || t.requestedFamily || t.family; return setBox(t, t.a*2, t.b*2); }
  function worldBase(t){ return translate(t.base, [t.cx, t.cy]); }

  // How far in from its centre (along n) a tray may be cut before its TV box
  // would collapse: the core must stay visible and MIN_COVERAGE must remain.
  function limitOffset(t, n, others){
    const P0 = others || t.base;   // local coordinates
    const coreH = Math.max(...corePoints([0,0], t.a, t.b).map(p => dot(n,p))) + t.rim + FLOOR_PAD + 1;
    const sup = support(P0, n);
    if(coreH >= sup) return sup;
    const ok = h => { const P = clip(P0, n, h); if(P.length < 3) return false; return coverage(inset(P, t.rim + FLOOR_PAD), [0,0], t.a, t.b) >= RULES.MIN_COVERAGE; };
    if(!ok(sup)) return sup;
    let lo = coreH, hi = sup;
    if(ok(lo)) return lo;
    for(let i=0;i<18;i++){ const m = (lo+hi)/2; ok(m) ? hi = m : lo = m; }
    return hi;
  }

  // Contact between two convex footprints: the cut plane between them.
  // Returns null when they are apart, else {n (A->B), m (plane position), extent}.
  function contact(PA, PB, cA, cB, gap){
    const I = intersect(offset(PA, gap/2), offset(PB, gap/2));
    if(I.length < 3 || area(I) < 0.5) return null;
    const g = centroid(I);
    let sxx=0, syy=0, sxy=0;
    for(const p of I){ const d = sub(p,g); sxx+=d[0]*d[0]; syy+=d[1]*d[1]; sxy+=d[0]*d[1]; }
    // major axis of the overlap lens: the contact face runs along it
    const th = 0.5*Math.atan2(2*sxy, sxx-syy);
    const t = [Math.cos(th), Math.sin(th)];
    let nP = [-t[1], t[0]];
    const axis = norm(sub(cB, cA));
    if(dot(nP, axis) < 0) nP = mul(nP, -1);
    const l1 = (sxx+syy)/2 + Math.sqrt(((sxx-syy)/2)**2 + sxy*sxy), l2 = (sxx+syy)/2 - Math.sqrt(((sxx-syy)/2)**2 + sxy*sxy);
    const aniso = l1 > 1e-9 ? Math.max(0, Math.min(1, (l1 - l2)/(l1 + l2))) : 0;
    const n = norm(add(mul(nP, aniso), mul(axis, 1-aniso)));
    const proj = I.map(p => dot(n,p));
    return {n, m: dot(n,g), extent: Math.max(...proj) - Math.min(...proj)};
  }

  // One relaxation pass. bounds = {x0,y0,x1,y1}; obstacles = [{poly (world), id}]
  // Mutates tray positions (pushing) and sets t.cuts = [{n, c}] in world coordinates.
  function solve(trays, bounds, obstacles, iterations){
    obstacles = obstacles || [];
    const it = iterations || 6;
    let moved = 0, unresolved = 0;
    // Several passes that may push trays apart, then one last pass that only
    // measures, so every cut matches the final positions.
    for(let k=0;k<=it;k++){
      const push = k < it;
      for(const t of trays){ t.cuts = []; if(!push) t.pressure = 0; }
      const W = trays.map(worldBase);
      // tray against tray
      for(let i=0;i<trays.length;i++) for(let j=i+1;j<trays.length;j++){
        const A = trays[i], B = trays[j];
        if(A.hidden || B.hidden) continue;
        const cA = [A.cx, A.cy], cB = [B.cx, B.cy];
        // quick reject on bounding circles
        const rA = Math.max(...A.base.map(len)), rB = Math.max(...B.base.map(len));
        if(len(sub(cB,cA)) > rA + rB + RULES.GAP) continue;
        const ct = contact(W[i], W[j], cA, cB, RULES.GAP);
        if(!ct) continue;
        const stA = A.pinned ? 1 : 0, stB = B.pinned ? 1 : 0;
        const m = ct.m + (stA - stB) * 0.5 * ct.extent;
        const hA = (m - RULES.GAP/2) - dot(ct.n, cA);            // A keeps n.p <= hA (relative)
        const hB = dot(ct.n, cB) - (m + RULES.GAP/2);            // B keeps -n.p <= hB (relative)
        const minA = limitOffset(A, ct.n), minB = limitOffset(B, mul(ct.n,-1));
        const deficit = Math.max(0, minA - hA) + Math.max(0, minB - hB);
        if(!push && deficit > 1){ unresolved++; A.pressure += deficit; B.pressure += deficit; }
        if(push && deficit > 0.01){
          // Too deep to absorb: push them apart. A pinned tray (being dragged) does not move.
          const shareA = A.pinned && !B.pinned ? 0 : B.pinned && !A.pinned ? 1 : 0.5;
          if(!(A.pinned && B.pinned)){
            A.cx -= ct.n[0]*deficit*shareA; A.cy -= ct.n[1]*deficit*shareA;
            B.cx += ct.n[0]*deficit*(1-shareA); B.cy += ct.n[1]*deficit*(1-shareA);
            moved += deficit;
          }
        }
        A.cuts.push({n:ct.n, c:dot(ct.n,cA) + Math.max(hA, minA)});
        const nb = mul(ct.n,-1);
        B.cuts.push({n:nb, c:dot(nb,cB) + Math.max(hB, minB)});
      }
      // tray against obstacles (fan, lantern...) — obstacles never move
      for(const t of trays){
        if(t.hidden) continue;
        const Pw = worldBase(t), c = [t.cx, t.cy];
        for(const ob of obstacles){
          const ct = contact(ob.poly, Pw, centroid(ob.poly), c, RULES.GAP);
          if(!ct) continue;
          const nb = mul(ct.n,-1);
          const h = dot(ct.n, c) - (ct.m + ct.extent*0.5 + RULES.GAP/2);
          const minT = limitOffset(t, nb);
          if(!push && minT - h > 1){ unresolved++; t.pressure += minT - h; }
          if(push && minT - h > 0.01 && !t.pinned){ t.cx += ct.n[0]*(minT-h); t.cy += ct.n[1]*(minT-h); moved += minT-h; }
          t.cuts.push({n:nb, c:dot(nb,c) + Math.max(h, minT)});
        }
      }
      // tray against the Counter's edges
      if(bounds) for(const t of trays){
        if(t.hidden) continue;
        const walls = [[[-1,0], -bounds.x0], [[1,0], bounds.x1], [[0,-1], -bounds.y0], [[0,1], bounds.y1]];
        for(const [n, edge] of walls){
          const c = [t.cx, t.cy];
          const h = edge - RULES.WALL_GAP - dot(n, c);
          // A free tray simply slides back onto the Counter; a tray being dragged
          // flattens against the edge until its TV box would collapse.
          const minT = t.pinned ? limitOffset(t, n) : support(t.base, n);
          if(!push && minT - h > 1){ unresolved++; t.pressure += minT - h; }
          if(push && minT - h > 0.01){ t.cx -= n[0]*(minT-h); t.cy -= n[1]*(minT-h); moved += minT-h; }
          if(support(t.base, n) > h + 0.01) t.cuts.push({n, c:dot(n,[t.cx,t.cy]) + Math.max(h, t.pinned ? minT : -Infinity)});
        }
      }
    }
    let valid = unresolved === 0;
    for(const t of trays){ finalize(t); if(!t.hidden && !t.ok) valid = false; }
    // valid = no two trays overlap and every TV box still shows its core and at least MIN_COVERAGE.
    // A dragged tray should stop at its last valid position when this is false.
    return {moved, valid};
  }

  // Crowding: a tray under pressure shrinks a little (never below MIN_SCALE of the
  // size asked for); a tray with room grows back. Call once per frame after solve().
  // Returns true while some crowded tray can still shrink (the crowd is still easing).
  function breathe(trays, rate){
    rate = rate || 0.02;
    let easing = false;
    for(const t of trays){
      if(t.hidden || t.pinned) continue;
      let s = t.scale;
      t.calm = t.pressure > 0 ? 0 : (t.calm || 0) + 1;
      if(t.pressure > 1 && s > RULES.MIN_SCALE){ s = Math.max(RULES.MIN_SCALE, s*(1-rate)); easing = true; }
      // grow back only after a long spell with room, and only by a hair, so trays don't wobble
      else if(t.calm > 45 && s < 1){ s = Math.min(1, s*(1+rate*0.15)); t.calm = 30; }
      if(s !== t.scale){ t.scale = s; setBox(t, t.reqW*s, t.reqH*s); }
    }
    return easing;
  }
  // Ask for a new TV box size (the user resized the tray). The silhouette is kept and stretched (see setBox).
  function resize(t, w, h){ t.reqW = w; t.reqH = h; t.scale = 1; setBox(t, w, h); }

  // Build the tray's current outline from its base and its contact cuts.
  function finalize(t){
    let P = worldBase(t);
    for(const cut of (t.cuts || [])) P = clip(P, cut.n, cut.c);
    if(P.length < 3) P = worldBase(t);
    t.poly = P;
    t.q = inset(P, t.r);                         // rounded outline = q grown by r
    if(t.q.length < 3) t.q = inset(P, Math.max(2, t.r*0.5));
    const f = floorOf(P, t.r, t.rim);
    f.q = t.q;
    t.floor = f;
    t.coverage = coverage(f.poly, [t.cx, t.cy], t.a, t.b);
    t.ok = t.coverage >= RULES.MIN_COVERAGE - 0.005 && coreInside(f, [t.cx, t.cy], t.a, t.b);
    return t;
  }

  // ---------- helpers for the page ----------
  // SVG path of a rounded convex polygon (q grown by r), relative to origin o.
  function roundedPath(q, r, o){
    o = o || [0,0];
    const n = q.length, f = v => (Math.round(v*100)/100);
    if(n < 3) return '';
    let d = '';
    for(let i=0;i<n;i++){
      const nPrev = edgeNormal(q,(i-1+n)%n), nNext = edgeNormal(q,i);
      const a = add(q[i], mul(nPrev, r)), b = add(q[i], mul(nNext, r));
      d += (i === 0 ? 'M' : 'L') + f(a[0]-o[0]) + ' ' + f(a[1]-o[1]);
      d += 'A' + f(r) + ' ' + f(r) + ' 0 0 1 ' + f(b[0]-o[0]) + ' ' + f(b[1]-o[1]);
    }
    return d + 'Z';
  }
  // The screen: the rectangle the content element occupies. It covers the whole
  // floor of the tray's own (uncut) frame and does not change while the frame
  // flexes against neighbours, so content never reflows or distorts when trays
  // touch — the frame simply covers a little more of its edge. [x0, y0, x1, y1] world.
  function screenRect(t){
    const f = inset(t.base, t.rim + FLOOR_PAD);
    const P = f.length ? f : t.base;
    const xs = P.map(p=>p[0]), ys = P.map(p=>p[1]);
    return [t.cx + Math.min(...xs), t.cy + Math.min(...ys), t.cx + Math.max(...xs), t.cy + Math.max(...ys)];
  }
  // Clip path for the content element (the screen), in the screen's own coordinates.
  function contentClipPath(t){
    const f = t.floor; if(!f || !f.q.length) return 'none';
    const sr = screenRect(t);
    return "path('" + roundedPath(f.q, f.r, [sr[0], sr[1]]) + "')";
  }
  // Where the TV box (the safe area for text and controls) sits inside the screen.
  // [left, top, width, height] relative to the screen rectangle.
  function safeArea(t){
    const sr = screenRect(t);
    return [t.cx - t.a - sr[0], t.cy - t.b - sr[1], 2*t.a, 2*t.b];
  }
  // Where the title plaque sits: the middle of the frame's most upward-facing
  // long side, on the rim. {x, y, angle (radians), room (px along the side)}.
  function titleAnchor(t){
    const P = t.poly || worldBase(t); let best = null;
    for(let i=0;i<P.length;i++){
      const a = P[i], b = P[(i+1)%P.length], n = edgeNormal(P, i), L = len(sub(b,a));
      if(-n[1] < 0.55) continue;
      const score = -n[1] * Math.min(L, 420);
      if(!best || score > best.score) best = {score, a, b, n, L};
    }
    if(!best) return {x:t.cx, y:t.cy - t.b, angle:0, room:120};
    const m = mul(add(best.a, best.b), 0.5);
    let ang = Math.atan2(best.b[1]-best.a[1], best.b[0]-best.a[0]);
    if(ang > Math.PI/2) ang -= Math.PI; if(ang < -Math.PI/2) ang += Math.PI;
    return {x: m[0] - best.n[0]*t.rim*0.5, y: m[1] - best.n[1]*t.rim*0.5, angle: ang, room: Math.max(0, best.L - 2*t.r)};
  }
  // Horizontal run of the visible floor at height y (world) — where a title bar can sit.
  function spanAt(t, y){
    const f = t.floor; if(!f || !f.poly.length) return null;
    const P = f.poly; let lo = Infinity, hi = -Infinity;
    for(let i=0;i<P.length;i++){
      const a = P[i], b = P[(i+1)%P.length];
      if((a[1]-y)*(b[1]-y) <= 0 && a[1] !== b[1]){ const x = a[0] + (b[0]-a[0])*(y-a[1])/(b[1]-a[1]); lo = Math.min(lo,x); hi = Math.max(hi,x); }
    }
    if(lo === Infinity) return null;
    // keep clear of the rounded corners
    return [lo + f.r*0.6, hi - f.r*0.6];
  }
  function hit(t, p){ return t.q && t.q.length ? sdRounded(t.q, t.r, p) : Infinity; }

  const api = {FLOOR_PAD, RULES, FAMILIES, generate, ruleViolation, fitTo, makeTray, setBox, reshape, resize, solve, breathe, finalize, limitOffset, contact,
    contentClipPath, screenRect, safeArea, titleAnchor, roundedPath, spanAt, hit, coverage, coreInside, floorOf,
    _internal:{emit, rng},
    geom:{area, centroid, clip, intersect, inset, offset, orient, sdPolygon, sdRounded, angles, sides, isConvex, parallelPairs, support}};
  if(typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ForesightShapes = api;
})(typeof window !== 'undefined' ? window : globalThis);
