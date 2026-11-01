# Frontend Check + Visual Patch Route Test Handoff

Date: 2026-06-17
Scope: Big Zip construction build only. Non-destructive, test-focused follow-up.

## Decision

Checked the frontend first because the backend preview route was already passing, and the main risk was whether the quiet browser bridge was correctly loaded and shaped.

## Frontend Result

Confirmed:

- static/voxel_block_preview_client.js is present.
- The client loads after audio and GLB motion bridges on:
  - static/control.html
  - static/stage.html
  - static/stage_3d.html
  - static/avatar_walk_test.html
- JS syntax checks passed for:
  - static/voxel_block_preview_client.js
  - static/program_audio_runtime.js
  - static/avatar_glb_motion_consumer.js
- Node runtime tests passed for all three browser bridges.

The frontend bridge is contract-ready. It is still intentionally quiet: no UI, no console, no map-room editor.

## Backend Follow-Up

Added route-level tests for existing endpoint:

POST /api/visual-patch/approve

The new coverage proves:

- Missing auth is rejected.
- Guest auth is rejected.
- Mod auth can approve an adaptive extension.
- Approved adaptive extension persists both PubWorld prop data and a canonical voxel set into the test data directory.

## File Updated

- 	ests/test_main_route_authorization_parity.py

## Backup

Pre-edit copy:

$backup

## Verification

Passed frontend contract check with permission-enabled app writes:

`powershell
pytest -p no:cacheprovider tests\test_beefed_up_recovery_wiring.py tests\test_frontend_startup_contracts.py tests\test_ready_wiring_routes.py tests\test_menu_coverage_and_safe_console.py -q
node tests\test_program_audio_runtime_node.js
node tests\test_avatar_glb_motion_consumer_node.js
node tests\test_voxel_block_preview_client_node.js
# 21 passed plus all 3 Node tests passed
`

Passed route authorization file:

`powershell
pytest -p no:cacheprovider tests\test_main_route_authorization_parity.py -q
# 6 passed
`

Passed combined backend/frontend wiring regression:

`powershell
pytest -p no:cacheprovider tests\test_main_route_authorization_parity.py tests\test_visual_patch_approval_bridge.py tests\test_voxel_block_preview.py tests\test_ready_wiring_routes.py tests\test_beefed_up_recovery_wiring.py tests\test_menu_coverage_and_safe_console.py -q
node tests\test_program_audio_runtime_node.js
node tests\test_avatar_glb_motion_consumer_node.js
node tests\test_voxel_block_preview_client_node.js
# 30 passed plus all 3 Node tests passed
`

## Next Good Target

Add black-box witness event hooks for voxel preview requests and approved visual patch submissions, without exposing black box through the player menu.