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

## The rule

On one exposed face at a time, each column of the selection asks: which nearby columns can I reach without crossing a marked edge, within half the fidelity span? It fits a best-fit plane to their heights. The weighting falls off with distance, so neighbouring fits blend with no creases. Cream fills from the block up to that plane, never higher than the highest nearby block. Where the plane runs below a block's corner, the corner stays: removing it is sanding.

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

## Limits (measured, not guessed)

- Fill only. On a staircase or a dip, the lower half of each step fills and about half the step remains at the riser. On bulges (top of a nose bridge, a kneecap) the best fit runs under the block corners, so their steps stay until a sanding tool exists. On the curve test, the surface came about 20% closer to the true curve, and the largest remaining step went from 1 to 0.78–1.0 fine units.
- Filler boxes have flat tops at the working grid: a fine staircase, about 1 mm here.
- One face direction per call. Cream does not wrap from a top face onto a side face.
- Barriers stop direct bridging between two pieces; a path around through a third piece of the same surface still connects them. Use different surface names when parts must never meet (eyelids).
- The working grid follows the smallest piece and finest fidelity in the selection; it is not adaptive per area.
- Wedges: `+y` face only, rotations about Y in 90° steps. Corner cuts are occluders (never filled).
- Overlapping layers overlap as geometry; data never accumulates. Adjacent filler boxes keep shared inner faces.
