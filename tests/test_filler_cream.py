"""Focused tests for modules/filler_cream.py on the 1/64 proof fixtures."""
from __future__ import annotations

import copy
import json
import math
import time

import numpy as np
import pytest

from modules.filler_cream import (
    FIDELITY_STOPS, FINE_SUBDIVISION, FINE_UNIT_MM, FillerCreamError, FillerCreamLayers, FillerLayer,
    FillerSelection, SurfacePiece, bake_with_filler, compute_filler, fidelity_span_fine, parse_glb,
    pieces_from_voxel_object, pieces_from_voxel_set,
)
from modules.filler_cream_fixture import (
    CRACK_X, OPENING_X, RECESS_X, STRIP_ONE, build_fixture_object, curve_pieces, finger_pieces,
    fixture_annotations, true_curve,
)
from modules.filler_cream_fixture import S  # fixture tables are in 1/64 units; S converts to internal units
from modules.voxel_set_contract import PUB_BLOCK_METERS
from modules.voxel_studio import VoxelBaker, VoxelPrimitive, VoxelShape


def _all(pieces, **kw):
    return compute_filler(pieces, FillerSelection(frozenset(p.piece_id for p in pieces), **kw))


def _run(obj=None, annotations=None, **sel_kw):
    obj = obj or build_fixture_object()
    pieces, _ = pieces_from_voxel_object(obj, fixture_annotations() if annotations is None else annotations)
    return pieces, _all(pieces, **sel_kw)


def _strip(layer, z_lo, z_hi):
    """Cells whose z position (internal fine units) is in [z_lo, z_hi)."""
    return [c for c in layer.cells if z_lo <= c.column[1] * layer.grid_unit < z_hi]


def _x(cell, layer):
    """A cell's x position in internal fine units (column x grid unit)."""
    return cell.column[0] * layer.grid_unit


def _tops(pieces):
    return {p.piece_id: p.origin[1] + p.size[1] for p in pieces}


# ── units ──────────────────────────────────────────────────────────────────

def test_units_come_from_the_existing_block():
    assert FINE_SUBDIVISION == 128 and S == 2
    assert FINE_UNIT_MM == pytest.approx(PUB_BLOCK_METERS * 1000 / 128) == pytest.approx(1.984375)
    # fidelity stops keep their real size: very_high = 3/64 block, high = 1/8 block
    assert fidelity_span_fine("very_high") == 6 and fidelity_span_fine("high") == 16
    assert fidelity_span_fine("very_low") == 128 and fidelity_span_fine(31.75) == pytest.approx(16)
    assert list(FIDELITY_STOPS) == ["very_high", "high", "medium", "low", "very_low"]
    with pytest.raises(FillerCreamError):
        fidelity_span_fine("ultra")
    for _, x, y, z, s in STRIP_ONE:
        assert all(isinstance(v, int) for v in (x, y, z, s))


# ── core behaviour ─────────────────────────────────────────────────────────

def test_steps_are_smoothed_and_never_exceed_nearby_blocks():
    pieces, layer = _run()
    tops = _tops(pieces)
    assert {_x(c, layer) for c in _strip(layer, 0, 8 * S) if _x(c, layer) < 8 * S}, "P0 step gets cream"
    for c in layer.cells:
        assert c.top > c.base
        assert c.top <= max(tops[s] for s in c.sources) + 1e-9
    row = [c.top for c in sorted(_strip(layer, 3 * S, 4 * S), key=lambda c: c.column) if _x(c, layer) < 16 * S]
    assert row == sorted(row), "cream rises evenly up the staircase, no lip at the open end"


def test_unmarked_protrusion_blends_at_its_base_but_keeps_its_top():
    pieces, layer = _run()
    xs = {_x(c, layer) for c in _strip(layer, 0, 8 * S)}
    assert any(24 * S <= x < 32 * S for x in xs), "approach to the protrusion is blended"
    assert not any(32 * S <= x < 40 * S for x in xs), "protrusion top untouched"
    approach = [c.top for c in sorted(_strip(layer, 3 * S, 4 * S), key=lambda c: c.column) if 20 * S <= _x(c, layer) < 32 * S]
    assert approach == sorted(approach) and max(b - a for a, b in zip(approach, approach[1:])) < 3.0 * S, \
        "the blend up to the protrusion is a continuous ramp, not a cliff"
    _, marked = _run(annotations={"RECESS": {"tags": ["recess"]}, "PROT": {"tags": ["protrusion"]}})
    assert not any("PROT" in c.sources for c in marked.cells), "a marked protrusion is left exactly as built"


def test_marked_recess_and_opening_stay_intact():
    _, layer = _run()
    xs = {_x(c, layer) for c in _strip(layer, 0, 8 * S)}
    assert not any(RECESS_X[0] <= x < RECESS_X[1] for x in xs)
    assert not any(OPENING_X[0] <= x < OPENING_X[1] for x in xs)
    _, unmarked = _run(annotations={})
    assert any(RECESS_X[0] <= x < RECESS_X[1] for x in {_x(c, unmarked) for c in unmarked.cells}), \
        "without the mark the recess would be filled: the blueprint mark is what protects it"


