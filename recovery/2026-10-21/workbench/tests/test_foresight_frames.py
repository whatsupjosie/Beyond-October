"""Foresight Frames, rigid sides (the default edge model).

Josie's v2 tray movement handoff (2026-10-14): "each straight edge to kind of be on a slider", "like a door that
never opens, but could swing from either hinge", "never, like, bend in half". So every side of a tray is one
straight bar; the corners are hinges; a side slides in or out and swings about either corner, telescoping a
little so the outline stays closed.

Also covered here: crowded trays shrink (contents and all) and grow back, a locked tray never changes, a tray can
be dragged slowly through a full counter, and the whole counter stays fast enough to run every frame.

Runs foresight_chain.js (the frame physics) under Node against real trays from foresight_shapes.js.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHAPES = ROOT / "static" / "foresight_shapes.js"
CHAIN = ROOT / "static" / "foresight_chain.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

PRELUDE = r"""
const S = require(process.argv[1]), C = require(process.argv[2]);
if(C.OPT.edges !== 'rigid') throw new Error('rigid sides should be the default');
const B = {x0:0, y0:0, x1:1600, y1:1000};
const CH = {x0:0, y0:300, x1:1600, y1:700};   // a channel just taller than the trays, so a pushed tray has to take the hit
function env(solid, bounds, extra){ return Object.assign({bounds:bounds || CH, obstacles:[], pad: 2, rigid:t => solid.includes(t), target:() => null}, extra || {}); }   // pad: the screen's inset, as on the page
function dentOf(t){ let m = 0; for(let i=0;i<t.chain.P.length;i++){ const p=t.chain.P[i], r=t.chain.R[i];
  m = Math.max(m, Math.hypot(p[0]-t.cx-r[0], p[1]-t.cy-r[1])); } return m; }
// side lengths against their rest length: [shortest, longest]
function sideRange(t){ const P=t.chain.P, n=P.length; let lo=Infinity, hi=0; for(let i=0;i<n;i++){ const d=Math.hypot(P[(i+1)%n][0]-P[i][0], P[(i+1)%n][1]-P[i][1])/t.chain.L0[i]; lo=Math.min(lo,d); hi=Math.max(hi,d); } return [lo, hi]; }
// how much further into the TV box any part of the frame reaches than it does at rest (px; 0 = never further)
function intrusion(t){ const I = C._internal, c = t.chain, P = c.P, n = P.length, need = (t.rim||0) + 2 - t.r + C.OPT.boxMargin; let worst = 0;
  for(let i=0;i<n;i++){ const a=P[i], b=P[(i+1)%n], u = I.closestOnSide(a, b, t.cx, t.cy, t.a, t.b);
    const q = [a[0]+(b[0]-a[0])*u - t.cx, a[1]+(b[1]-a[1])*u - t.cy], d = I.boxField(q, t.a, t.b).d;
    worst = Math.max(worst, Math.min(need, c.restS[i]) - d); } return worst; }
// the sharpest any corner has swung from its own angle (radians)
function swing(t){ const P=t.chain.P, n=P.length; let m=0; for(let i=0;i<n;i++){ const a=P[(i-1+n)%n], b=P[i], c=P[(i+1)%n];
  const u=[b[0]-a[0],b[1]-a[1]], v=[c[0]-b[0],c[1]-b[1]]; m=Math.max(m, Math.abs(Math.atan2(u[0]*v[1]-u[1]*v[0], u[0]*v[0]+u[1]*v[1]) - t.chain.theta[i])); } return m; }
function pushUntilBlocked(a, others, e, dx, dy, n){ const all = [a].concat(others);
  for(let k=0;k<(n||400);k++){ const before = C.pressure(all); a.cx += dx; a.cy += dy; C.step(all, e);
    if(C.worsened(before, C.pressure(all))){ a.cx -= dx; a.cy -= dy; C.step(all, e); return k; } } return n||400; }
"""


def run(js):
    out = subprocess.run(["node", "-e", PRELUDE + js, str(SHAPES), str(CHAIN)], capture_output=True, text=True, timeout=240)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_a_side_hit_moves_whole_straight_sides_and_never_reaches_the_screen():
    r = run("""
