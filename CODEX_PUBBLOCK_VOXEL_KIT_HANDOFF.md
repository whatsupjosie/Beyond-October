# PubCast PubBlock Voxel Kit Handoff

Date: 2026-06-14
Scope: construction copy only, non-destructive.

## Added / hardened

- `modules/voxel_set_contract.py`
  - Added PubBlock measurement constants.
  - 1 PubBlock = 10 inches = 0.254 meters.
  - Half block = 5 inches, quarter block = 2.5 inches.
  - Added conversion helpers for inches <-> PubBlock units.
  - Voxel sets now carry measurement metadata.

- `modules/voxel_block_kit.py`
  - Added reusable block-kit builders for PubWorld stage/set construction.
  - Supports floors, walls, backdrop panels, doorway walls, and hidden guide grids.
  - Guide-grid voxels are marked `visible_to_program=false`, `guide_only=true`, and `collision=false`.
  - Grid intersections are deduplicated so voxel validation stays clean.

- `tests/test_pubblock_voxel_block_kit.py`
  - Covers base-10 measurement rules.
  - Confirms 6-foot rounded avatar height is 7 full PubBlocks.
  - Confirms quarter-block precision for fine work.
  - Confirms stage floor and hidden guides validate cleanly.
  - Confirms backdrop and doorway support for the 3D stage concept.

## Backups made before edits

- `modules/voxel_set_contract.py.pre_pubblocks_20260614.bak`
- `tests/test_voxel_set_contract.py.pre_pubblocks_20260614.bak`

## Validation

- `python -m pytest tests\test_voxel_set_contract.py tests\test_pubblock_voxel_block_kit.py -q` -> 8 passed
- `python -m pytest tests\test_glb_motion_retargeter.py tests\test_program_audio_contract.py tests\test_menu_coverage_and_safe_console.py tests\test_pub_manager_recovery.py tests\test_beefed_up_recovery_wiring.py tests\test_voxel_set_contract.py tests\test_pubblock_voxel_block_kit.py -q` -> 27 passed
- `node tests\test_avatar_glb_motion_consumer_node.js` -> passed
- `node tests\test_program_audio_runtime_node.js` -> passed

## Notes

These files are ready to be included in the eventual Big Zip build pass, but they are not wired into a final editor UI yet. They give the build a stable measurement contract and a tested voxel construction kit for PubWorld's 3D studio stage.
