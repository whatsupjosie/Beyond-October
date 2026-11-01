# PubCast Voxel Block Kit Status Wiring Handoff

Date: 2026-06-17
Scope: Big Zip construction build only, non-destructive copy work.

## What Changed

- Added a read-only backend status endpoint: /api/voxel/block-kit/status.
- Added Pub Manager awareness for oxel_block_kit as a foundation system.
- Added a safe Pub Manager action: oxel.block_kit_status.
- Added menu metadata placement under Scene / Room and Help / Recovery.
- Did not add the voxel block kit to the out-of-session safe console.
- Did not create map rooms, consoles, or player-facing builder UI.

## Status Endpoint Reports

- PubBlock unit profile: pub_block_10in.
- Base block: 10 inches / 0.254 meters.
- Subdivisions: full, half, quarter.
- Builders: stage floor, flat wall, backdrop panel, guide grid, doorway wall, rectangular prism, make voxel set.
- Materials from the current voxel block kit.
- Read-only flags confirming this route creates no map rooms and no consoles.

## Files Updated

- main.py
- modules/pub_manager_recovery.py
- config/menu_coverage.json
- 	ests/test_ready_wiring_routes.py
- 	ests/test_menu_coverage_and_safe_console.py
- 	ests/test_beefed_up_recovery_wiring.py
- 	ests/test_pub_manager_recovery.py

## Backup

Pre-edit copies were saved in:

$backup

## Verification

Passed:

`powershell
python -m py_compile main.py modules\pub_manager_recovery.py tests\test_ready_wiring_routes.py tests\test_menu_coverage_and_safe_console.py tests\test_beefed_up_recovery_wiring.py tests\test_pub_manager_recovery.py
`

Passed focused regression:

`powershell
pytest -p no:cacheprovider tests\test_ready_wiring_routes.py tests\test_beefed_up_recovery_wiring.py tests\test_menu_coverage_and_safe_console.py tests\test_pub_manager_recovery.py tests\test_voxel_set_contract.py tests\test_pubblock_voxel_block_kit.py -q
# 29 passed
`

Passed broader foundation regression:

`powershell
pytest -p no:cacheprovider tests\test_ready_wiring_routes.py tests\test_beefed_up_recovery_wiring.py tests\test_menu_coverage_and_safe_console.py tests\test_pub_manager_recovery.py tests\test_pub_partner_chat.py tests\test_ai_runtime_slots.py tests\test_runtime_spine.py tests\test_voxel_set_contract.py tests\test_pubblock_voxel_block_kit.py -q
# 41 passed
`

## Notes / Next Product Steps

- This pass makes the existing PubBlock kit discoverable and testable by the foundation systems.
- The next safe step is to add a tiny internal adapter that can request canonical block-kit previews without saving assets, still no map rooms or consoles.
- After that, wire selected generated voxel sets into the visual patch/object adaptation pathway with explicit user approval before persistence.
- Keep black box access outside the player menu, as requested.