const b = S.makeTray('b','hexagon', 1600-300, 500, 380, 240), a = S.makeTray('a','pentagon', 800, 500, 300, 200);
[a,b].forEach(t => C.attach(t, S)); const e = env([a]); C.settle([a,b], e, 200);
const corners = b.chain.R.length; let worstIn = 0, lo = 1, hi = 1, sw = 0, cornersSeen = new Set();
for(let k=0;k<400;k++){ const before = C.pressure([a,b]); a.cx += 1.5; C.step([a,b], e);
  if(C.worsened(before, C.pressure([a,b]))){ a.cx -= 1.5; C.step([a,b], e); break; }
  worstIn = Math.max(worstIn, intrusion(b)); const sr = sideRange(b); lo = Math.min(lo, sr[0]); hi = Math.max(hi, sr[1]); sw = Math.max(sw, swing(b)); cornersSeen.add(b.q.length); }
console.log(JSON.stringify({dent: dentOf(b), corners, published: [...cornersSeen], worstIn, lo, hi, sw, aSolid: dentOf(a)}));""")
    assert r["dent"] > 8, r                                   # it gave way
    assert r["published"] == [r["corners"]], r                # the outline always has exactly the tray's own corners: no side ever bends in half
    assert r["worstIn"] <= 1.0, r                             # never reaches further into the TV box than at rest (1px tolerance)
    # sides only slide within their travel (0.62-1.18); the screen guard has the last word over the slider, so
    # a side pressed hard across the screen's corner may run a few percent past its travel rather than cover it
    assert r["lo"] >= 0.62 - 0.03 and r["hi"] <= 1.18 + 0.06, r
    assert r["sw"] <= 0.55 + 0.08, r                          # corners only swing within their limit
    assert r["aSolid"] < 1e-6, r                              # the solid tray never dented


def test_a_side_hit_near_one_end_swings_like_a_door_and_in_the_middle_slides():
    r = run("""
const FIXED = {finalize: t => t};
// the struck tray has a long flat left side from (-190,-160) to (-190,160), the side under test
function struck(){ return {id:'b', cx: 1300, cy: 500, a: 130, b: 90, r: 20, rim: 14,
  q: [[-190,-160],[150,-160],[200,0],[150,160],[-190,160]].map(p => [p[0] + 1300, p[1] + 500])}; }
function trial(y){
  const b = struck(), w = {id:'w', cx: 900, cy: 500 + y, a: 60, b: 50, r: 6, rim: 6, q: [[-120,-90],[120,0],[-120,90]].map(p => [p[0] + 900, p[1] + 500 + y])};
  C.attach(b, FIXED); C.attach(w, FIXED);
  const e = env([w]); C.settle([w,b], e, 50);
  // the two corners of the side under test (the leftmost two)
  const idx = b.chain.R.map((r,i) => [r[0], i]).sort((p,q) => p[0]-q[0]).slice(0,2).map(p => p[1]);
  const top = b.chain.R[idx[0]][1] < b.chain.R[idx[1]][1] ? idx[0] : idx[1], bot = top === idx[0] ? idx[1] : idx[0];
  const inward = i => b.chain.P[i][0] - b.cx - b.chain.R[i][0];
  for(let k=0;k<600;k++){ const before = C.pressure([w,b]); w.cx += 1.5; C.step([w,b], e);
    if(C.worsened(before, C.pressure([w,b])) || Math.max(inward(top), inward(bot)) > 26) break; }
  const straight = b.q.length === 5;
  return {top: inward(top), bot: inward(bot), straight};
}
console.log(JSON.stringify({nearTop: trial(-115), middle: trial(0)}));""")
    t, m = r["nearTop"], r["middle"]
    assert t["straight"] and m["straight"], r
    assert t["top"] > 12, r                                   # hit near its top end, the side gives way there...
    assert t["top"] >= 2.0 * max(t["bot"], 1.0), r            # ...and swings about its far hinge, like a door
    assert m["top"] > 8 and m["bot"] > 8, r                   # hit in the middle, the whole side slides in
    assert 0.6 <= m["top"] / m["bot"] <= 1.6, r


def test_a_wall_lays_a_whole_side_flat_against_it():
    r = run("""
