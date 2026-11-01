"""Foresight Chain: tray frames that behave like linked bike chain (Josie's model).

Runs foresight_chain.js under Node against real trays from foresight_shapes.js and checks the
behaviour she described: a side hit dents, a wall flattens, a corner dents sharper than a flat
side, the dent springs back when the pressure goes, the TV box is never entered, links keep their
length, the selected tray stays solid, and a tray glides like a tissue blown across a table
(a gentle flick inches it, a hard one slides it far, and it always comes to rest).
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
C.OPT.edges = EDGES;   // these tests cover the many-link chain model; rigid sides have their own file
const B = {x0:0, y0:0, x1:1600, y1:1000};
// a channel just taller than the trays, so a pushed tray cannot slip out sideways and has to take the hit
const CH = {x0:0, y0:500-200, x1:1600, y1:500+200};
function env(solid, bounds){ return {bounds:bounds || CH, obstacles:[], rigid:t => solid.includes(t), target:() => null}; }
// largest inward displacement of a chain from its rest shape (px), and where
function dentOf(t){ let m = 0; for(let i=0;i<t.chain.P.length;i++){ const p=t.chain.P[i], r=t.chain.R[i];
  const rest=[t.cx+r[0], t.cy+r[1]], toC=[t.cx-rest[0], t.cy-rest[1]], l=Math.hypot(...toC)||1;
  const inward=((p[0]-rest[0])*toC[0]+(p[1]-rest[1])*toC[1])/l; if(inward>m) m=inward; } return m; }
// sharpest hinge bend away from rest (radians)
function sharpest(t){ const P=t.chain.P, n=P.length; let m=0; for(let i=0;i<n;i++){ const a=P[(i-1+n)%n], b=P[i], c=P[(i+1)%n];
  const u=[b[0]-a[0],b[1]-a[1]], v=[c[0]-b[0],c[1]-b[1]]; const ang=Math.atan2(u[0]*v[1]-u[1]*v[0], u[0]*v[0]+u[1]*v[1]);
  m=Math.max(m, Math.abs(ang - t.chain.theta[i])); } return m; }
// how far the chain gets into the TV box (px past the allowed clearance; 0 = never)
function boxIntrusion(t){ const need=(t.rim||0)+2-t.r; let worst=0; for(const p of t.chain.P){
  const f=C._internal.boxField([p[0]-t.cx, p[1]-t.cy], t.a, t.b); worst=Math.max(worst, need-f.d); } return worst; }
function linkSpread(t){ const P=t.chain.P, n=P.length; let lo=Infinity, hi=0; for(let i=0;i<n;i++){ const d=Math.hypot(P[(i+1)%n][0]-P[i][0], P[(i+1)%n][1]-P[i][1])/t.chain.L0[i]; lo=Math.min(lo,d); hi=Math.max(hi,d); }
  return [lo, hi]; }
"""


