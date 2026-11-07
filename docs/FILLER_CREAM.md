# Filler Cream — usage and rules

Code: `modules/filler_cream.py`. Proof fixtures: `modules/filler_cream_fixture.py`. Tests: `tests/test_filler_cream.py`. View tool: `tools/filler_cream_view.py`.

## Design rule (Josie, 2026-11-06)

The blueprint describes the real object, or the stylised version you want. Voxels are always an approximation of it. So every voxel step is smoothed unless the blueprint marks it as designed. Step size alone never protects anything.

Ways to mark a designed edge, dip or opening:
- a keep tag on the piece: `preserve`, `recess`, `protrusion`, `edge`, `opening`
- a different surface name (`surface_id`), for example `skin` and `nail`, or `lid_upper` and `lid_lower`
- a barrier pair in the selection

## Units (from the existing system)

The size comes from `modules/voxel_set_contract.py`: one PubBlock is 10 in (0.254 m). Filler Cream works in 1/64 of a block, 3.96875 mm, and reads the block size from the contract, never from its own copy.

## Fidelity gauge

How far one best fit reaches, tied to real size through the block:

| Stop | Span | About | Use |
|---|---|---|---|
| very_high | 3/64 block | 12 mm | lips, nostrils, nail edges |
| high | 1/8 block | 32 mm | nose, eyes, fingers |
| medium (default) | 1/4 block | 64 mm | cheeks, jaw, knees |
| low | 1/2 block | 127 mm | belly, thighs, back |
| very_low | 1 block | 254 mm | floors, walls |

Any span in millimetres also works. Each blueprint part can carry a fidelity (`fidelity` in annotations or block metadata); the applicator (`FillerSelection.fidelity`) overrides it for one application. These values are starting points to judge by eye.

## The rule (outer points, like wood filler wiped flush)

On one exposed face at a time, each column of the selection asks: which nearby columns can I reach without crossing a marked edge, within half the fidelity span? It fits a best-fit plane to their heights, weighted so neighbouring fits blend with no creases. Then it lifts that plane, keeping its slope, until it rests on the outermost block points nearby. Each point's pull fades with distance, so the surface stays continuous and the open end of a run gets no lip. Cream fills from the block up to that plane, never higher than the highest nearby block. The voxel points set the surface; the cream is wiped flush with them. Sanding is a separate tool (not built) for making an angle finer.

Cracks: an empty gap no wider than `max_gap` (default 2/64 block) between two connected pieces fills from the pieces' base up to a straight line between them. Wider gaps are openings and stay empty.

Locality: a fit only sees columns within its reach that it can get to without crossing a mark. The nose tip cannot affect the eye corner. A bigger selection means more local fits, not wider ones.

No buildup: cream is computed from the original pieces only. Re-applying replaces the layer; removing it restores the original exactly.

## Run it (PowerShell 5, from the repo root)

    python -m pytest -p no:cacheprovider tests\test_filler_cream.py -q
    python tools\filler_cream_view.py

## Call it from Python

    from modules.filler_cream import FillerSelection, FillerCreamLayers, pieces_from_voxel_object, bake_with_filler
    pieces, notes = pieces_from_voxel_object(obj, annotations={"NAIL1": {"surface_id": "nail", "fidelity": "very_high"}})
    layers = FillerCreamLayers()
    layers.apply("hand_left", pieces, FillerSelection(frozenset({"S1", "S2", "NAIL1"}), fidelity="high"))
    glb_bytes = bake_with_filler(obj, layers.layers())
    layers.remove("hand_left")

For canonical voxel sets use `pieces_from_voxel_set(voxel_set)`; block metadata `surface_id` (or `part`), `filler_tags`, `filler: "preserve"` and `fidelity` carry the marks.

## What "flush" means: guaranteed vs approximate