const b = S.makeTray('b','octagon', 1200, 500, 360, 260), a = S.makeTray('a','hexagon', 700, 500, 360, 260);
[a,b].forEach(t => C.attach(t, S)); const e = env([a]);
pushUntilBlocked(a, [b], e, 1.5, 0, 600);
const wallX = 1600 - b.r, P = b.chain.P, n = P.length; let flatSide = false;
for(let i=0;i<n;i++){ if(Math.abs(P[i][0]-wallX) < 1.5 && Math.abs(P[(i+1)%n][0]-wallX) < 1.5) flatSide = true; }
console.log(JSON.stringify({flatSide, maxX: Math.max(...P.map(p => p[0])), wallX, corners: b.q.length, own: b.chain.R.length}));""")
    assert r["maxX"] <= r["wallX"] + 0.5, r       # nothing past the wall
    assert r["flatSide"], r                        # a whole side lies flush along it
    assert r["corners"] == r["own"], r


def test_a_dented_frame_springs_back_when_the_pressure_goes():
    r = run("""
const b = S.makeTray('b','hexagon', 1600-300, 500, 380, 240), a = S.makeTray('a','pentagon', 800, 500, 300, 200);
[a,b].forEach(t => C.attach(t, S)); const e = env([a]); C.settle([a,b], e, 200);
const base = dentOf(b);
pushUntilBlocked(a, [b], e, 1.5, 0, 400);
const pressed = dentOf(b);
a.cx = 300; for(let k=0;k<500;k++) C.step([a,b], e);
console.log(JSON.stringify({pressed, after: dentOf(b) - base}));""")
    assert r["pressed"] > 8, r
    assert r["after"] < 1.0, r


def test_a_frame_crushed_into_a_corner_still_surrounds_its_screen():
    r = run("""
const b = S.makeTray('b','rhombus', 1350, 800, 240, 200), a = S.makeTray('a','octagon', 900, 500, 420, 300);
[a,b].forEach(t => C.attach(t, S)); const e = env([a], B);
function cover(t){ const fr = t.floor.r; let inside = 0, n = 0;
  for(let i=0;i<=10;i++) for(let j=0;j<=10;j++){ const p = [t.cx - t.a + 2*t.a*i/10, t.cy - t.b + 2*t.b*j/10];
    n++; if(C._internal.nearest(t.chain.P, p).d <= fr + 0.5) inside++; } return inside/n; }
const atRest = cover(b); let worst = 1;
for(let k=0;k<500;k++){ const before = C.pressure([a,b]); a.cx += 1.2; a.cy += 0.8; C.step([a,b], e);
  if(C.worsened(before, C.pressure([a,b]))){ a.cx -= 1.2; a.cy -= 0.8; C.step([a,b], e); }
  worst = Math.min(worst, cover(b)); }
const xs = b.chain.P.map(p => p[0]), ys = b.chain.P.map(p => p[1]);
console.log(JSON.stringify({worst, atRest, spanX: Math.max(...xs) - Math.min(...xs), spanY: Math.max(...ys) - Math.min(...ys)}));""")
    assert r["atRest"] >= 0.94, r
    assert r["worst"] >= 0.94, r
    assert r["spanX"] > 150 and r["spanY"] > 120, r


def test_a_crushed_tray_shrinks_to_its_floor_and_grows_back_with_room():
    r = run("""
// b is held against the right wall in the channel while a solid tray keeps leaning on it
const b = S.makeTray('b','hexagon', 1600-300, 500, 380, 240), a = S.makeTray('a','pentagon', 800, 500, 300, 200);
[a,b].forEach(t => C.attach(t, S));
const e = env([a], CH, {minScale: t => t === b ? 0.8 : 0.7});
C.settle([a,b], e, 100);
let minS = 1;
for(let k=0;k<500;k++){ const before = C.pressure([a,b]); a.cx += 1.5; C.step([a,b], e);
  if(C.worsened(before, C.pressure([a,b]))){ a.cx -= 1.5; C.step([a,b], e); }
  C.squeeze([a,b], e, S); minS = Math.min(minS, b.scale); }