def test_fingertip_skin_nail_and_nail_edge_stay_distinct():
    marked = _all(finger_pieces(marked=True), fidelity="high")
    for c in marked.cells:
        surfaces = {("nail" if s.startswith("N") else "skin") for s in c.sources}
        assert len(surfaces) == 1, f"cream crossed skin/nail at {c.column}"
    assert not any(_x(c, marked) >= 56 * S and {"N2"} & set(c.sources) for c in marked.cells)
    unmarked = _all(finger_pieces(marked=False), fidelity="high")
    assert any({"S3", "N0"} <= set(c.sources) for c in unmarked.cells), \
        "unmarked, the skin-to-nail drop would be smoothed away"


def test_short_best_fits_follow_a_curve():
    """Measured in the 1/64 units the curve was designed in, sampled at the
    centre of each 1/64 step, so the thresholds keep their real meaning."""
    pieces = curve_pieces()
    layer = _all(pieces, fidelity="high")
    g = layer.grid_unit
    cream = {c.column[0]: c.top for c in layer.cells if c.column[1] == 0}
    block_top = {}
    for p in pieces:
        for x in range(p.origin[0], p.origin[0] + p.size[0]):
            block_top[x] = p.origin[1] + p.size[1]
    xs = [k * S + S // 2 for k in range(96)]                     # centre of each 1/64 step
    raw = [block_top[x] / S for x in xs]
    surf = [max(block_top[x], cream.get(x // g, block_top[x])) / S for x in xs]
    truth = [true_curve(x) / S for x in xs]                         # xs are already step centres
    before = sum(abs(a - b) for a, b in zip(truth, raw))
    after = sum(abs(a - b) for a, b in zip(truth, surf))
    # Re-measured 2026-11-08 at the 1/128 internal unit: error 48.8 -> 25.5,
    # largest step 0.55, overshoot 0.11 (1/64 units), identical to 2026-11-06.
    assert after < 0.6 * before, (before, after)
    assert max(abs(surf[k + 1] - surf[k]) for k in range(95)) < 0.7
    assert max(s - tr for s, tr in zip(surf, truth)) < 0.25
    assert max(cream.values()) <= max(block_top.values())


def test_fidelity_controls_how_far_one_fit_reaches():
    u = lambda *v: tuple(x * S for x in v)  # designed in 1/64 units
    flat = [SurfacePiece(f"F{i}", u(i * 2, 8, 0), u(2, 2, 2)) for i in range(40)]
    ridge = [SurfacePiece("R0", u(80, 14, 0), u(2, 2, 2)), SurfacePiece("R1", u(82, 14, 0), u(2, 2, 2))]
    more = [SurfacePiece(f"G{i}", u(84 + i * 2, 8, 0), u(2, 2, 2)) for i in range(40)]
    pieces = flat + ridge + more
    fine = _all(pieces, fidelity="very_high")
    broad = _all(pieces, fidelity="low")
    reach = lambda L: max(min(abs(_x(c, L) - 80 * S), abs(_x(c, L) - 83 * S)) for c in L.cells) / S
    assert reach(fine) <= 3 < 10 < reach(broad)   # in 1/64 units, as designed
    # applicator override beats the blueprint's per-piece fidelity
    tagged = [SurfacePiece(p.piece_id, p.origin, p.size, fidelity="very_high") for p in pieces]
    assert _all(tagged, fidelity="low").cells == broad.cells
    assert _all(tagged).cells == fine.cells


def test_crack_fills_from_shell_base_but_opening_does_not():
    _, layer = _run()
    crack = [c for c in layer.cells if c.kind == "crack"]
    assert crack and all(CRACK_X[0] <= _x(c, layer) < CRACK_X[1] for c in crack)
    assert all(c.base == pytest.approx(21.0 * S) and c.top == pytest.approx(29.0 * S) for c in crack)
    _, none = _run(max_gap=0)
    assert not [c for c in none.cells if c.kind == "crack"]


def test_unrelated_regions_and_distant_pieces_do_not_influence_each_other():
    _, base = _run()
    _, changed = _run(obj=build_fixture_object(strip_two_heights={"Q1": 6, "Q2": 1}))
    assert _strip(base, 0, 8 * S) == _strip(changed, 0, 8 * S)
    assert _strip(base, 40 * S, 48 * S) != _strip(changed, 40 * S, 48 * S)
    obj = build_fixture_object()
    obj.primitives[0].position = (0.0, S / FINE_SUBDIVISION, 0.0)  # move P0 by one 1/64 step
    _, moved = _run(obj=obj)
    far = lambda L: [c for c in L.cells if _x(c, L) >= 20 * S]
    assert far(base) == far(moved)


def test_barriers_and_surface_ids_block_bridging():
    pieces, _ = _run()
    layer = compute_filler(pieces, FillerSelection(frozenset(p.piece_id for p in pieces),
                                                   barriers=frozenset({frozenset({"P0", "P1"})})))
    assert not any({"P0", "P1"} <= set(c.sources) for c in layer.cells)
    _, split = _run(annotations={"RECESS": {"tags": ["recess"]}, "P1": {"surface_id": "lip_upper"}})
    assert not any("P1" in c.sources and len(c.sources) > 1 for c in split.cells)


def test_region_outside_selection_is_unchanged():
    pieces, _ = _run()
    layer = compute_filler(pieces, FillerSelection(frozenset({"P0", "P1"})))
    assert layer.cells and all(set(c.sources) <= {"P0", "P1"} for c in layer.cells)
    assert all(_x(c, layer) < 16 * S for c in layer.cells)


# ── reversibility and the mesh pipeline ───────────────────────────────────

def test_removal_restores_original_and_regeneration_is_deterministic():
    obj = build_fixture_object()
    before_src = copy.deepcopy(obj.to_dict())
    before_glb = VoxelBaker().bake(obj)
    store = FillerCreamLayers()
    pieces, _ = pieces_from_voxel_object(obj, fixture_annotations())
    sel = FillerSelection(frozenset(p.piece_id for p in pieces))
    first = store.apply("all", pieces, sel)
    with_filler = bake_with_filler(obj, store.layers(), pieces=pieces)
    assert len(with_filler) > len(before_glb)
    assert obj.to_dict() == before_src
    for _ in range(3):
        again = store.apply("all", pieces, sel)
        assert again.fingerprint() == first.fingerprint() and again.volume() == first.volume()
    assert len(store.layers()) == 1
    assert bake_with_filler(obj, store.layers(), pieces=pieces) == with_filler
    assert store.remove("all") and store.layers() == []
    assert bake_with_filler(obj, store.layers(), pieces=pieces) == before_glb
    assert VoxelBaker().bake(obj) == before_glb
    assert FillerLayer.from_dict(first.to_dict()).fingerprint() == first.fingerprint()


def test_filler_mesh_goes_through_existing_glb_pipeline():
    obj = build_fixture_object()
    _, layer = _run(obj)
    glb = bake_with_filler(obj, [layer], unchecked=True)
    bv, _, bf = parse_glb(VoxelBaker().bake(obj))
    v, n, f = parse_glb(glb)
    assert len(f) == len(bf) + 12 * len(layer.cells)
    assert np.allclose(v[: len(bv)], bv) and int(f.max()) < len(v)
    assert np.allclose(np.linalg.norm(n, axis=1), 1.0, atol=1e-5)


def test_wedge_top_matches_voxel_studio_geometry():
    from modules.voxel_studio import build_primitive_geometry
    for ry, side in ((0, "-x"), (90, "+z"), (180, "+x"), (270, "-z")):
        v, _, _ = build_primitive_geometry(VoxelShape.WEDGE, 1.0, (0, ry, 0))
        p = SurfacePiece("w", (0, 0, 0), (64, 64, 64), "wedge", side)
        for x, y, z in v:
            if abs(y - 1.0) < 1e-5:
                assert p.top_at(1, 1, {0: x * 64, 2: z * 64}) == pytest.approx(64.0)


def test_a_designed_wedge_slope_gains_nothing():
    w = [SurfacePiece("W", (0, 0, 0), (64, 64, 64), "wedge", "-x")]
    assert _all(w, fidelity="high").cells == ()


def test_unsupported_shapes_become_occluders():
    """Corner cuts are supported since 2026-11-08; a corner turned off the
    vertical axis is still an occluder."""
    obj = build_fixture_object()
    obj.add_primitive(VoxelPrimitive(primitive_id="CORNER", shape=VoxelShape.CORNER_OUTER, size=8 / 64,
                                     position=(96 / 64, 0.0, 0.0)))
    obj.add_primitive(VoxelPrimitive(primitive_id="TIPPED", shape=VoxelShape.CORNER_INNER, size=8 / 64,
                                     position=(112 / 64, 0.0, 0.0), rotation_deg=(90.0, 0.0, 0.0)))
    pieces, notes = pieces_from_voxel_object(obj)
    shapes = {p.piece_id: p.shape for p in pieces}
    assert shapes["CORNER"] == "corner_outer"
    assert shapes["TIPPED"] == "occluder" and any(n.startswith("TIPPED") for n in notes)
    with pytest.raises(FillerCreamError):
        pieces_from_voxel_object(type(obj)(primitives=[VoxelPrimitive(size=0.01)]))


def test_large_floor_uses_coarse_grid_and_stays_level():
    from modules.voxel_block_kit import make_voxel_set, stage_floor
    floor = make_voxel_set("floor_20ft", "20 ft floor", stage_floor(24, 24))  # 24 blocks = 20 ft
    pieces = pieces_from_voxel_set(floor)
    t0 = time.perf_counter()
    layer = _all(pieces, fidelity="very_low")
    assert layer.grid_unit == 8 * S and layer.cells == ()   # 1/8-block columns, same real size as before
    assert time.perf_counter() - t0 < 30.0
    crack = [SurfacePiece("A", (0, 0, 0), (64, 64, 64)), SurfacePiece("B", (65, 0, 0), (64, 64, 64))]
    cl = _all(crack)
    assert cl.cells and all(c.top == 64.0 and c.base == 0.0 for c in cl.cells)


def test_candidate_shortcut_matches_checking_every_column():
    """Random scenes with mixed per-piece fidelity: the shortcut must equal
    the exhaustive result exactly (this caught a real skip on 2026-11-06)."""
    import random
    stops = list(FIDELITY_STOPS)
    for seed in range(12):
        rng = random.Random(seed)
        pieces = []
        for i in range(10):
            for j in range(3):
                h = rng.randint(0, 6)
                pieces.append(SurfacePiece(f"p{i}_{j}", (i * 4, h, j * 4), (4, 4, 4),
                                           surface_id=rng.choice(["a", "a", "a", "b"]),
                                           tags=frozenset(["recess"]) if rng.random() < 0.08 else frozenset(),
                                           fidelity=rng.choice(stops)))
        sel = FillerSelection(frozenset(p.piece_id for p in pieces))
        assert compute_filler(pieces, sel).cells == compute_filler(pieces, sel, _exhaustive=True).cells, seed


@pytest.mark.parametrize("face,axis_order,flip", [("+x", (1, 0, 2), 1), ("-y", (0, 1, 2), -1), ("-z", (0, 2, 1), -1)])
def test_every_face_direction_matches_the_top_face(face, axis_order, flip):
    """Rotate/mirror the stepped strip onto another face: same cream amount."""
    base_pieces, base = _run()
    moved = []
    for p in base_pieces:
        o = [p.origin[k] for k in axis_order]
        s = [p.size[k] for k in axis_order]
        up = face_axis = {"+x": 0, "-y": 1, "-z": 2}[face]
        if flip < 0:
            o[up] = -(o[up] + s[up])
        moved.append(SurfacePiece(p.piece_id, tuple(o), tuple(s), p.shape if p.shape != "wedge" else "cube",
                                  None, p.surface_id, p.tags, p.fidelity))
    layer = compute_filler(moved, FillerSelection(frozenset(p.piece_id for p in moved), face=face))
    assert len(layer.cells) == len(base.cells)
    assert layer.volume() == pytest.approx(base.volume())
    up = {"+x": 0, "-y": 1, "-z": 2}[face]
    for (lo, hi), cell in zip(layer.boxes(), layer.cells):
        assert hi[up] - lo[up] == pytest.approx(cell.top - cell.base)


def test_a_ceiling_never_blocks_the_floor_beneath_it():
    """Reviewer's case: a slab overhead (separated by air) used to zero the cream."""
    two = [SurfacePiece("A", (0, 0, 0), (8, 8, 8)), SurfacePiece("B", (8, 2, 0), (8, 8, 8))]
    sel = FillerSelection(frozenset({"A", "B"}))
    alone = compute_filler(two, sel)
    assert alone.cells
    ceiling = compute_filler(two + [SurfacePiece("CEIL", (0, 40, 0), (16, 4, 8))], sel)
    assert ceiling.cells == alone.cells
    lid = compute_filler(two + [SurfacePiece("LID", (0, 8, 0), (8, 4, 8))], sel)
    assert not any(c.column[0] < 8 for c in lid.cells), "a piece resting on the surface still covers it"


def test_saved_layers_detect_stale_cream_and_regenerate():
    from modules.filler_cream import layer_is_stale, regenerate
    pieces, _ = pieces_from_voxel_object(build_fixture_object(), fixture_annotations())
    sel = FillerSelection(frozenset({"P0", "P1", "P2", "P3"}), fidelity="high", barriers=frozenset({frozenset({"P2", "P3"})}))
    store = FillerCreamLayers()
    layer = store.apply("steps", pieces, sel)
    saved = FillerLayer.from_dict(json.loads(json.dumps(layer.to_dict())))
    assert saved.selection() == sel and saved.source_fingerprint == layer.source_fingerprint
    assert not layer_is_stale(saved, pieces)
    far = [p if p.piece_id != "Q1" else SurfacePiece("Q1", (8 * S, 9 * S, 40 * S), (8 * S,) * 3) for p in pieces]
    assert not layer_is_stale(saved, far), "editing a piece that can't affect it leaves it fresh"
    edited = [p if p.piece_id != "P1" else SurfacePiece("P1", (8 * S, 5 * S, 0), (8 * S,) * 3) for p in pieces]
    assert layer_is_stale(saved, edited) and store.stale(edited) == ["steps"]
    fresh = regenerate(saved, edited)
    assert fresh.cells == compute_filler(edited, sel).cells != layer.cells
    assert store.refresh(edited) == {"steps": "regenerated"} and store.stale(edited) == []
    gone = [p for p in pieces if p.piece_id != "P1"]
    assert store.refresh(gone)["steps"].startswith("needs attention")
    v1 = FillerLayer.from_dict({**layer.to_dict(), "version": 1, "selection": None, "source_fingerprint": ""})
    assert layer_is_stale(v1, pieces)


def test_generator_output_feeds_filler_cream():
    from modules import voxel_llm_adapter as vla
    from modules.filler_cream import pieces_from_generated_blocks
    _, blocks = vla._local_generate("kitchen table style chair")
    pieces, _ = pieces_from_generated_blocks(blocks)
    assert len(pieces) == len(blocks)
    layer = _all(pieces)
    assert all(c.top > c.base for c in layer.cells)
    seat_leg = [{"position": [0, 0, 0], "scale": [1, 1, 1], "material": "wood"},
                {"position": [1, 0, 0], "scale": [1, 1, 1], "material": "metal"}]
    p2, _ = pieces_from_generated_blocks(seat_leg)
    assert {p.surface_id for p in p2} == {"wood", "metal"}


def test_textured_bake_has_uvs_and_same_geometry():
    import struct as _st
    from modules.filler_cream import bake_textured
    obj = build_fixture_object()
    _, layer = _run(obj)
    plain = parse_glb(bake_with_filler(obj, [layer], unchecked=True))
    glb = bake_textured(obj, [layer], unchecked=True)
    v, n, f = parse_glb(glb)
    assert np.allclose(v, plain[0]) and np.array_equal(f, plain[2])
    jlen = _st.unpack_from("<I", glb, 12)[0]
    gltf = json.loads(glb[20:20 + jlen].decode())
    assert gltf["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_0"] == 2
    assert glb[20:20 + jlen].rstrip(b" ").endswith(b"}") and b"\x00" not in glb[20:20 + jlen]
    acc = gltf["accessors"][2]
    assert acc["count"] == len(v) and acc["type"] == "VEC2"


def test_engine_change_marks_saved_cream_stale_and_bad_inputs_raise(monkeypatch):
    import modules.filler_cream as fc
    pieces, _ = pieces_from_voxel_object(build_fixture_object(), fixture_annotations())
    layer = compute_filler(pieces, FillerSelection(frozenset({"P0", "P1"})))
    assert not fc.layer_is_stale(layer, pieces)
    monkeypatch.setattr(fc, "ENGINE_VERSION", "filler-cream/next")
    assert fc.layer_is_stale(layer, pieces), "a rule change must mark old cream stale"
    with pytest.raises(FillerCreamError):
        fc.source_fingerprint(pieces + [pieces[0]], FillerSelection(frozenset({"P0"})))
    with pytest.raises(FillerCreamError):
        fc.pack_glb_uv(np.zeros((0, 3)), np.zeros((0, 3)), np.zeros((0, 3)), np.zeros((0, 2)), "empty")
    with pytest.raises(FillerCreamError):
        fc.pack_glb_uv(np.zeros((3, 3)), np.zeros((3, 3)), np.array([[0, 1, 5]]), np.zeros((3, 2)), "bad")



def test_protected_slab_over_a_small_air_gap_is_never_penetrated():
    """Regression (outside review, 2026-11-06): cream rose to 9.68 inside a
    preserve-tagged slab whose base sits 1 unit above the surface."""
    two = [SurfacePiece("A", (0, 0, 0), (8, 8, 8)), SurfacePiece("B", (8, 2, 0), (8, 8, 8))]
    for tags in (frozenset({"preserve"}), frozenset()):
        slab = SurfacePiece("SLAB", (0, 9, 0), (8, 4, 8), tags=tags)
        layer = compute_filler(two + [slab], FillerSelection(frozenset({"A", "B"})))
        under = [c for c in layer.cells if c.column[0] < 8]
        assert under and all(c.top <= 9.0 + 1e-9 for c in under), "cream stops at the slab's underside"
    crack = [SurfacePiece("L", (0, 0, 0), (8, 8, 8)), SurfacePiece("R", (9, 0, 0), (8, 8, 8)),
             SurfacePiece("LID", (8, 6, 0), (1, 4, 8))]
    cl = compute_filler(crack, FillerSelection(frozenset({"L", "R"})))
    assert all(c.top <= 6.0 + 1e-9 for c in cl.cells if c.kind == "crack")


def test_stale_cream_can_never_silently_enter_a_bake():
    obj = build_fixture_object()
    pieces, _ = pieces_from_voxel_object(obj, fixture_annotations())
    store = FillerCreamLayers()
    store.apply("steps", pieces, FillerSelection(frozenset({"P0", "P1"})))
    with pytest.raises(FillerCreamError):
        bake_with_filler(obj, store.layers())                    # no pieces given: refused
    bake_with_filler(obj, store.bake_layers(pieces), pieces=pieces)  # fresh: fine
    gone = [p for p in pieces if p.piece_id != "P1"]
    assert store.refresh(gone)["steps"].startswith("needs attention")
    with pytest.raises(FillerCreamError):
        store.bake_layers(gone)                                  # failed refresh blocks the bake
    with pytest.raises(FillerCreamError):
        bake_with_filler(obj, store.layers(), pieces=gone)
    from modules.filler_cream import bake_textured
    with pytest.raises(FillerCreamError):
        bake_textured(obj, store.layers(), pieces=gone)



@pytest.mark.parametrize("bad", [
    dict(verts=np.zeros((3, 2))),                       # reviewer's case: (3,2) written as VEC3
    dict(normals=np.zeros((3, 4))),
    dict(uvs=np.zeros((3, 3))),
    dict(faces=np.array([0, 1, 2])),                    # not (M,3)
    dict(faces=np.array([[0, 1, 2, 0]])),
    dict(faces=np.array([[0, 1, -1]])),
    dict(faces=np.array([[0.0, 1.5, 2.0]])),
    dict(verts=np.array([[0, 0, 0], [1, 0, 0], [np.nan, 1, 0]], dtype=float)),
    dict(uvs=np.array([[0, 0], [1, np.inf], [0, 1]], dtype=float)),
    dict(verts=np.array([["a", "b", "c"]] * 3)),
])
def test_pack_glb_uv_rejects_malformed_arrays(bad):
    from modules.filler_cream import pack_glb_uv
    good = dict(verts=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float),
                normals=np.array([[0, 0, 1]] * 3, dtype=float),
                faces=np.array([[0, 1, 2]]), uvs=np.array([[0, 0], [1, 0], [0, 1]], dtype=float))
    assert parse_glb(pack_glb_uv(good["verts"], good["normals"], good["faces"], good["uvs"], "ok"))[2].shape == (1, 3)
    args = {**good, **bad}
    with pytest.raises(FillerCreamError):
        pack_glb_uv(args["verts"], args["normals"], args["faces"], args["uvs"], "bad")


# ── 2026-11-07 hostile review ───────────────────────────────────────────────

def test_rotated_piece_is_never_penetrated():
    """A cube turned 45 degrees pokes below its unturned box; cream must stop
    under the turned shape's lowest point, not the unturned box's base."""
    from modules.voxel_studio import VoxelObject, build_primitive_geometry
    f = float(FINE_SUBDIVISION)
    obj = VoxelObject(object_id="rot", name="rot", created_at=0.0)
    obj.add_primitive(VoxelPrimitive(primitive_id="A", shape=VoxelShape.CUBE, size=8 / f, position=(0, 0, 0)))
    obj.add_primitive(VoxelPrimitive(primitive_id="B", shape=VoxelShape.CUBE, size=8 / f, position=(8 / f, 4 / f, 0)))
    obj.add_primitive(VoxelPrimitive(primitive_id="TURNED", shape=VoxelShape.CUBE, size=3 / f,
                                     position=(4 / f, 11 / f, 0), rotation_deg=(0.0, 0.0, 45.0)))
    pieces, notes = pieces_from_voxel_object(obj)
    turned = {p.piece_id: p for p in pieces}["TURNED"]
    v, _, _ = build_primitive_geometry(VoxelShape.CUBE, 3 / f, (0.0, 0.0, 45.0))
    true_low = (11 / f + float(v[:, 1].min())) * f            # about 10.4, below the unturned base (11)
    assert true_low < 11 and turned.origin[1] <= true_low + 1e-6 and turned.size[0] > 3
    free = compute_filler([p for p in pieces if p.piece_id != "TURNED"], FillerSelection(frozenset({"A", "B"})))
    layer = compute_filler(pieces, FillerSelection(frozenset({"A", "B"})))
    g = layer.grid_unit
    under = lambda L: [c for c in L.cells if turned.origin[0] <= c.column[0] * g < turned.origin[0] + turned.size[0]
                       and c.column[1] * g < turned.size[2]]
    assert any(c.top > true_low for c in under(free)), "without the piece, cream would rise into its space"
    assert under(layer) and all(c.top <= true_low + 1e-9 for c in under(layer))


def test_gap_claims_use_the_local_surface_not_the_highest_point():
    """Multi-level scene: a shelf above a low crack must not block that crack
    just because some other selected piece sits higher than the shelf."""
    pieces = [SurfacePiece("L", (0, 0, 0), (8, 8, 8)), SurfacePiece("R", (9, 0, 0), (8, 8, 8)),
              SurfacePiece("TALL", (40, 30, 0), (8, 10, 8)),
              SurfacePiece("SHELF", (8, 20, 0), (1, 4, 8))]        # 12 units above the crack
    layer = compute_filler(pieces, FillerSelection(frozenset({"L", "R", "TALL"})))
    crack = [c for c in layer.cells if c.kind == "crack"]
    assert crack and all(c.top == pytest.approx(8.0) for c in crack)


def test_crossing_cracks_fill_at_the_intersection():
    """A plus-shaped 1-unit gap: straight-line search can't see across the
    centre (the gap runs on both axes); the diagonal search can."""
    pieces = [SurfacePiece(f"c{i}_{j}", (i, 0, j), (1, 8, 1))
              for i in range(9) for j in range(9) if i != 4 and j != 4]
    sel = FillerSelection(frozenset(p.piece_id for p in pieces))
    layer = compute_filler(pieces, sel)
    filled = {c.column for c in layer.cells if c.kind == "crack"}
    assert (4, 4) in filled
    assert filled == {(i, 4) for i in range(9)} | {(4, j) for j in range(9)}
    assert layer.cells == compute_filler(pieces, sel, _exhaustive=True).cells


def test_cell_source_lists_are_capped():
    from modules.filler_cream import MAX_SOURCES_PER_CELL
    flat = [SurfacePiece(f"F{i}", (i, 8, 0), (1, 2, 1)) for i in range(60)]
    bump = [SurfacePiece("BUMP", (60, 8, 0), (2, 6, 1))]
    more = [SurfacePiece(f"G{i}", (62 + i, 8, 0), (1, 2, 1)) for i in range(60)]
    layer = _all(flat + bump + more, fidelity="low")
    assert layer.cells and all(len(c.sources) <= MAX_SOURCES_PER_CELL for c in layer.cells)
    assert any(c.sources[-1].endswith("more") for c in layer.cells)


def test_old_saved_selections_still_load():
    old = {"piece_ids": ["P0", "P1"], "face": "+y", "barriers": [], "max_step": None, "max_gap": 2,
           "ramp_samples": 4, "fidelity": "high"}
    loaded = FillerSelection.from_dict(old)
    assert loaded.grid_samples == 4
    assert loaded.max_gap == 2 * S, "lengths saved at 1/64 keep their real size"
    assert FillerSelection.from_dict(loaded.to_dict()) == loaded


# ── 2026-11-07 resource pass ────────────────────────────────────────────────

def test_fast_path_matches_the_careful_per_column_search():
    """The moment-sum fast path must give the same cream as walking every
    window: same columns, same sources, heights equal to rounding."""
    import random
    stops = list(FIDELITY_STOPS)
    for seed in range(15):
        rng = random.Random(100 + seed)
        pieces = []
        for i in range(12):
            for j in range(6):
                if rng.random() < 0.06:
                    continue
                shape, side = ("wedge", rng.choice(["-x", "+x", "-z", "+z"])) if rng.random() < 0.1 else ("cube", None)
                pieces.append(SurfacePiece(f"p{i}_{j}", (i * 4, rng.randint(0, 8), j * 4), (4, 4, 4), shape, side,
                                           rng.choice(["a", "a", "a", "b"]),
                                           frozenset(["recess"]) if rng.random() < 0.05 else frozenset(),
                                           rng.choice(stops)))
        sel = FillerSelection(frozenset(p.piece_id for p in pieces))
        fast = {c.column: c for c in compute_filler(pieces, sel).cells}
        careful = {c.column: c for c in compute_filler(pieces, sel, _careful_only=True).cells}
        assert set(fast) == set(careful), seed
        for k in fast:
            assert fast[k].sources == careful[k].sources and fast[k].kind == careful[k].kind
            assert fast[k].top == pytest.approx(careful[k].top, abs=1e-9)


def test_fast_path_batches_give_the_same_answer(monkeypatch):
    import modules.filler_cream as fc
    pieces = curve_pieces()
    sel = FillerSelection(frozenset(p.piece_id for p in pieces), fidelity="high")
    whole = compute_filler(pieces, sel).cells
    monkeypatch.setattr(fc, "FAST_PATH_BATCH", 7)
    assert compute_filler(pieces, sel).cells == whole


def test_vectorised_normals_match_voxel_studio_exactly():
    from modules.filler_cream import _flat_normals
    from modules.voxel_studio import _compute_normals
    _, layer = _run()
    from modules.voxel_studio import VoxelShape as VS, _shape_verts_faces
    uv, uf = _shape_verts_faces(VS.CUBE)
    bx = layer.boxes()
    lo = np.array([b[0] for b in bx]) / 64.0
    ext = np.array([b[1] for b in bx]) / 64.0 - lo
    V = (uv[None] * ext[:, None] + lo[:, None]).reshape(-1, 3)
    F = (uf[None] + (np.arange(len(bx)) * len(uv))[:, None, None]).reshape(-1, 3)
    for got, want in zip(_flat_normals(V, F), _compute_normals(V, F)):
        assert np.array_equal(got, want)
    deg = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0]], float)
    for got, want in zip(_flat_normals(deg, np.array([[0, 1, 2], [0, 1, 3]])),
                         _compute_normals(deg, np.array([[0, 1, 2], [0, 1, 3]]))):
        assert np.array_equal(got, want)


