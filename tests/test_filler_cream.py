"""Focused tests for modules/filler_cream.py on the 1/64 proof fixtures."""
from __future__ import annotations

import copy
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
from modules.voxel_set_contract import PUB_BLOCK_METERS
from modules.voxel_studio import VoxelBaker, VoxelPrimitive, VoxelShape


def _all(pieces, **kw):
    return compute_filler(pieces, FillerSelection(frozenset(p.piece_id for p in pieces), **kw))


def _run(obj=None, annotations=None, **sel_kw):
    obj = obj or build_fixture_object()
    pieces, _ = pieces_from_voxel_object(obj, fixture_annotations() if annotations is None else annotations)
    return pieces, _all(pieces, **sel_kw)


def _strip(layer, z_lo, z_hi):
    return [c for c in layer.cells if z_lo <= c.column[1] < z_hi]


def _tops(pieces):
    return {p.piece_id: p.origin[1] + p.size[1] for p in pieces}


# ── units ──────────────────────────────────────────────────────────────────

def test_units_come_from_the_existing_block():
    assert FINE_SUBDIVISION == 64
    assert FINE_UNIT_MM == pytest.approx(PUB_BLOCK_METERS * 1000 / 64) == pytest.approx(3.96875)
    assert fidelity_span_fine("very_high") == 3 and fidelity_span_fine("high") == 8
    assert fidelity_span_fine("very_low") == 64 and fidelity_span_fine(31.75) == pytest.approx(8)
    assert list(FIDELITY_STOPS) == ["very_high", "high", "medium", "low", "very_low"]
    with pytest.raises(FillerCreamError):
        fidelity_span_fine("ultra")
    for _, x, y, z, s in STRIP_ONE:
        assert all(isinstance(v, int) for v in (x, y, z, s))


# ── core behaviour ─────────────────────────────────────────────────────────

def test_steps_are_smoothed_and_never_exceed_nearby_blocks():
    pieces, layer = _run()
    tops = _tops(pieces)
    assert {c.column[0] for c in _strip(layer, 0, 8) if c.column[0] < 8}, "P0 step gets cream"
    for c in layer.cells:
        assert c.top > c.base
        assert c.top <= max(tops[s] for s in c.sources) + 1e-9
    row = [c.top for c in sorted(_strip(layer, 3, 4), key=lambda c: c.column) if c.column[0] < 16]
    assert row == sorted(row), "cream rises evenly up the staircase, no lip at the open end"


def test_unmarked_protrusion_blends_at_its_base_but_keeps_its_top():
    pieces, layer = _run()
    xs = {c.column[0] for c in _strip(layer, 0, 8)}
    assert any(24 <= x < 32 for x in xs), "approach to the protrusion is blended"
    assert not any(32 <= x < 40 for x in xs), "protrusion top untouched"
    approach = [c.top for c in sorted(_strip(layer, 3, 4), key=lambda c: c.column) if 20 <= c.column[0] < 32]
    assert approach == sorted(approach) and max(b - a for a, b in zip(approach, approach[1:])) < 3.0, \
        "the blend up to the protrusion is a continuous ramp, not a cliff"
    _, marked = _run(annotations={"RECESS": {"tags": ["recess"]}, "PROT": {"tags": ["protrusion"]}})
    assert not any("PROT" in c.sources for c in marked.cells), "a marked protrusion is left exactly as built"


def test_marked_recess_and_opening_stay_intact():
    _, layer = _run()
    xs = {c.column[0] for c in _strip(layer, 0, 8)}
    assert not any(RECESS_X[0] <= x < RECESS_X[1] for x in xs)
    assert not any(OPENING_X[0] <= x < OPENING_X[1] for x in xs)
    _, unmarked = _run(annotations={})
    assert any(RECESS_X[0] <= x < RECESS_X[1] for x in {c.column[0] for c in unmarked.cells}), \
        "without the mark the recess would be filled: the blueprint mark is what protects it"


def test_fingertip_skin_nail_and_nail_edge_stay_distinct():
    marked = _all(finger_pieces(marked=True), fidelity="high")
    for c in marked.cells:
        surfaces = {("nail" if s.startswith("N") else "skin") for s in c.sources}
        assert len(surfaces) == 1, f"cream crossed skin/nail at {c.column}"
    assert not any(c.column[0] >= 56 and {"N2"} & set(c.sources) for c in marked.cells)
    unmarked = _all(finger_pieces(marked=False), fidelity="high")
    assert any({"S3", "N0"} <= set(c.sources) for c in unmarked.cells), \
        "unmarked, the skin-to-nail drop would be smoothed away"


