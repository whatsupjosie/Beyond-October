# PubCast Backend + Frontend Voxel Preview Wiring Handoff

Date: 2026-06-17
Scope: Big Zip construction build only. Non-destructive copy work.

## Purpose

Continue wiring PubCast with both backend and frontend support for systems that are already ready enough to connect safely.

This pass adds dry-run voxel preview support. It does not create map rooms, consoles, visible UI, saved assets, or persistent scene changes.

## Backend Added

- New side-effect-free module: modules/voxel_block_preview.py
- New backend route: GET /api/voxel/block-kit/preview/capabilities
- New backend route: POST /api/voxel/block-kit/preview
- Pub Manager safe action: oxel.block_kit_preview
- Menu metadata entries under Scene / Room and Help / Recovery only.

Supported preview kinds:

- stage_floor
- lat_wall
- ackdrop_panel
- guide_grid
- doorway_wall
- ectangular_prism
- isual_patch
- daptive_extension

Backend guarantees:

- Read-only preview.
- No asset saving.
- No map-room creation.
- No console creation.
- Canonical voxel-set normalization.
- PubBlock measurement rules preserved.

## Frontend Added

- New quiet runtime bridge: static/voxel_block_preview_client.js
- Loaded on:
  - static/control.html
  - static/stage.html
  - static/stage_3d.html
  - static/avatar_walk_test.html

The frontend bridge exposes:

- window.PubcastVoxelBlockPreview.capabilities()
- window.PubcastVoxelBlockPreview.preview(kind, params)
- window.PubcastVoxelBlockPreview.status()

It also dispatches browser events for future tools:

- pubcast:voxel-block-preview-capabilities
- pubcast:voxel-block-preview

No visual controls were added.

## Files Created

- modules/voxel_block_preview.py
- 	ests/test_voxel_block_preview.py
- static/voxel_block_preview_client.js
- 	ests/test_voxel_block_preview_client_node.js

## Files Updated

- main.py
- modules/pub_manager_recovery.py
- config/menu_coverage.json
- 	ests/test_ready_wiring_routes.py
- 	ests/test_beefed_up_recovery_wiring.py
- 	ests/test_menu_coverage_and_safe_console.py
- 	ests/test_pub_manager_recovery.py
- static/control.html
- static/stage.html
- static/stage_3d.html
- static/avatar_walk_test.html

## Backups

Backend wiring backup:

$backupBackend

Frontend wiring backup:

$backupFrontend

## Verification

Passed new module tests:

`powershell
pytest -p no:cacheprovider tests\test_voxel_block_preview.py -q
# 4 passed
`

Passed focused backend regression:

`powershell
pytest -p no:cacheprovider tests\test_voxel_block_preview.py tests\test_ready_wiring_routes.py tests\test_beefed_up_recovery_wiring.py tests\test_menu_coverage_and_safe_console.py tests\test_pub_manager_recovery.py tests\test_voxel_set_contract.py tests\test_pubblock_voxel_block_kit.py tests\test_visual_patch_approval_bridge.py -q
# 37 passed
`

Passed broader foundation regression:

`powershell
pytest -p no:cacheprovider tests\test_voxel_block_preview.py tests\test_ready_wiring_routes.py tests\test_beefed_up_recovery_wiring.py tests\test_menu_coverage_and_safe_console.py tests\test_pub_manager_recovery.py tests\test_pub_partner_chat.py tests\test_ai_runtime_slots.py tests\test_runtime_spine.py tests\test_voxel_set_contract.py tests\test_pubblock_voxel_block_kit.py tests\test_visual_patch_approval_bridge.py -q
# 49 passed
`

Passed combined backend/frontend contracts:

`powershell
pytest -p no:cacheprovider tests\test_voxel_block_preview.py tests\test_ready_wiring_routes.py tests\test_beefed_up_recovery_wiring.py tests\test_menu_coverage_and_safe_console.py tests\test_pub_manager_recovery.py tests\test_voxel_set_contract.py tests\test_pubblock_voxel_block_kit.py tests\test_visual_patch_approval_bridge.py tests\test_frontend_startup_contracts.py -q
node tests\test_program_audio_runtime_node.js
node tests\test_avatar_glb_motion_consumer_node.js
node tests\test_voxel_block_preview_client_node.js
# 40 passed plus all 3 Node tests passed
`

## Suggested Next Wiring

1. Add route-level tests for /api/visual-patch/approve using the existing auth/test fixtures.
2. Add a runtime event bridge from PubcastVoxelBlockPreview to future visual patch/object adaptation tools.
3. Add black-box witness events for preview requests and approved visual patch submissions, without making black box accessible from the player menu.
4. Add a small status aggregator endpoint that reports backend route + frontend bridge readiness together.