def run(js, edges="chain"):
    out = subprocess.run(["node", "-e", PRELUDE.replace("EDGES", repr(edges)) + js, str(SHAPES), str(CHAIN)], capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_a_side_hit_dents_the_frame_and_never_reaches_the_screen():
    r = run("""
// b sits against the right wall so it cannot escape; a solid tray presses into its left side
const b = S.makeTray('b','hexagon', 1600-300, 500, 380, 240), a = S.makeTray('a','pentagon', 800, 500, 300, 200);
[a,b].forEach(t => C.attach(t, S)); const e = env([a]);
C.settle([a,b], e, 200);
let worstBox = 0, worstLink = [1,1];
// push like a person would: keep going until the frames have no more room, then stop
for(let k=0;k<400;k++){ const before = C.pressure([a,b]); a.cx += 1.5; C.step([a,b], e); if(C.worsened(before, C.pressure([a,b]))){ a.cx -= 1.5; C.step([a,b], e); break; } worstBox = Math.max(worstBox, boxIntrusion(b));
  const ls = linkSpread(b); worstLink = [Math.min(worstLink[0], ls[0]), Math.max(worstLink[1], ls[1])]; }
console.log(JSON.stringify({dent: dentOf(b), worstBox, worstLink, aSolid: dentOf(a)}));""")
    assert r["dent"] > 8, r                 # it dented
    assert r["worstBox"] <= 1.0, r          # the TV box was never entered (1px tolerance)
    assert r["worstLink"][1] < 1.12, r   # like real chain, a link never stretches (it may go slack where the frame is dented)
    assert r["aSolid"] < 1e-6, r            # the solid tray never dented


def test_a_wall_flattens_the_links_against_it():
    r = run("""
const b = S.makeTray('b','octagon', 1200, 500, 360, 260), a = S.makeTray('a','hexagon', 700, 500, 360, 260);
[a,b].forEach(t => C.attach(t, S)); const e = env([a]);
// measured while it is pressed against the wall (the moment the push runs out of room)
for(let k=0;k<600;k++){ const before = C.pressure([a,b]); a.cx += 1.5; C.step([a,b], e); if(C.worsened(before, C.pressure([a,b]))){ a.cx -= 1.5; break; } }
const wallX = 1600 - b.r, flat = b.chain.P.filter(p => Math.abs(p[0] - wallX) < 1.5).length;
console.log(JSON.stringify({flat, maxX: Math.max(...b.chain.P.map(p => p[0])), wallX}));""")
    assert r["maxX"] <= r["wallX"] + 0.5, r     # nothing past the wall
    assert r["flat"] >= 3, r                     # several links lie flat along it


def test_a_corner_dents_sharper_than_a_flat_side():
    r = run("""
// pushers with an exact leading edge: a wedge leads with its point, a block with a flat face
const FIXED = {finalize: t => t};
function pusher(id, poly){ return {id, cx: 900, cy: 500, a: 60, b: 50, r: 6, rim: 6, q: poly.map(p => [p[0] + 900, p[1] + 500])}; }
function trial(p){
  // the struck tray has a long flat face toward the pusher, so only the pusher's shape differs between trials
  const b = {id:'b', cx: 1300, cy: 500, a: 130, b: 90, r: 20, rim: 14,
             q: [[-190,-160],[150,-160],[200,0],[150,160],[-190,160]].map(p => [p[0] + 1300, p[1] + 500])};
  C.attach(b, FIXED); C.attach(p, FIXED);
  const e = env([p]); C.settle([p,b], e, 200);
  for(let k=0;k<600;k++){ const before = C.pressure([p,b]); p.cx += 1.5; C.step([p,b], e);
    if(C.worsened(before, C.pressure([p,b])) || dentOf(b) > 30){ break; } }
  const d = dentOf(b), P = b.chain.P, R = b.chain.R; let wide = 0;
  for(let i=0;i<P.length;i++){ const rest=[b.cx+R[i][0], b.cy+R[i][1]], toC=[b.cx-rest[0], b.cy-rest[1]], l=Math.hypot(...toC)||1;
    if(((P[i][0]-rest[0])*toC[0]+(P[i][1]-rest[1])*toC[1])/l > 4) wide++; }
  return {wide, dent: d, sharp: sharpest(b)};
}
const corner = trial(pusher('w', [[-120,-90],[120,0],[-120,90]]));
const flat = trial(pusher('k', [[-120,-170],[120,-170],[120,170],[-120,170]]));
console.log(JSON.stringify({corner, flat}));""")
    assert r["corner"]["dent"] > 15 and r["flat"]["dent"] > 15, r
    # at the same depth, a corner pushes in far fewer links: a narrow, steep V; a flat face a broad, shallow-walled dent.
    # (both reach the hinge limit at their sharpest hinge by design: a flat dent has two crisp shoulders, a V one point)
    assert abs(r["corner"]["dent"] - r["flat"]["dent"]) < 6, r
    assert r["corner"]["wide"]*2 <= r["flat"]["wide"], r



def test_the_dent_springs_back_when_the_pressure_goes():
    r = run("""
const b = S.makeTray('b','hexagon', 1600-300, 500, 380, 240), a = S.makeTray('a','pentagon', 800, 500, 300, 200);
[a,b].forEach(t => C.attach(t, S)); const e = env([a]); C.settle([a,b], e, 200);
const base = dentOf(b);   // the channel walls already press it a little
for(let k=0;k<400;k++){ const before = C.pressure([a,b]); a.cx += 1.5; C.step([a,b], e); if(C.worsened(before, C.pressure([a,b]))){ a.cx -= 1.5; C.step([a,b], e); break; } }
const pressed = dentOf(b);
a.cx = 300;                                   // take the pusher away
for(let k=0;k<400;k++) C.step([a,b], e);
console.log(JSON.stringify({pressed, after: dentOf(b) - base}));""")
    assert r["pressed"] > 8, r
    assert r["after"] < 1.0, r


def test_trays_glide_like_a_tissue_blown_across_a_table():
    r = run("""
function slide(v){
  const t = S.makeTray('t','heptagon', 400, 500, 300, 200); C.attach(t, S); C.fling(t, v, 0);
  const x0 = t.cx; let k = 0; for(; k < 2000; k++){ if(C.step([t], env([], B)) < 0.01 && k > 2) break; }
  return {dist: t.cx - x0, stoppedAfter: k};
}
console.log(JSON.stringify({puff: slide(2), shove: slide(30)}));""")
    assert 0 < r["puff"]["dist"] < 120, r          # a light puff inches it
    assert r["shove"]["dist"] > 500, r              # a hard one slides it far
    assert r["shove"]["stoppedAfter"] < 2000, r     # and it always comes to rest


def test_a_frame_crushed_into_a_corner_still_surrounds_its_whole_screen():
    r = run("""
// a solid tray drives another into the bottom-right corner of the counter, as hard as it will go
const b = S.makeTray('b','rhombus', 1350, 800, 240, 200), a = S.makeTray('a','octagon', 900, 500, 420, 300);
[a,b].forEach(t => C.attach(t, S)); const e = env([a], B);
function cover(t){ const fr = t.floor.r; let inside = 0, n = 0;
  for(let i=0;i<=10;i++) for(let j=0;j<=10;j++){ const p = [t.cx - t.a + 2*t.a*i/10, t.cy - t.b + 2*t.b*j/10];
    n++; if(C._internal.nearest(t.chain.P, p).d <= fr + 0.5) inside++; } return inside/n; }
const atRest = cover(b);   // rounded corners leave a little of the box's very corners uncovered even at rest (the rules allow 6%)
let worst = 1;
for(let k=0;k<500;k++){ const before = C.pressure([a,b]); a.cx += 1.2; a.cy += 0.8; C.step([a,b], e);
  if(C.worsened(before, C.pressure([a,b]))){ a.cx -= 1.2; a.cy -= 0.8; C.step([a,b], e); }
  worst = Math.min(worst, cover(b)); }
const xs = b.chain.P.map(p => p[0]), ys = b.chain.P.map(p => p[1]);
console.log(JSON.stringify({worst, atRest, spanX: Math.max(...xs) - Math.min(...xs), spanY: Math.max(...ys) - Math.min(...ys)}));""")
    assert r["atRest"] >= 0.94, r                    # the design rule at rest
    assert r["worst"] >= 0.94, r                      # crushed hard into a corner it still meets the rule (only the box's very corners can uncover)
    assert r["spanX"] > 150 and r["spanY"] > 120, r   # the frame never collapsed

