"""Focused tests for modules/filler_cream.py on the 1/64 proof fixture."""
from __future__ import annotations

import copy
import time

import numpy as np
import pytest

from modules.filler_cream import (
    FINE_SUBDIVISION, FINE_UNIT_MM, FillerCreamError, FillerCreamLayers, FillerLayer,
    FillerSelection, SurfacePiece, bake_with_filler, compute_filler, parse_glb,
    pieces_from_voxel_object, pieces_from_voxel_set,
)
from modules.filler_cream_fixture import (
    CRACK_X, OPENING_X, RECESS_X, STRIP_ONE, build_fixture_object, fixture_annotations,
)
from modules.voxel_studio import VoxelBaker, VoxelPrimitive, VoxelShape


def _run(obj=None, annotations=None, **sel_kw):
    obj = obj or build_fixture_object()
    pieces, notes = pieces_from_voxel_object(obj, fixture_annotations() if annotations is None else annotations)
    sel = FillerSelection(frozenset(p.piece_id for p in pieces), **sel_kw)
    return pieces, compute_filler(pieces, sel)


def _strip(layer, z_lo, z_hi):
    return [c for c in layer.cells if z_lo <= c.column[1] < z_hi]


def _tops(pieces):
    return {p.piece_id: p.origin[1] + p.size[1] for p in pieces}


def test_units_match_existing_terminology():
    assert FINE_SUBDIVISION == 64
    assert abs(FINE_UNIT_MM - 3.96875) < 1e-9  # 10 in / 64
    for _, x, y, z, s in STRIP_ONE:  # fixture is whole fine units
        assert all(isinstance(v, int) for v in (x, y, z, s))


def test_eligible_steps_receive_bounded_filler():
    pieces, layer = _run()
    tops = _tops(pieces)
    sources = {c.sources for c in layer.cells if c.kind == "ramp"}
    assert {("P0", "P1"), ("P1", "P2"), ("P2", "P3"), ("P8", "P7")} <= sources
    for c in layer.cells:
        a, b = c.sources
        assert c.top > c.base
        assert c.top <= max(tops[a], tops[b]) + 1e-9          # never beyond local contour
        if c.kind == "ramp":
            assert c.base == pytest.approx(tops[a])            # starts on the existing surface
    # ramp rises monotonically toward the higher neighbour
    row = [c.top for c in sorted(_strip(layer, 0, 1), key=lambda c: c.column) if c.sources == ("P0", "P1")]
    assert row == sorted(row) and len(row) == 4


def test_designed_edge_recess_and_opening_stay_intact():
    pieces, layer = _run()
    xs = {c.column[0] for c in _strip(layer, 0, 8)}
    assert not any(RECESS_X[0] <= x < RECESS_X[1] for x in xs)      # recess untouched
    assert not any(OPENING_X[0] <= x < OPENING_X[1] for x in xs)    # opening untouched
    assert not any(("P3", "PROT") == c.sources for c in layer.cells)  # 16-unit designed edge kept
    assert not any(32 <= x < 40 for x in xs)                         # protrusion top untouched


def test_recess_protection_comes_from_the_explicit_tag():
    _, untagged = _run(annotations={})
    xs = {c.column[0] for c in _strip(untagged, 0, 8)}
    assert any(RECESS_X[0] <= x < RECESS_X[1] for x in xs), "without the tag the 6-unit pit is fillable"


def test_crack_fills_from_shell_base_but_opening_does_not():
    pieces, layer = _run()
    crack = [c for c in layer.cells if c.kind == "crack"]
    assert crack and all(CRACK_X[0] <= c.column[0] < CRACK_X[1] for c in crack)
    assert all(c.base == pytest.approx(21.0) and c.top == pytest.approx(29.0) for c in crack)
    _, wide = _run(max_gap=0)
    assert not [c for c in wide.cells if c.kind == "crack"]


def test_unrelated_regions_do_not_influence_each_other():
    _, base = _run()
    _, changed = _run(obj=build_fixture_object(strip_two_heights={"Q1": 6, "Q2": 1}))
    assert _strip(base, 0, 8) == _strip(changed, 0, 8)
    assert _strip(base, 40, 48) != _strip(changed, 40, 48)
    # locality inside one strip: moving P0 only changes the P0/P1 fill
    obj = build_fixture_object()
    obj.primitives[0].position = (0.0, 1 / FINE_SUBDIVISION, 0.0)
    _, moved = _run(obj=obj)
    far = lambda L: [c for c in L.cells if c.column[0] >= 8]
    assert far(base) == far(moved)


def test_barriers_and_surface_ids_block_bridging():
    pieces, _ = _run()
    sel = FillerSelection(frozenset(p.piece_id for p in pieces), barriers=frozenset({frozenset({"P0", "P1"})}))
    layer = compute_filler(pieces, sel)
    assert not any(c.sources == ("P0", "P1") for c in layer.cells)
    _, split = _run(annotations={"RECESS": {"tags": ["recess"]}, "P1": {"surface_id": "lip_upper"}})
    assert not any("P1" in c.sources for c in split.cells)


def test_region_outside_selection_is_unchanged():
    pieces, _ = _run()
    layer = compute_filler(pieces, FillerSelection(frozenset({"P0", "P1"})))
    assert {c.sources for c in layer.cells} == {("P0", "P1")}
    assert {c.column[0] for c in layer.cells} <= set(range(0, 16))


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
    assert obj.to_dict() == before_src                       # source never touched
    for _ in range(3):                                        # re-apply: no buildup
        again = store.apply("all", pieces, sel)
        assert again.fingerprint() == first.fingerprint() and again.volume() == first.volume()
    assert len(store.layers()) == 1
    assert bake_with_filler(obj, store.layers()) == with_filler
    assert store.remove("all") and store.layers() == []
    assert bake_with_filler(obj, store.layers()) == before_glb  # byte-identical original
    assert VoxelBaker().bake(obj) == before_glb
    assert FillerLayer.from_dict(first.to_dict()).fingerprint() == first.fingerprint()


def test_filler_mesh_goes_through_existing_glb_pipeline():
    obj = build_fixture_object()
    pieces, layer = _run(obj)
    glb = bake_with_filler(obj, [layer])
    bv, bn, bf = parse_glb(VoxelBaker().bake(obj))
    v, n, f = parse_glb(glb)
    assert len(f) == len(bf) + 12 * len(layer.cells)          # 12 triangles per filler box
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
    layer = compute_filler(pieces, FillerSelection(frozenset(p.piece_id for p in pieces)))
    elapsed = time.perf_counter() - t0
    assert layer.grid_unit == 8          # 1/8 block columns, not 1/64
    assert layer.cells == ()             # a level floor gains nothing
    assert elapsed < 30.0
    # a fractional crack in a floor is filled level with it
    crack = [SurfacePiece("A", (0, 0, 0), (64, 64, 64)), SurfacePiece("B", (65, 0, 0), (64, 64, 64))]
    cl = compute_filler(crack, FillerSelection(frozenset({"A", "B"})))
    assert cl.cells and all(c.top == 64.0 and c.base == 0.0 for c in cl.cells)