const squeezed = b.scale, boxW = b.a*2;
a.cx = 200; let k = 0; for(; k<3000 && b.scale < 1; k++){ C.step([a,b], e); C.squeeze([a,b], e, S); }
console.log(JSON.stringify({squeezed, minS, boxW, after: b.scale, frames: k, reqW: b.reqW, corners: b.q.length, own: b.chain.R.length}));""")
    assert r["squeezed"] < 0.95, r                 # it gave way by shrinking
    assert r["minS"] >= 0.8 - 1e-9, r              # never below the floor its contents set
    assert abs(r["boxW"] - r["reqW"] * r["squeezed"]) < 1.0, r   # the TV box (and so the contents) shrank with it
    assert r["after"] == 1, r                      # with room again it grew back to its set size
    assert r["corners"] == r["own"], r


def test_a_locked_tray_never_moves_dents_or_shrinks():
    r = run("""
const b = S.makeTray('b','hexagon', 1100, 500, 380, 240), a = S.makeTray('a','pentagon', 600, 500, 300, 200);
[a,b].forEach(t => C.attach(t, S));
// b is locked: solid and still. a is pushed into it hard.
const e = env([b], CH, {locked: t => t === b}); const at = [b.cx, b.cy], q0 = b.q.map(p => p.slice());
for(let k=0;k<400;k++){ a.cx += 2; C.step([a,b], e); C.squeeze([a,b], e, S); }
let moved = 0; b.q.forEach((p,i) => { moved = Math.max(moved, Math.hypot(p[0]-q0[i][0], p[1]-q0[i][1])); });
console.log(JSON.stringify({dx: b.cx - at[0], dy: b.cy - at[1], moved, scale: b.scale, aDent: dentOf(a)}));""")
    assert r["dx"] == 0 and r["dy"] == 0, r
    assert r["moved"] < 1e-9, r
    assert r["scale"] == 1, r
    assert r["aDent"] > 8, r                       # the other tray took the whole hit


def test_a_tray_can_be_dragged_slowly_through_a_full_counter():
    r = run("""
// a full counter: two rows of trays nearly wall to wall top and bottom, with one more tray dragged from the far
// left to the far right straight between them. There is not room for it: the others have to move, give and shrink.
const W = {x0:0, y0:0, x1:1600, y1:900};
const fam = ['hexagon','pentagon','octagon','heptagon','trapezoid','ellipse'];
const crowd = []; let id = 0;
for(const y of [210, 690]) for(const x of [320, 800, 1280]){ const t = S.makeTray('c'+(id++), fam[id % fam.length], x, y, 340, 230); crowd.push(t); }
const d = S.makeTray('d','rhombus', 130, 450, 220, 180);
const all = crowd.concat([d]); all.forEach(t => C.attach(t, S));
const goal = W.x1 - Math.max(...d.chain.R.map(r => Math.abs(r[0]))) - d.r - 4;   // as far right as it can go (held, its whole frame stays on the counter)
const hand = {t: d, want: [d.cx, d.cy], at: [d.cx, d.cy]};
const e = env([d], W, {target: t => t === d ? hand.at : null, minScale: () => 0.7});
for(let k=0;k<400;k++){ C.step(all, e); C.squeeze(all, e, S); }   // let the full counter find its own rest first
const start = C.overlap(all);
hand.want = [goal, 450];
let blockedFrames = 0, worstIn = 0, outside = 0, worstOv = 0, minScale = 1, k = 0;
for(; k < 2400; k++){
  const r = C.dragStep(all, e, hand); C.squeeze(all, e, S);
  if(r.blocked) blockedFrames++;
  worstOv = Math.max(worstOv, C.overlap(all)); minScale = Math.min(minScale, ...crowd.map(t => t.scale));
  for(const t of all){ worstIn = Math.max(worstIn, intrusion(t)); for(const p of t.chain.P) if(p[0] < W.x0 + t.r - 0.5 || p[0] > W.x1 - t.r + 0.5 || p[1] < W.y0 + t.r - 0.5 || p[1] > W.y1 - t.r + 0.5) outside++; }
  if(Math.abs(goal - d.cx) < 2) break;
}
console.log(JSON.stringify({reached: d.cx, goal, frames: k, blockedFrames, worstIn, outside, start, worstOv, minScale,
  scales: crowd.map(t => +t.scale.toFixed(3))}));""")
    assert r["reached"] > r["goal"] - 3, r         # it got all the way through
    assert r["minScale"] < 0.95, r                 # the crowd really had to give way by shrinking (it was full)
    assert r["minScale"] >= 0.7 - 1e-9, r          # but nobody shrank past the floor
    assert r["worstIn"] <= 1.0, r                  # no frame ever reached into a screen
    assert r["outside"] == 0, r                    # every frame stayed inside the four walls
    assert r["worstOv"] <= max(r["start"], 4.0) + 0.6, r   # frames never pushed further into each other than the full counter already rested


def test_a_crowded_counter_runs_well_inside_a_frame():
    r = run("""
