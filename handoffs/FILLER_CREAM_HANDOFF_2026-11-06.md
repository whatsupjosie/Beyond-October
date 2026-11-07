# Filler Cream — session handoff (2026-11-06)

Branch: `claude-work` on whatsupjosie/Beyond-October. Code commit: `1bf605e5d035f05f536d78076b6ef7aca3e8725d`. This handoff is the next commit on the same branch.

## Changed files (all new; no existing file was edited)

- `modules/filler_cream.py` — core operation, layer store, adapters, GLB output
- `modules/filler_cream_fixture.py` — 1/64 proof fixture as a real VoxelObject
- `tests/test_filler_cream.py` — 13 focused tests
- `tools/filler_cream_view.py` — writes before/after GLBs and a side-profile PNG
- `docs/FILLER_CREAM.md` — usage, the interpolation rule, limits
- `docs/filler_cream/` — fixture_before.glb, fixture_after.glb, before_after_profile.png
- `handoffs/FILLER_CREAM_HANDOFF_2026-11-06.md` — this file

## What I found and reused

- Units: `modules/voxel_set_contract.py` (10 in PubBlock; subdivisions 1 / 2 / 4 only). 1/64 does not exist in the contract. I did not add it; it is your call (one line in `PUB_BLOCK_SUBDIVISIONS`, and existing tests that list subdivisions would need updating).
- Shapes, triangular cuts and the mesh pipeline: `modules/voxel_studio.py` — cube / wedge / corner_outer / corner_inner, `_shape_verts_faces`, `_compute_normals`, `VoxelBaker`, `pack_glb`. Filler geometry is built from the same cube table and normals routine and baked through `VoxelBaker` + `pack_glb`.
- Block-kit floors: `modules/voxel_block_kit.py` (`stage_floor`, `make_voxel_set`) feed the large-floor test through the canonical contract.
- Hollowing: `modules/wired/pubcast_voxel_hollow_patch.py` is a patch script, not a runtime API. Filler treats each piece as a surface shell piece and never fills below the shell base.

## Implemented behaviour

One callable operation, `compute_filler(pieces, FillerSelection)`, plus `FillerCreamLayers` (apply / remove / regenerate) and `bake_with_filler(voxel_object, layers)`. Rule: half-run linear ramps on the lower piece toward an eligible higher neighbour, plus crack fill between eligible pieces, both bounded by the two neighbours' surfaces. Full rule and limits in `docs/FILLER_CREAM.md`.

## Integration status

Completed:
- Reads `voxel_studio.VoxelObject` directly (`pieces_from_voxel_object`) and canonical voxel sets (`pieces_from_voxel_set`).
- Output goes through the existing VoxelStudio baker and GLB packer. With no filler the bake is byte-identical to `VoxelBaker().bake(obj)`.

Prepared, not done:
- No HTTP route in `main.py`, no change to `VoxelStudio`, no brush UI, no three.js / Rust renderer hookup.
- Connection point: `VoxelStudio.bake_object` (modules/voxel_studio.py) — store `FillerCreamLayers.to_dict()` beside the object's source JSON and call `bake_with_filler` instead of `VoxelBaker.bake` when layers exist.

## Checks actually executed (this sandbox, Python 3.13, numpy 2.5.3, pytest 9.1.1)

- `python -m pytest -p no:cacheprovider tests/test_filler_cream.py -q` → 13 passed.
- Existing voxel tests, unchanged: `tests/test_pubblock_voxel_block_kit.py tests/test_voxel_block_preview.py tests/test_voxel_set_contract.py` → 12 passed.
- Wedge orientation: the model's wedge top matched `build_primitive_geometry` vertices for rotations 0 / 90 / 180 / 270 about Y (also a test).
- `python tools/filler_cream_view.py` → 200 filler cells, grid 1 fine unit, 256 cubic fine units; PNG inspected by eye.
- Not run: the full repo suite, Windows, any GitHub Actions.

What the tests prove: eligible steps get filler that never goes above the higher neighbour; the 16-unit protrusion edge, the tagged recess and the 12-unit opening get none; without the recess tag the pit would fill (so the tag is doing the work); the one-unit crack fills from the shell base; changing strip two leaves strip one's filler identical, and moving P0 changes only the P0/P1 fill; barriers and different surface ids stop bridging; filler stays inside the selection; re-applying three times gives the same fingerprint and volume with one layer; removing it restores the original bake byte for byte; the 24 × 24 block (20 ft) floor runs on a 1/8-block grid, not 1/64, and a level floor gains nothing.

## Observed in existing code (not changed)

- `voxel_studio.pack_glb` pads the GLB JSON chunk with NUL bytes; glTF requires spaces. Strict loaders may reject these files. My reader tolerates it.
- `pytest.ini` sets `asyncio_mode`; pytest-asyncio was not installed here, so pytest warns. Harmless for these tests.

## Limitations

See `docs/FILLER_CREAM.md` → Limits. Biggest ones: one face orientation per call; flat-top filler leaves a fine staircase (sanding not built); recesses or slits shallower than `max_step` need an explicit tag, surface id or barrier.

## Smallest remaining step

Wire the prepared connection point: in `VoxelStudio.bake_object`, load `filler/<object_id>.json` if present and bake with `bake_with_filler`. About ten lines in `modules/voxel_studio.py`, plus one test.
