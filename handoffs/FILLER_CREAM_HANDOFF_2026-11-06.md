# Filler Cream — session handoff (2026-11-06)

Repo: whatsupjosie/Beyond-October, branch `claude-work`. This handoff's own commit is the newest Filler Cream commit on that branch (a file can't contain its own commit's SHA; `git log -1 -- handoffs/FILLER_CREAM_HANDOFF_2026-11-06.md` shows it).

## Reproduce exactly

- **Base commit** (claude-work before this session): `295b556e27fe7436ac371d35cc3a141b9fb82a98`. Filler Cream needs these unchanged files from it: `modules/__init__.py`, `modules/voxel_studio.py`, `modules/voxel_set_contract.py`, `modules/voxel_block_kit.py`, `modules/voxel_llm_adapter.py`. The ZIP includes them (unchanged) so it runs on its own. Checked: a clean folder with only the ZIP's files passes all Filler Cream tests.
- **Versions used:** Python 3.13.18, numpy 2.5.3, pytest 9.1.1, matplotlib 3.11.2 (view tool only). trimesh (latest from pip, 2026-11-06) was used once, outside the test suite, as an independent check that the textured GLB loads with its UVs.
- **Exact test command** (PowerShell 5, repo root or the unzipped folder):

      python -m pytest -p no:cacheprovider tests\test_filler_cream.py -q

  Expected: 38 passed. In the repo, add the existing voxel tests to check nothing broke:

      python -m pytest -p no:cacheprovider tests\test_filler_cream.py tests\test_pubblock_voxel_block_kit.py tests\test_voxel_block_preview.py tests\test_voxel_set_contract.py -q

  Expected: 50 passed.

## What Filler Cream is (Josie's design, settled in this session)

- The voxel blueprint is the carving. It describes the real object, or the stylised version wanted. Voxels are always an approximation of it.
- Filler Cream is like wood filler (sawdust and glue) spread into a scar and wiped flush with the surrounding surface. It fills the low spots between neighbouring surface voxels up to the surface set by the outer points of the voxels, never past it, and never into the hollow interior.
- Everything is smoothed unless the blueprint marks it as designed: a keep tag (`preserve`, `recess`, `protrusion`, `edge`, `opening`), a different surface name (skin vs nail, upper vs lower eyelid), or a barrier pair. Step size alone never decides.
- Smoothing is a chain of short local best fits. A fidelity gauge sets how far one fit reaches: few long fits on a potbelly, many short fits on a nose.
- Fidelity is tied to real size through the existing 10 in PubBlock: very_high 3/64 block (about 12 mm), high 1/8 (32 mm), medium 1/4 (64 mm, the default), low 1/2 (127 mm), very_low 1 block (254 mm), or any span in mm. Blueprint parts carry a fidelity; the applicator overrides it for one application.
- The finishing order is carve (voxels), cream (fill flush), sand (separate tool, removes material to fine-tune angles and silhouette, not built), then paint and polish (later).
- Units stay the existing system: the 10 in block from `modules/voxel_set_contract.py`, 1/64 = 3.97 mm. Read from the contract, never copied.

## Files (all new; no existing file edited)