# ── 2026-11-08: 1/128 for Primp faces and close-ups ─────────────────────────

def test_lip_edge_and_eyelid_crease_at_1_128():
    """1/128 blocks hold the designed lip and lid shapes about twice as closely
    as 1/64 blocks, cream never crosses the lip border or the lid/brow parts,
    and the marked crease is left exactly as built."""
    import re
    from modules.filler_cream_fixture import lip_and_lid_pieces, lip_true_curve
    errors = {}
    for step in (2, 1):                              # 1/64 blocks, then 1/128 blocks
        pieces = lip_and_lid_pieces(step)
        layer = _all(pieces, fidelity="very_high")
        g = layer.grid_unit
        assert layer.cells
        for c in layer.cells:
            parts = {re.sub(r"\d+$", "", s) for s in c.sources}
            assert len(parts) == 1, f"cream crossed parts at {c.column}: {parts}"
            assert not (60 <= c.column[0] * g < 62), "the marked crease is untouched"
        top = {}
        for p in pieces:
            for x in range(p.origin[0], p.origin[0] + p.size[0]):
                top[x] = p.origin[1] + p.size[1]
        cream = {c.column[0]: c.top for c in layer.cells if c.column[1] == 0}
        xs = [x for x in sorted(top) if not 60 <= x < 62]
        raw = sum(abs(lip_true_curve(x + 0.5) - top[x]) for x in xs) / len(xs)
        done = sum(abs(lip_true_curve(x + 0.5) - max(top[x], cream.get(x // g, top[x]))) for x in xs) / len(xs)
        assert done < raw
        errors[step] = done * FINE_UNIT_MM
    # measured 2026-11-08: 1/64 -> 1.35 mm, 1/128 -> 0.73 mm mean distance from the design
    assert errors[1] < 0.65 * errors[2], errors


def test_contract_voxel_sets_at_1_64_and_1_128_feed_filler_cream():
    """The voxel contract now accepts 1/64 and 1/128; a two-step lip-edge
    patch built either way reaches Filler Cream at the right real size."""
    from modules.voxel_block_kit import make_voxel_set
    from modules.voxel_set_contract import pub_block_measurement
    assert pub_block_measurement(128)["unit_inches"] == pytest.approx(10 / 128)
    assert pub_block_measurement(64)["unit_inches"] == pytest.approx(10 / 64)
    results = {}
    for sub in (64, 128):
        k = sub // 64                                  # blocks per 1/64 step at this subdivision
        blocks = [{"x": x * k + dx, "y": (0 if x < 4 else 1) * k + dy, "z": z * k + dz}
                  for x in range(8) for z in range(2) for dx in range(k) for dy in range(k) for dz in range(k)]
        vs = make_voxel_set(f"lip_{sub}", "lip patch", blocks, subdivision=sub)
        pieces = pieces_from_voxel_set(vs)
        assert {p.size for p in pieces} == {(FINE_SUBDIVISION // sub,) * 3}
        layer = _all(pieces, fidelity="high")
        results[sub] = layer.volume() * (FINE_UNIT_MM ** 3)   # cubic millimetres
        assert layer.cells
    # Measured 2026-11-08: 172.7 mm^3 (1/64 blocks) vs 195.0 mm^3 (1/128 blocks).
    # 1/128 pieces get 1/128 columns, which follow the ramp more closely.
    assert results[128] == pytest.approx(results[64], rel=0.15), results



# ── 2026-11-08: corner-cut pieces take cream ────────────────────────────────

def _ray_top(v, f, x, z):
    """Highest point of VoxelStudio's actual triangles above (x, z)."""
    best = None
    for a, b, c in f:
        A, B, C = v[a], v[b], v[c]
        d = (B[0] - A[0]) * (C[2] - A[2]) - (C[0] - A[0]) * (B[2] - A[2])
        if abs(d) < 1e-12:
            continue
        l1 = ((x - A[0]) * (C[2] - A[2]) - (C[0] - A[0]) * (z - A[2])) / d
        l2 = ((B[0] - A[0]) * (z - A[2]) - (x - A[0]) * (B[2] - A[2])) / d
        if l1 >= -1e-9 and l2 >= -1e-9 and l1 + l2 <= 1 + 1e-9:
            y = A[1] + l1 * (B[1] - A[1]) + l2 * (C[1] - A[1])
            best = y if best is None else max(best, y)
    return best


@pytest.mark.parametrize("shape", [VoxelShape.CORNER_OUTER, VoxelShape.CORNER_INNER])
@pytest.mark.parametrize("turns", [0, 1, 2, 3])
def test_corner_tops_match_voxel_studio_geometry(shape, turns):
    from modules.voxel_studio import build_primitive_geometry
    v, _, f = build_primitive_geometry(shape, 1.0, (0.0, 90.0 * turns, 0.0))
    v = v.astype(float)
    p = SurfacePiece("c", (0, 0, 0), (64, 64, 64), shape.value, y_turns=turns)
    for x in np.linspace(0.02, 0.98, 9):
        for z in np.linspace(0.02, 0.98, 9):
            assert p.top_at(1, 1, {0: x * 64, 2: z * 64}) / 64 == pytest.approx(_ray_top(v, f, x, z), abs=1e-12)


def test_corner_pieces_map_from_voxel_studio_and_take_cream():
    f = float(FINE_SUBDIVISION)
    from modules.voxel_studio import VoxelObject
    obj = VoxelObject(object_id="corners", name="corners", created_at=0.0)
    for i in range(6):                                            # a low floor row
        obj.add_primitive(VoxelPrimitive(primitive_id=f"F{i}", shape=VoxelShape.CUBE, size=8 / f,
                                         position=(i * 8 / f, 0.0, 0.0)))
    obj.add_primitive(VoxelPrimitive(primitive_id="PEAK", shape=VoxelShape.CORNER_OUTER, size=8 / f,
                                     position=(16 / f, 8 / f, 0.0), rotation_deg=(0.0, 90.0, 0.0)))
    pieces, notes = pieces_from_voxel_object(obj)
    peak = {p.piece_id: p for p in pieces}["PEAK"]
    assert peak.shape == "corner_outer" and peak.y_turns == 1 and not notes
    alone = _all([p for p in pieces if p.piece_id != "PEAK"], fidelity="high")
    assert alone.cells == ()                                      # a flat floor gains nothing
    layer = _all(pieces, fidelity="high")
    assert layer.cells, "cream blends the floor up toward the corner piece"
    assert max(c.top for c in layer.cells) <= 16 + 1e-9           # never above the corner's apex
    assert not any("PEAK" == c.sources[0] and len(c.sources) == 1 for c in layer.cells), \
        "a designed corner slope on its own gains nothing"
    sel = FillerSelection(frozenset(p.piece_id for p in pieces), fidelity="high")
    fast = {c.column: c for c in compute_filler(pieces, sel).cells}
    careful = {c.column: c for c in compute_filler(pieces, sel, _careful_only=True).cells}
    assert set(fast) == set(careful) and all(fast[k].top == pytest.approx(careful[k].top, abs=1e-9) for k in fast)


def test_a_designed_corner_slope_gains_nothing():
    for shape in ("corner_outer", "corner_inner"):
        for k in range(4):
            assert _all([SurfacePiece("C", (0, 0, 0), (64, 64, 64), shape, y_turns=k)], fidelity="high").cells == ()
