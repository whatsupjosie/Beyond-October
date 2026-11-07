# Filler Cream — usage and rules

Code: `modules/filler_cream.py`. Proof fixture: `modules/filler_cream_fixture.py`. Tests: `tests/test_filler_cream.py`. View tool: `tools/filler_cream_view.py`.

## Units (checked against existing code)

- One PubBlock = 10 in = 0.254 m (`modules/voxel_set_contract.py`).
- The existing subdivisions are full = 1, half = 2, quarter = 4 (contract), and VoxelStudio sizes are floats in block units, 1.0 / 0.5 / 0.25 (`modules/voxel_studio.py`).
- Filler Cream works in **fine units = 1/64 block = 0.15625 in = 3.96875 mm**. Everything is a whole number of fine units.
- The canonical contract still rejects subdivision 64. This module does not change it. VoxelStudio already accepts any float size, so 1/64-multiple primitives bake today.

## Run it (PowerShell 5, from the repo root)

    python -m pytest -p no:cacheprovider tests\test_filler_cream.py -q
    python tools\filler_cream_view.py

The view tool writes `docs\filler_cream\fixture_before.glb`, `fixture_after.glb` and `before_after_profile.png`.

## Call it from Python

    from modules.filler_cream import FillerSelection, FillerCreamLayers, pieces_from_voxel_object, bake_with_filler
    pieces, notes = pieces_from_voxel_object(voxel_object, annotations={"EYE_PIT": {"tags": ["recess"]}})
    layers = FillerCreamLayers()
    layers.apply("knee_left", pieces, FillerSelection(frozenset({"K1", "K2", "K3"}), face="+y"))
    glb_bytes = bake_with_filler(voxel_object, layers.layers())
    layers.remove("knee_left")   # original geometry back, byte for byte

For a canonical voxel set (the block kit, PubWorld sets) use `pieces_from_voxel_set(voxel_set)`. Block metadata `surface_id` (or `part`) and `filler_tags` / `filler: "preserve"` carry the boundaries.

Selection scale: one exposed face = one piece id with its `face`; one voxel's exposed surface = the same piece with each face you want; a connected group = a set of ids. A 20 × 20 ft floor is just a bigger set (see the floor test).

## The local interpolation rule

Applied on one exposed face orientation at a time. The selection is laid out as columns on that face; each column belongs to the outermost piece over it and has a surface height.

1. **Ramp (step fill).** For a column of piece A, look along each of the four in-plane directions to A's edge. If the next piece B is an eligible neighbour and is higher by a step no bigger than `max_step`, add cream that rises linearly from nothing at the middle of A's run to the step height at the shared edge. Capped at the higher of the two surfaces. Only ever adds. The highest of the four directions wins.
2. **Crack.** An empty run of columns between two eligible pieces, no wider than `max_gap` (default 2 fine units, about 8 mm), is filled from the shell base (the higher of the two pieces' bases, so it never reaches into the hollow interior) up to the straight line between the two surfaces. Wider empty runs are openings and stay empty.

**Eligible neighbour:** both selected; both shapes supported on this face; neither tagged `preserve`, `recess`, `protrusion`, `edge` or `opening`; same `surface_id`; not listed together in `barriers`; and the step is no bigger than `max_step` (default: the thinner piece's thickness along the face normal). Pieces must touch column to column or sit across a crack; nearness alone never counts.

Every filler value depends only on piece A's own run and the one column across its edge, so nothing reaches past one piece width. A nose-tip piece cannot affect an eye-corner piece. A bigger selection means more of these small fills, never deeper ones.

**No buildup:** filler is computed from the original pieces only and never reads existing filler. Re-applying replaces the layer; removing it restores the source exactly.

## Limits (honest list)

- One face orientation per call. A curved body part is handled as patches per face direction; cream does not wrap around an edge from a top face onto a side face.
- Filler boxes have flat tops at the working grid, so each ramp is a fine staircase (0.25 fine unit, about 1 mm, in the fixture). Smoothing that is sanding, which is out of scope.
- The ramp covers half of the lower piece's run. At the edge column a small riser of step ÷ run length remains.
- A designed recess or slit whose depth is within `max_step` needs an explicit boundary: a `recess` / `preserve` tag, a different `surface_id` (for example upper and lower eyelid), or a barrier pair. Deeper designed edges are kept automatically.
- The working grid is chosen per selection from the smallest piece in it. One tiny piece inside a huge selection makes that whole selection fine. Per-area adaptive grids are not built.
- Wedges are supported only for the `+y` face and only with rotations about Y in 90° steps. Corner cuts and other rotations are kept as occluders (never filled, never anchor filler) and listed in `notes`.
- A sloped neighbour's edge height is sampled at the next column's centre (half-column error on wedges).
- Two layers over the same columns overlap as geometry. Data never accumulates, but the union is not merged.
- Adjacent filler boxes keep their shared inner faces (no greedy merge yet).