Guaranteed by construction and covered by tests:
1. **Only adds.** A cream cell starts at its column's existing block surface (or, for a crack, the higher of the two pieces' bases) and ends above it.
2. **Bounded.** Cream never rises above the highest block surface inside that column's own fit window (radius = half the fidelity span plus half a column), reached without crossing a mark. Crack cream never rises above the higher of its two edges.
3. **Marks hold.** No fit window crosses a keep-tagged piece, a different surface name, a barrier pair, an unselected piece or an empty column.
4. **Local.** A cell depends only on pieces inside its window (plus a crack's two edges, at most `max_gap` apart).
5. **Reversible and deterministic.** It's computed from the original pieces only, and removing it restores the original bake byte for byte.

Approximate, not guaranteed: **following the intended contour between voxel points.** The blueprint stores only voxels; it holds no curve between them. "Flush" is implemented as a local best-fit plane, lifted to rest on the nearby outer block points (each point's pull fades with distance). Between points it can sit slightly above where a designer pictured the curve on convex areas (measured: up to 0.11 fine units at high fidelity on the test curve, never past guarantee 2), and slightly below on concave areas. The flat-topped output boxes add a fine stair of at most (local slope × one grid column).

## Surface isolation (one surface per column)

Each call works on one face direction and keeps one surface per column.
- **Fixed:** an unselected piece covers a selected surface only where it touches it (its base at or below that surface). A ceiling, shelf or slab separated by air no longer blocks the floor beneath. On empty columns, an unselected piece only matters if it starts at or below the highest selected surface.
- **Still true:** inside one selection, if two selected surfaces face the same way and stack in the same column (a floor and the top of a ceiling slab, an arm held in front of the torso, the lower lip under the upper lip seen from above), only the outermost is creamed there. Today the way around it is to apply cream to each part as its own selection. Faces pointing different ways are already separate calls; a lip's underside faces down and the lower lip's top faces up.

## Regeneration and invalidation contract

- A saved layer (v2) stores its full application settings (`selection`) and a `source_fingerprint`: a hash of every piece that could influence it (the selection's footprint grown by `max_gap`), plus the block size.
- `layer_is_stale(layer, pieces)` is true when any of those pieces changed (moved, resized, retagged, renamed part, new fidelity, removed). Editing pieces outside that footprint leaves the layer fresh.
- `regenerate(layer, pieces)` recomputes from the saved settings. `FillerCreamLayers.stale(pieces)` lists stale layers; `refresh(pieces)` regenerates them. A layer whose selected pieces no longer exist is kept and reported as "needs attention", never guessed.
- v1 layers (no saved settings) are always reported stale and can't be regenerated automatically.
- Not automatic yet: nothing calls `refresh` when voxels are edited. The VoxelStudio hookup should call it before every bake.

## Limits (measured, not guessed)

- On the curve test at high fidelity, the surface came 48% closer to the true curve (error 48.8 → 25.5), the largest step went from 1 to 0.55 fine units, and the cream never rose more than 0.11 fine units (under half a millimetre) above the true curve. Small steps remain because filler boxes have flat tops at the working grid; light sanding is the finishing step.
- On convex areas the lifted plane can sit slightly above the true surface between block corners. That's bounded by the fidelity span and capped at the highest nearby block. Use higher fidelity on tight curves.
- An unmarked big step (16 fine units in the fixture) blends into a steep ramp: monotone, with at most 2.4 per column. Mark it if it is a designed edge.
- One face direction per call. Cream does not wrap from a top face onto a side face.
- Barriers stop direct bridging between two pieces; a path around through a third piece of the same surface still connects them. Use different surface names for parts that must never meet (eyelids).
- The working grid follows the smallest piece and finest fidelity in the selection; it is not adaptive per area.
- Wedges: `+y` face only, rotations about Y in 90° steps. Corner cuts are occluders (never filled).
- Overlapping layers overlap as geometry; data never accumulates. Adjacent filler boxes keep shared inner faces.
- Speed (measured, plain Python): a 128 × 128 column patch at 1/64 (about 51 cm square, wavy) takes 2.7 s at very_high, 8.4 s at high, and 22.7 s at medium. Fine for baking, too slow for a live brush. Speed-up path: compute the fits with array maths (numpy moment sums over the grid) where no marks cut the window.
- Cracks use a straight line between their two edges, not the outer-points lift (they're at most 2/64 block wide).
- A cube at a non-90° rotation becomes an occluder sized by its unrotated box.
