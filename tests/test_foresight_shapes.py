"""Foresight Shapes: tray silhouettes, the TV-box rule and collision morphing.

Runs foresight_shapes.js under Node and checks the rules Josie set:
rounded irregular polygons (no squares or rectangles, wide angles), a TV box
that stays mostly visible with its title strip never cut, trays that flatten
against each other with a gap instead of overlapping, and crowded trays that
shrink rather than collapse.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHAPES = ROOT / "static" / "foresight_shapes.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(js):
    script = "const S = require(process.argv[1]);\n" + js
    out = subprocess.run(["node", "-e", script, str(SHAPES)], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_every_family_obeys_the_tray_design_rules_at_every_aspect():
    r = run("""
const res = [];
for(const f of S.FAMILIES) for(const [w,h] of [[16,9],[4,3],[1,1],[9,16],[21,9]]) for(const seed of ['a','b','c']){
  const t = S.makeTray(seed+f+w+'x'+h, f, 0, 0, w*40, h*40); S.finalize(t);
  res.push({f, fam:t.family, why:S.ruleViolation(S.geom.orient(t.base), t.family), cov:t.coverage, ok:t.ok,
            min:Math.min(...S.geom.angles(t.base)), rect: t.base.length===4 && S.geom.parallelPairs(t.base) >= 2});
}
console.log(JSON.stringify(res));""")
    for row in r:
        assert row["why"] is None, row
        assert not row["rect"], row
        assert row["ok"], row
        assert row["cov"] >= 0.98, row
        assert row["min"] >= 65, row          # no sharp spikes


def test_rhombus_is_kept_for_near_square_boxes_and_never_too_sharp():
    r = run("""
const out = [];
for(let i=0;i<40;i++){ const g = S.generate('rhombus', 1.0, 'r'+i); out.push({fam:g.family, min:Math.min(...S.geom.angles(g.unit))}); }
console.log(JSON.stringify(out));""")
    assert all(x["fam"] == "rhombus" for x in r)
    assert min(x["min"] for x in r) >= 70


def test_trays_pressed_together_flatten_with_a_gap_and_sprout_sides():
    r = run("""
const bounds = {x0:0, y0:0, x1:1600, y1:1000};
const A = S.makeTray('preview','heptagon', 560, 330, 560, 315), B = S.makeTray('chat','hexagon', 1130, 300, 300, 400);
const before = A.base.length;
A.pinned = true; A.cx = 760;
let res; for(let f=0;f<20;f++){ res = S.solve([A,B], bounds, [], 4); S.breathe([A,B]); }
// smallest distance from B's rounded outline to A's rounded outline
let gap = Infinity;
for(let i=0;i<B.q.length;i++){ const p=B.q[i], q=B.q[(i+1)%B.q.length];
  for(let k=0;k<=20;k++){ const x=[p[0]+(q[0]-p[0])*k/20, p[1]+(q[1]-p[1])*k/20]; gap = Math.min(gap, S.hit(A, x) - B.r); } }
console.log(JSON.stringify({valid:res.valid, gap, verts:B.poly.length, baseVerts:B.base.length, covA:A.coverage, covB:B.coverage, okB:B.ok}));""")
    assert r["valid"]
    assert r["gap"] >= 17.0                         # RULES.GAP is 18px; never overlapping
    assert r["verts"] > r["baseVerts"] - 1          # the contact face adds a side rather than only moving one
    assert r["okB"] and r["covB"] >= 0.935          # the frame flexes only a little into the TV box


def test_title_strip_is_never_cut_by_a_contact():
    r = run("""
const t = S.makeTray('files','pentagon', 600, 600, 520, 220);
// cut straight down from above as far as the rules allow
const h = S.limitOffset(t, [0,-1]);
t.cuts = [{n:[0,-1], c: -t.cy + h}]; S.finalize(t);
const span = S.spanAt(t, t.cy - t.b + 2);
console.log(JSON.stringify({ok:t.ok, top:-h, boxTop:-t.b, span, a:t.a, cx:t.cx}));""")
    assert r["ok"]
    assert r["top"] <= r["boxTop"] + 1e-6           # the cut stays above the TV box's top edge
    assert r["span"] is not None


def test_crowded_counter_shrinks_trays_instead_of_overlapping():
    r = run("""