const W = {x0:0, y0:0, x1:1600, y1:900};
const fam = ['hexagon','pentagon','octagon','heptagon','trapezoid','ellipse'];
const all = []; let id = 0;
for(const y of [230, 650]) for(const x of [330, 800, 1270]){ const t = S.makeTray('c'+(id++), fam[id % fam.length], x, y, 320, 210); all.push(t); }
all.forEach(t => C.attach(t, S));
const d = all[1], hand = {t: d, want: [800, 650], at: [d.cx, d.cy]};
const e = env([d], W, {target: t => t === d ? hand.at : null});
for(let k=0;k<30;k++) C.dragStep(all, e, hand);   // warm up
const t0 = process.hrtime.bigint(); const N = 120;
for(let k=0;k<N;k++){ hand.want = [800 + 120*Math.sin(k/9), 440 + 140*Math.cos(k/11)]; C.dragStep(all, e, hand); C.squeeze(all, e, S); }
const ms = Number(process.hrtime.bigint() - t0)/1e6/N;
console.log(JSON.stringify({ms}));""")
    assert r["ms"] < 8.0, r                        # a 60 fps frame is 16.7 ms; physics must leave most of it for drawing


def test_an_overfull_counter_holds_a_drag_back_without_frames_passing_into_each_other():
    r = run("""
// the lab's starting counter (about four fifths covered, with the fan in the corner): a long drag across it may
// not get all the way, but nothing may break on the way: no frame into another, none past a wall, no screen covered
const W = {x0:0, y0:70, x1:1600, y1:1000};
const specs = [['preview','heptagon',640,300,600,338],['chat','hexagon',200,600,290,360],['files','trapezoid',690,735,560,190],
  ['output','pentagon',1240,360,290,280],['tools','rhombus',1240,760,240,210],['status','octagon',1230,120,290,150]];
const all = specs.map(([id,f,x,y,w,h]) => S.makeTray(id,f,x,y,w,h)); all.forEach(t => C.attach(t, S));
const fan = [[20,60],[110,50],[262,120],[270,150],[190,300],[120,330],[60,330],[30,200]];
const d = all[1], hand = {t: d, want: [d.cx, d.cy], at: [d.cx, d.cy]};
const e = env([d], W, {obstacles: [fan], target: t => t === d ? hand.at : null, minScale: t => t.id === 'preview' ? 0.5 : 0.6});
for(let k=0;k<300;k++){ C.step(all, e); C.squeeze(all, e, S); }
const start = C.overlap(all); hand.want = [1400, 600];
let worstOv = 0, worstIn = 0, outside = 0;
for(let k=0;k<400;k++){ C.dragStep(all, e, hand); C.squeeze(all, e, S);
  worstOv = Math.max(worstOv, C.overlap(all));
  for(const t of all){ worstIn = Math.max(worstIn, intrusion(t)); for(const p of t.chain.P) if(p[0] < W.x0 + t.r - 0.5 || p[0] > W.x1 - t.r + 0.5 || p[1] < W.y0 + t.r - 0.5 || p[1] > W.y1 - t.r + 0.5) outside++; } }