def test_short_best_fits_follow_a_curve():
    pieces = curve_pieces()
    tops = {p.piece_id: (p.origin[0] + p.size[0] / 2, p.origin[1] + p.size[1]) for p in pieces}
    layer = _all(pieces, fidelity="high")
    filled = {c.column[0]: c.top for c in layer.cells if c.column[1] == 0}
    before, after = [], []
    for x in range(96):
        h = next(t for pid, (cx, t) in tops.items() if abs(cx - (x // 2 * 2 + 1)) < 1e-9)
        truth = true_curve(x + 0.5)
        before.append(abs(truth - h))
        after.append(abs(truth - max(h, filled.get(x, h))))
    # Outer-points rule, measured 2026-11-06 at high fidelity: error 48.8 -> 25.5,
    # largest step 1 -> 0.55, never more than 0.11 fine units above the true curve.
    surface = [max(h, filled.get(x, h)) for x, h in enumerate(
        next(t for _, (cx, t) in tops.items() if abs(cx - (x // 2 * 2 + 1)) < 1e-9) for x in range(96))]
    assert sum(after) < 0.6 * sum(before), (sum(before), sum(after))
    assert max(abs(surface[x + 1] - surface[x]) for x in range(95)) < 0.7
    assert max(surface[x] - true_curve(x + 0.5) for x in range(96)) < 0.25
    assert max(filled.values()) <= max(t for _, t in tops.values())


def test_fidelity_controls_how_far_one_fit_reaches():
    flat = [SurfacePiece(f"F{i}", (i * 2, 8, 0), (2, 2, 2)) for i in range(40)]
    ridge = [SurfacePiece("R0", (80, 14, 0), (2, 2, 2)), SurfacePiece("R1", (82, 14, 0), (2, 2, 2))]
    more = [SurfacePiece(f"G{i}", (84 + i * 2, 8, 0), (2, 2, 2)) for i in range(40)]
    pieces = flat + ridge + more
    fine = _all(pieces, fidelity="very_high")
    broad = _all(pieces, fidelity="low")
    reach = lambda L: max(min(abs(c.column[0] - 80), abs(c.column[0] - 83)) for c in L.cells)
    assert reach(fine) <= 3 < 10 < reach(broad)
    # applicator override beats the blueprint's per-piece fidelity
    tagged = [SurfacePiece(p.piece_id, p.origin, p.size, fidelity="very_high") for p in pieces]
    assert _all(tagged, fidelity="low").cells == broad.cells
    assert _all(tagged).cells == fine.cells


def test_crack_fills_from_shell_base_but_opening_does_not():
    _, layer = _run()
    crack = [c for c in layer.cells if c.kind == "crack"]
    assert crack and all(CRACK_X[0] <= c.column[0] < CRACK_X[1] for c in crack)
    assert all(c.base == pytest.approx(21.0) and c.top == pytest.approx(29.0) for c in crack)
    _, none = _run(max_gap=0)
    assert not [c for c in none.cells if c.kind == "crack"]


def test_unrelated_regions_and_distant_pieces_do_not_influence_each_other():
    _, base = _run()
    _, changed = _run(obj=build_fixture_object(strip_two_heights={"Q1": 6, "Q2": 1}))
    assert _strip(base, 0, 8) == _strip(changed, 0, 8)
    assert _strip(base, 40, 48) != _strip(changed, 40, 48)
    obj = build_fixture_object()
    obj.primitives[0].position = (0.0, 1 / FINE_SUBDIVISION, 0.0)  # move P0
    _, moved = _run(obj=obj)
    far = lambda L: [c for c in L.cells if c.column[0] >= 20]
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
    assert {c.column[0] for c in layer.cells} <= set(range(0, 16))


# ── reversibility and the mesh pipeline ───────────────────────────────────

def test_removal_restores_original_and_regeneration_is_deterministic():
    obj = build_fixture_object()
    before_src = copy.deepcopy(obj.to_dict())
    before_glb = VoxelBaker().bake(obj)
    store = FillerCreamLayers()
    pieces, _ = pieces_from_voxel_object(obj, fixture_annotations())
    sel = FillerSelection(frozenset(p.piece_id for p in pieces))
    first = store.apply("all", pieces, sel)
    with_filler = bake_with_filler(obj, store.layers())
    assert len(with_filler) > len(before_glb)
    assert obj.to_dict() == before_src
    for _ in range(3):
        again = store.apply("all", pieces, sel)
        assert again.fingerprint() == first.fingerprint() and again.volume() == first.volume()
    assert len(store.layers()) == 1
    assert bake_with_filler(obj, store.layers()) == with_filler
    assert store.remove("all") and store.layers() == []
    assert bake_with_filler(obj, store.layers()) == before_glb
    assert VoxelBaker().bake(obj) == before_glb
    assert FillerLayer.from_dict(first.to_dict()).fingerprint() == first.fingerprint()


def test_filler_mesh_goes_through_existing_glb_pipeline():
    obj = build_fixture_object()
    _, layer = _run(obj)
    glb = bake_with_filler(obj, [layer])
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
    obj = build_fixture_object()
    obj.add_primitive(VoxelPrimitive(primitive_id="CORNER", shape=VoxelShape.CORNER_OUTER, size=8 / 64,
                                     position=(96 / 64, 0.0, 0.0)))
    pieces, notes = pieces_from_voxel_object(obj)
    assert any(n.startswith("CORNER") for n in notes)
    assert {p.piece_id: p.shape for p in pieces}["CORNER"] == "occluder"
    with pytest.raises(FillerCreamError):
        pieces_from_voxel_object(type(obj)(primitives=[VoxelPrimitive(size=0.01)]))


def test_large_floor_uses_coarse_grid_and_stays_level():
    from modules.voxel_block_kit import make_voxel_set, stage_floor
    floor = make_voxel_set("floor_20ft", "20 ft floor", stage_floor(24, 24))  # 24 blocks = 20 ft
    pieces = pieces_from_voxel_set(floor)
    t0 = time.perf_counter()
    layer = _all(pieces, fidelity="very_low")
    assert layer.grid_unit == 8 and layer.cells == ()
    assert time.perf_counter() - t0 < 30.0
    crack = [SurfacePiece("A", (0, 0, 0), (64, 64, 64)), SurfacePiece("B", (65, 0, 0), (64, 64, 64))]
    cl = _all(crack)
    assert cl.cells and all(c.top == 64.0 and c.base == 0.0 for c in cl.cells)
