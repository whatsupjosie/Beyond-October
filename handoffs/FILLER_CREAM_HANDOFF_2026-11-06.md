# Filler Cream — session handoff (2026-11-06)

Repo: whatsupjosie/Beyond-October, branch `claude-work`. This handoff's own commit is the newest Filler Cream commit on that branch (a file can't contain its own commit's SHA; `git log -1 -- handoffs/FILLER_CREAM_HANDOFF_2026-11-06.md` shows it).

## Reproduce exactly

- **Base commit** (claude-work before this session): `295b556e27fe7436ac371d35cc3a141b9fb82a98`. Filler Cream needs these unchanged files from it: `modules/__init__.py`, `modules/voxel_studio.py`, `modules/voxel_set_contract.py`, `modules/voxel_block_kit.py`. The ZIP includes them (unchanged) so it runs on its own. Checked: a clean folder with only the ZIP's files passes all Filler Cream tests.
- **Versions used:** Python 3.13.18, numpy 2.5.3, pytest 9.1.1, matplotlib 3.11.2 (view tool only).
- **Exact test command** (PowerShell 5, repo root or the unzipped folder):

      python -m pytest -p no:cacheprovider tests\test_filler_cream.py -q

  Expected: 23 passed. In the repo, add the existing voxel tests to check nothing broke:

      python -m pytest -p no:cacheprovider tests\test_filler_cream.py tests\test_pubblock_voxel_block_kit.py tests\test_voxel_block_preview.py tests\test_voxel_set_contract.py -q

  Expected: 35 passed.

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
- `tests/test_filler_cream.py`: 21 focused test functions (23 test cases)
- `tools/filler_cream_view.py`: before/after GLBs and a side-profile PNG
- `docs/FILLER_CREAM.md`: usage, the rule, measured limits
- `docs/FILLER_CREAM_APPLICATOR_UI_SPEC.md`: applicator UI proposal (not built, awaiting Josie's review)
- `docs/filler_cream/`: `fixture_before.glb`, `fixture_after.glb`, `before_after_profile.png`
- this handoff

## Implemented behaviour

`compute_filler(pieces, FillerSelection)` works on one exposed face direction. Each column fits a weighted best-fit plane to the heights it can reach without crossing a mark, within half the fidelity span. The plane keeps its slope but is lifted to rest on the nearby outer block points; each point's pull fades with distance, so the surface is continuous with no lip at open ends. Cream fills up to it, capped at the highest nearby block. Cracks no wider than `max_gap` (2/64 block) fill from the pieces' base; wider gaps are openings and stay empty. `FillerCreamLayers` applies, replaces, removes and serialises layers; cream is computed from the original pieces only, so there's no buildup. `bake_with_filler` bakes through the existing `VoxelBaker` and `pack_glb`; with no cream it returns the original bytes exactly.

## Integration status

Completed: reads `voxel_studio.VoxelObject` and canonical voxel sets (block kit floors); output goes through VoxelStudio's own cube table, normals, baker and GLB packer; block size comes from the contract.

Prepared, not done: no `main.py` route, no change to `VoxelStudio`, no applicator brush UI, no renderer hookup, no sanding.

## Checks executed (this sandbox: Python 3.13, numpy 2.5.3, pytest 9.1.1; not GitHub, not Windows)

- `tests/test_filler_cream.py`: 23 passed. Together with the existing voxel tests (block kit, preview, contract): 35 passed, so no existing voxel test broke.
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

## Observed in existing code (not changed)

- `voxel_studio.pack_glb` pads the GLB JSON chunk with NUL bytes; glTF requires spaces. Strict loaders may reject these files.
- `pytest.ini` sets `asyncio_mode`; pytest-asyncio isn't installed in this sandbox, so pytest warns. Harmless here.

## Limitations

See `docs/FILLER_CREAM.md` → Limits:
- small steps remain from flat-top filler boxes (sanding finishes them);
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
6. Later: cream wrapping across faces, sanding.

## How to run (PowerShell 5, repo root)

    python -m pytest -p no:cacheprovider tests\test_filler_cream.py -q
    python tools\filler_cream_view.py