console.log(JSON.stringify({start, worstOv, worstIn, outside, progress: d.cx - 200, scales: all.map(t => +t.scale.toFixed(2))}));""")
    assert r["worstOv"] <= max(r["start"], 4.0) + 0.6, r     # frames never pass into each other
    assert r["worstIn"] <= 1.0, r
    assert r["outside"] == 0, r
    assert r["progress"] > 300, r                             # and it still gets a good way across


# ---- fixed things: the fan, the lantern and locked trays are as solid as the walls -------------------------------
LAB = r"""
// the lab's counter: six trays, the fan and lantern in the upper left as one fixed obstacle
const W = {x0:0, y0:70, x1:1600, y1:1000};
const specs = [['preview','heptagon',640,300,600,338],['chat','hexagon',200,600,290,360],['files','trapezoid',690,735,560,190],
  ['output','pentagon',1240,360,290,280],['tools','rhombus',1240,760,240,210],['status','octagon',1230,120,290,150]];
const all = specs.map(([id,f,x,y,w,h]) => S.makeTray(id,f,x,y,w,h)); all.forEach(t => C.attach(t, S));
// the fan exactly as the counter makes it (7 blades: New and one per tray) with the lantern, as one hull
function hull(pts){ pts = pts.slice().sort((a,b)=>a[0]-b[0]||a[1]-b[1]); const cr=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]); const lo=[],up=[];
  for(const p of pts){ while(lo.length>=2&&cr(lo[lo.length-2],lo[lo.length-1],p)<=0) lo.pop(); lo.push(p);} for(const p of pts.slice().reverse()){ while(up.length>=2&&cr(up[up.length-2],up[up.length-1],p)<=0) up.pop(); up.push(p);} return lo.slice(0,-1).concat(up.slice(0,-1)); }
const circ = (c,r,n) => Array.from({length:n}, (_,i) => [c[0]+Math.cos(i/n*Math.PI*2)*r, c[1]+Math.sin(i/n*Math.PI*2)*r]);
const PV = [62,112], fanPts = [];
for(let i=0;i<7;i++){ const a=(2+i*14.5)*Math.PI/180, d=[Math.cos(a),Math.sin(a)]; fanPts.push(...circ([PV[0]+d[0]*34,PV[1]+d[1]*34],9,18), ...circ([PV[0]+d[0]*190,PV[1]+d[1]*190],25,30)); }
fanPts.push([PV[0]-30,PV[1]+40],[PV[0]+30,PV[1]+40]); for(let i=0;i<=16;i++){ const a=Math.PI+i/16*Math.PI; fanPts.push([PV[0]+Math.cos(a)*30,PV[1]-6+Math.sin(a)*38]); }
const fan = hull(fanPts);
const I = C._internal;
function intoFan(){ let w = 0; for(const t of all) for(const p of t.chain.P) w = Math.max(w, t.r - I.nearest(fan, p).d); return w; }
function settleAll(e){ for(let k=0;k<300;k++){ C.step(all, e); C.squeeze(all, e, S); } }
"""


def test_a_flicked_tray_stops_at_the_fan_and_at_a_locked_tray_and_never_glides_through_anything():
    r = run(LAB + """