const bounds = {x0:0, y0:0, x1:900, y1:600};
const T = ['a','b','c','d'].map((id,i) => S.makeTray(id, ['heptagon','hexagon','pentagon','octagon'][i], 200+i*150, 300, 420, 260));
let res, e;
for(let f=0;f<400;f++){ res = S.solve(T, bounds, [], 4); e = S.breathe(T); if(res.valid && !e && res.moved < 0.05) break; }
console.log(JSON.stringify({valid:res.valid, scales:T.map(t=>t.scale), oks:T.map(t=>t.ok)}));""")
    assert r["valid"]
    assert all(r["oks"])
    assert min(r["scales"]) >= 0.55 - 1e-9
    assert min(r["scales"]) < 1.0                   # something had to give way


def test_content_clip_path_matches_the_rendered_floor():
    r = run("""
const t = S.makeTray('x','hexagon', 400, 300, 400, 260); S.finalize(t);
console.log(JSON.stringify({path:S.contentClipPath(t), floorR:t.floor.r, r:t.r, rim:t.rim, pad:S.FLOOR_PAD, same:t.floor.q === t.q}));""")
    assert r["path"].startswith("path('M")
    assert r["same"]
    assert abs(r["floorR"] - (r["r"] - r["rim"] - r["pad"])) < 1e-9
    assert r["floorR"] >= 6


def test_screen_keeps_its_size_while_the_frame_flexes():
    r = run("""
const t = S.makeTray('x','heptagon', 600, 400, 520, 292); S.finalize(t);
const before = S.screenRect(t), path0 = S.contentClipPath(t);
t.cuts = [{n:[1,0], c: t.cx + S.limitOffset(t, [1,0])}]; S.finalize(t);
const after = S.screenRect(t), path1 = S.contentClipPath(t);
console.log(JSON.stringify({before, after, changed: path0 !== path1, ok: t.ok}));""")
    assert r["before"] == r["after"]                # content never reflows or stretches when trays touch
    assert r["changed"]                             # only the frame's covering edge moves
    assert r["ok"]


def test_resizing_keeps_the_trays_own_shape_and_is_reversible():
    """Owner decision 2026-10-14: resizing changes the size only, not the shape; stretching is allowed."""
    r = run("""
const res = [];
for(const f of ['pentagon','hexagon','octagon','trapezoid','rhombus','heptagon']){
  const t = S.makeTray('keep'+f, f, 0, 0, 400, 260);
  const before = t.base.map(p => p.slice()), fam = t.family, n = t.base.length;
  S.resize(t, 700, 220);                       // much wider, a little shorter
  const wide = {n: t.base.length, fam: t.family};
  // the stretched outline is the same outline: each point maps from the original by one x and one y factor
  const kx = Math.max(...t.base.map(p=>Math.abs(p[0])))/Math.max(...before.map(p=>Math.abs(p[0])));
  const ky = Math.max(...t.base.map(p=>Math.abs(p[1])))/Math.max(...before.map(p=>Math.abs(p[1])));
  const err = Math.max(...t.base.map((p,i) => Math.hypot(p[0] - before[i][0]*kx, p[1] - before[i][1]*ky)));
  S.resize(t, 400, 260);                       // and back
  const back = Math.max(...t.base.map((p,i) => Math.hypot(p[0]-before[i][0], p[1]-before[i][1])));
  res.push({f, fam, n, wide, err, back});
}
console.log(JSON.stringify(res));""")
    for row in r:
        assert row["wide"]["n"] == row["n"] and row["wide"]["fam"] == row["fam"], row   # same family, same vertices
        assert row["err"] < 1e-6, row                                                   # same outline, stretched
        assert row["back"] < 1e-6, row                                                  # exactly reversible