- `modules/filler_cream.py`: core operation, fidelity gauge, layer store, adapters, GLB output
- `modules/filler_cream_fixture.py`: 1/64 fixtures (stepped strip with protrusion, recess, opening and crack; fingertip; curve)
- `tests/test_filler_cream.py`: 27 focused test functions (38 test cases)
- `tools/filler_cream_view.py`: before/after GLBs and a side-profile PNG
- `docs/FILLER_CREAM.md`: usage, the rule, measured limits
- `docs/FILLER_CREAM_APPLICATOR_UI_SPEC.md`: applicator UI proposal (not built, awaiting Josie's review)
- `docs/SANDING_TOOL_DESIGN.md`: sanding/grinding tool and bit kit proposal (not built, awaiting Josie's review)
- `docs/filler_cream/`: `fixture_before.glb`, `fixture_after.glb`, `fixture_after_textured.glb` (with UVs and a paintable material), `before_after_profile.png`
- this handoff

## End-to-end object pipeline (Josie, 2026-11-06)

1. **Generate:** prompt the voxel object generator ("kitchen table style chair") and get a general voxel object. The existing entry point is `modules/voxel_llm_adapter.py` (cloud providers with a local fallback; returns a block list). Not yet checked: whether its block list goes straight into `pieces_from_voxel_set`.
2. **Refine:** a more detailed prompt, and/or hand edits.
3. **Finish:** Filler Cream (fill flush), then the Dremel for custom touches: carvings, the family name, pierced patterns, cut-through. All of these are layers over the untouched base, which can be saved as a reusable variant.
4. **Bake to one mesh.** Voxels are for authoring only; they're too heavy to keep at runtime. Copies of a variant reuse one baked mesh (instancing).
5. **Paint the mesh:** colour, image, texture or surface cover.

Gaps this pipeline exposes:
- **Texture coordinates: done.** `bake_textured(obj, layers)` bakes blocks plus cream into one mesh with box-projected UVs (one texture repeat per block, so wood grain and tile stay the same real size on every object) and a neutral "paintable" material. It's spec-clean (JSON padded with spaces) and verified loading in trimesh. `voxel_studio.pack_glb` is unchanged.
- **Generator to Filler Cream: done.** `voxel_llm_adapter` writes `position: [x, y, z]` with `scale`, which the voxel contract rejects. `pieces_from_generated_blocks(blocks)` reads that format directly; each block's material becomes its surface name, so wood and metal never blend. Found while testing: the offline fallback generator returned a generic "Open Space" for "kitchen table style chair", because it doesn't know chairs; the cloud generators were not tested here.
- **Paint vs re-bake (not built):** if a carving changes after painting, the mesh changes. Paint should be tied to the bake it was made on and flagged stale (the same contract as cream layers), not silently misplaced.
- **Carved text (not built):** the family name needs text turned into a stamp (font outlines). This is Dremel decision 6.
- **Box-projected UVs are a start, not an unwrap:** fine for wood grain, tile, stone and solid paint; a painted face or a logo across a curved surface will want a proper unwrap later.
- **Crisp edges** must survive the bake (see the sanding design).

## Implemented behaviour

`compute_filler(pieces, FillerSelection)` works on one exposed face direction. Each column fits a weighted best-fit plane to the heights it can reach without crossing a mark, within half the fidelity span. The plane keeps its slope but is lifted to rest on the nearby outer block points; each point's pull fades with distance, so the surface is continuous with no lip at open ends. Cream fills up to it, capped at the highest nearby block. Cracks no wider than `max_gap` (2/64 block) fill from the pieces' base; wider gaps are openings and stay empty. `FillerCreamLayers` applies, replaces, removes and serialises layers; cream is computed from the original pieces only, so there's no buildup. `bake_with_filler` bakes through the existing `VoxelBaker` and `pack_glb`; with no cream it returns the original bytes exactly.

## Integration status

Completed: reads `voxel_studio.VoxelObject` and canonical voxel sets (block kit floors); output goes through VoxelStudio's own cube table, normals, baker and GLB packer; block size comes from the contract.

Prepared, not done: no `main.py` route, no change to `VoxelStudio`, no applicator brush UI, no renderer hookup, no sanding.

## Checks executed (this sandbox: Python 3.13, numpy 2.5.3, pytest 9.1.1; not GitHub, not Windows)

- `tests/test_filler_cream.py`: 38 passed. Together with the existing voxel tests (block kit, preview, contract): 50 passed, so no existing voxel test broke.
- The textured GLB was loaded by trimesh (an independent reader): 16,056 vertices and 16,056 UV rows.
- Wedge orientation checked against `build_primitive_geometry` for all four Y rotations.
- View tool run and the PNG inspected by eye.

What the tests prove:
- Steps smooth into an even ramp with no lip at the open end, never above nearby blocks.
- An unmarked protrusion blends at its base as a continuous ramp and keeps its top; a marked one is untouched.
- The marked recess and the opening stay intact; unmarked, the recess fills.
- Skin, cuticle, nail and nail edge stay distinct when marked, and blend when unmarked.
- Fidelity controls reach, and the applicator overrides the blueprint.
- A designed wedge slope gains nothing.
- Regions far apart don't affect each other.
- Barriers and surface names block bridging, and nothing outside the selection changes.
- Removing the cream restores the original bake byte for byte, and redoing it is identical with no buildup.
- A 20 ft floor runs on a 1/8-block grid and stays level; a fractional crack in it fills level.
- The curve test (high fidelity): 48% closer to the true curve (48.8 → 25.5), largest step 1 → 0.55 fine units, never more than 0.11 fine units above the curve.

## Self-review (end of session) — found and fixed

- Bug: the candidate shortcut sized its search by the fidelity of the lower piece at a step. With mixed per-piece fidelity it skipped columns that should get cream. Proven: the old search was wrong in 2 of 12 random mixed-fidelity scenes (29 columns skipped). Fixed with a search radius proven conservative (2 × (largest radius + half a column)). New test: on random scenes, the shortcut equals fitting every column.
- Gap: only the top face (+y) had been tested. New test: the stepped strip rotated onto +x, -y and -z gives the same cream count and volume.
- Measured speed (see docs Limits): too slow for a live brush at medium fidelity on face-sized patches. Not fixed; the speed-up path is noted.

## Outside review (2026-11-06 evening): answers

1. **Outermost surface per column.** Confirmed bug: a separate slab overhead dropped cream from 64 cells to 0. Fixed (only touching pieces cover a surface); test added. Still open by design: two selected surfaces stacked in one column. See the docs, "Surface isolation", and question A below.
2. **Regeneration.** Implemented: layers save their settings and a source fingerprint; stale detection, regenerate and refresh are tested. Not yet automatic: the VoxelStudio hookup must call `refresh` before baking.
3. **"Flush".** Defined in the docs, "What flush means": five guarantees, plus the one approximation (the contour between voxel points), with measured numbers.
4. **Finished curved surface.** Not built. Plan below.
5. **Reproducibility.** Base commit, versions and exact commands are now in this file; the ZIP carries the four base files.

### Plan for a finished curved surface (not built)

The boxes are an intermediate result. The finished surface should come from one volume: blocks plus cream from every face direction the region exposes (up to six calls, combined by taking the larger), with a single continuous mesh extracted from it. The repo already has marching cubes (`run5_pubworld_camera/marching_cubes.py`) to adapt, or surface nets for crisper taped edges. That one mesh wraps a cheek, nose or fingertip in all directions at once, with no seams between face directions and no flat-top stair. Taped edges must stay sharp through extraction; that needs feature-preserving extraction (to be tested on the fingertip).

How much depends on sanding: removing the box stair and the seams between face directions is the job of surface extraction, not sanding. Sanding is still needed for (a) the slight overshoot on convex areas, and (b) artistic sharpening or softening.

### Questions for Josie

A. **Stacked surfaces in one selection** (floor under a ceiling slab, arm in front of torso, lower lip under upper lip). Options: (1) keep one surface per column and apply cream to each part separately, which works today; or (2) teach the engine to keep every exposed surface in a column as its own layer, which is the real fix. Recommendation: (2), before the face study, since lips, eyelids and fingers stack constantly.
B. **Stale cream after a voxel edit:** regenerate automatically on bake, or show it as stale and let the user choose?
C. **Finished surface:** approve the single-volume surface plan as the next engine block after the VoxelStudio hookup?

## Completion requirements: Filler Cream is NOT complete until both land

1. **Continuous surface extraction.** One closed mesh from blocks plus cream across every face direction, keeping sharp edges where taped or crisp-cut. This, not sanding, removes the flat-top box stair and the seams between face directions. Until then, output is boxes.
2. **Stacked-surface support.** Every exposed surface in a column kept as its own layer (floor under a ceiling slab, an arm in front of the torso, lips, eyelids, fingers), so one selection can cream both. Until then, apply cream part by part.

## Outside review 3 (2026-11-06, 20:09): fixed

- The reviewer ran the closeout2 package independently: 28/28 passed.
- **`pack_glb_uv` accepted malformed arrays.** A (3, 2) position array was written as VEC3 data. It now requires positions and normals shaped (N, 3), UVs (N, 2) and triangle indices (M, 3); finite numbers only; whole-number indices within range. Ten malformed-input cases are tested.
- The ZIP now includes two existing voxel test files (block kit, contract), so `python -m pytest -p no:cacheprovider tests -q` in the unzipped folder runs Filler Cream plus those two. `tests/test_voxel_block_preview.py` depends on a chain of other repo modules, so it runs only in the repo (the 50-test command above).

## Outside review 2 (2026-11-06, 20:03): fixed

- **Protected slab over a small air gap was penetrated.** Reproduced: cream reached 9.68 inside a slab whose base is at 9. Fixed: in each column, cream is capped at the underside of any piece hanging over the surface (protected, selected or not). Regression test included, plus the same check for crack cream under a lid. `ENGINE_VERSION` bumped, so cream saved before this fix reports stale.
- **Stale layers could enter a bake after a failed refresh.** Fixed: `bake_with_filler` and `bake_textured` now need the current pieces and refuse stale layers (only an explicit `unchecked=True` skips the check), and `FillerCreamLayers.bake_layers(pieces)` refuses too. Tested, including the failed-refresh case.
- **Docs that gave stair removal to sanding** are corrected. The stair goes with surface extraction; sanding is for reshaping by choice and convex overshoot.

## Closing review (end of session): fixed

- **Saved cream ignored rule changes.** `ENGINE_VERSION` is now part of every layer's fingerprint, so cream saved under an older rule reports stale. Bump it whenever the cream rule changes. Tested.
- **The GLB reader could drop geometry.** It now refuses any GLB with more than one mesh or primitive instead of reading only the first. Today's baker always writes one, so nothing was lost.
- **The textured writer could emit an invalid file.** It now raises on an empty mesh, or when vertex, normal and UV counts or indices disagree. Tested.
- **The out-of-date check accepted duplicate piece ids** silently. It now raises, like `compute_filler`. Tested.

## Observed in existing code (not changed)

- `VoxelBaker`'s docstring says it writes one mesh node per group; the code actually merges everything into one mesh with one primitive.

- `voxel_studio.pack_glb` pads the GLB JSON chunk with NUL bytes; glTF requires spaces. Strict loaders may reject these files.
- `pytest.ini` sets `asyncio_mode`; pytest-asyncio isn't installed in this sandbox, so pytest warns. Harmless here.

## Limitations

See `docs/FILLER_CREAM.md` → Limits:
- small steps remain from flat-top filler boxes (removed by continuous surface extraction, a completion requirement; not by sanding);
- slight overshoot between corners on convex areas, bounded by fidelity;
- one face direction per call (no wrapping from a top face onto a side face);
- corner-cut pieces are skipped;
- the working grid is not adaptive per area.

## Next steps, in order

1. Independent check by a reviewer that didn't write it: hunt for anything that breaks Josie's rules, and run it.
2. Smallest wiring step: in `VoxelStudio.bake_object` (`modules/voxel_studio.py`), load `filler/<object_id>.json` when present and bake with `bake_with_filler`. About ten lines plus one test.
3. Corner-cut pieces take cream instead of being skipped.
4. The face study at 1/64: brow, eye sockets, nose, cheeks, lips and chin. Raw, neutral material and simple paint, from front, three-quarter and profile.
5. Applicator UI: proposal in `docs/FILLER_CREAM_APPLICATOR_UI_SPEC.md` (for Primp and set building), awaiting Josie's six decisions listed at its end. It needs the engine speed-up before a live brush.
6. Sanding tool ("the Dremel" with a bit kit): design proposal in `docs/SANDING_TOOL_DESIGN.md`, awaiting Josie's five decisions; build voxel phase first.
7. Later: cream wrapping across faces.

## How to run (PowerShell 5, repo root)

    python -m pytest -p no:cacheprovider tests\test_filler_cream.py -q
    python tools\filler_cream_view.py