const out = {};
for(const [id, lock, vx, vy] of [['preview', null, -40, -20], ['output', 'chat', -45, 10], ['tools', null, -40, -40]]){
  const fresh = specs.map(([i,f,x,y,w,h]) => S.makeTray(i,f,x,y,w,h)); fresh.forEach(t => C.attach(t, S));
  all.length = 0; all.push(...fresh);
  const sel = all.find(t => t.id === id); if(lock) all.find(t => t.id === lock).locked = true;
  const e = env([], W, {obstacles: [fan], rigid: t => t.locked || t === sel, coast: t => !t.locked, locked: t => !!t.locked, minScale: () => 0.6});
  settleAll(e); const start = C.overlap(all);
  C.fling(sel, vx, vy);
  let worstOv = 0, worstFan = 0;
  for(let k=0;k<200;k++){ C.step(all, e); C.squeeze(all, e, S); worstOv = Math.max(worstOv, C.overlap(all));
    for(const p of sel.chain.P) worstFan = Math.max(worstFan, sel.r - I.nearest(fan, p).d); }
  out[id] = {start, worstOv, worstFan, moved: Math.hypot(sel.cx - specs.find(s => s[0] === id)[2], sel.cy - specs.find(s => s[0] === id)[3])};
}
console.log(JSON.stringify(out));""")
    for k, v in r.items():
        assert v["worstOv"] <= max(v["start"], 4.0) + 0.6, (k, v)   # it never glides through another tray, locked or not
        assert v["worstFan"] <= 0.5, (k, v)                           # nor over the fan
        assert v["moved"] > 40, (k, v)                                # but it does glide


def test_a_dragged_tray_slides_along_the_fan_and_never_goes_onto_it():
    r = run(LAB + """
const d = all.find(t => t.id === 'tools'), hand = {t: d, want: [d.cx, d.cy], at: [d.cx, d.cy]};
const e = env([d], W, {obstacles: [fan], target: t => t === d ? hand.at : null, minScale: t => t.id === 'preview' ? 0.5 : 0.6});
settleAll(e);
hand.want = [120, 160];   // straight at the fan
let worstFan = 0, worstOv = 0; const start = C.overlap(all);
for(let k=0;k<600;k++){ C.dragStep(all, e, hand); C.squeeze(all, e, S); worstFan = Math.max(worstFan, intoFan()); worstOv = Math.max(worstOv, C.overlap(all)); }
console.log(JSON.stringify({worstFan, worstOv, start, at: [d.cx, d.cy], dist: Math.hypot(d.cx - 120, d.cy - 160)}));""")
    assert r["worstFan"] <= 0.5, r                           # no frame on the fan, the dragged one or any it pushed
    assert r["worstOv"] <= max(r["start"], 4.0) + 0.6, r
    assert r["dist"] < 420, r                                # it got right up against the fan (the fan's own size keeps it off)


def test_a_drag_across_the_lab_counter_gets_there_and_held_up_frames_stay_cheap():
    r = run(LAB + """
const d = all.find(t => t.id === 'output'), hand = {t: d, want: [d.cx, d.cy], at: [d.cx, d.cy]};
const e = env([d], W, {obstacles: [fan], target: t => t === d ? hand.at : null, minScale: t => t.id === 'preview' ? 0.5 : 0.7});
settleAll(e);
// from the right-hand side, across the middle, to the far side of the crowd: between the Live Preview above, the
// Conversation to the left and the Project Files below, all of which must give way
const start = C.overlap(all), G = [600, 600]; hand.want = G;
let worstOv = 0, worstFan = 0, k = 0, t0 = null, timed = 0;
for(; k < 900; k++){ if(k === 5) t0 = process.hrtime.bigint();
  C.dragStep(all, e, hand); C.squeeze(all, e, S); worstOv = Math.max(worstOv, C.overlap(all)); worstFan = Math.max(worstFan, intoFan());
  if(Math.hypot(d.cx - G[0], d.cy - G[1]) < 2) break; }
const ms = t0 ? Number(process.hrtime.bigint() - t0)/1e6/Math.max(1, k - 5) : 0;
console.log(JSON.stringify({left: Math.hypot(d.cx - G[0], d.cy - G[1]), frames: k, ms, worstOv, worstFan, start, scales: all.map(t => +(t.scale||1).toFixed(2))}));""")
    assert r["left"] < 3, r                                   # right across the counter, through the crowd
    assert r["worstOv"] <= max(r["start"], 4.0) + 0.6, r
    assert r["worstFan"] <= 0.5, r
    assert r["ms"] < 16.0, r                                  # a frame's worth of physics, even while held up
