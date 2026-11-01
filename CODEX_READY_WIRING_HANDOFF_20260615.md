# Codex Ready Wiring Handoff - 2026-06-15

## Scope
Wired ready-but-unfinished foundation pieces in the copied construction build only:
C:\Users\hardc\Downloads\big zip\codex_construction_pubcast_20260614

Required spine instructions were read first:
C:\Users\hardc\Downloads\CODEX_PUBCAST_AUTONOMOUS_SPINE (2).md

## Non-Destructive Safety
- No source originals outside the construction build were edited.
- No files were deleted.
- Pre-edit backups were saved under:
  C:\Users\hardc\Downloads\big zip\codex_construction_pubcast_20260614\codex_validation_outputs\pre_wiring_20260615_130429
- Current copies of changed files were saved under:
  $copy

## Wired This Pass
- Added read-only menu coverage endpoint:
  GET /api/menu/coverage
- Added read-only runtime spine status endpoint:
  GET /api/runtime-spine/status
- Added Pub Manager safe action listing endpoint:
  GET /api/pub-manager/safe-actions
- Added Switchblade status endpoint:
  GET /api/switchblade/status
- Added no-model route preview endpoint:
  POST /api/switchblade/route-preview
- Expanded menu coverage for:
  - Switchblade router
  - Auto Switchblade
  - Background math
  - Runtime spine status
  - Pub Manager safe actions
- Expanded Pub Manager safe actions with:
  - i.switchblade_status
  - untime.spine_status
- Kept Black Box external-only and out of player/game menus.

## Files Changed
- main.py
- config/menu_coverage.json
- modules/pub_manager_recovery.py
- 	ests/test_beefed_up_recovery_wiring.py
- 	ests/test_menu_coverage_and_safe_console.py
- 	ests/test_ready_wiring_routes.py (new)

## Verification
Focused regression command:

`powershell
& 'C:\Users\hardc\anaconda3\python.exe' -m pytest -p no:cacheprovider tests\test_ready_wiring_routes.py tests\test_beefed_up_recovery_wiring.py tests\test_menu_coverage_and_safe_console.py tests\test_pub_manager_recovery.py tests\test_pub_partner_chat.py tests\test_ai_runtime_slots.py tests\test_runtime_spine.py -q
`

Result:

`	ext
30 passed in 6.66s
`

## Remaining Concerns Seen During Tests
These were already visible runtime warnings/errors, not caused by this pass:

- data\bots\sir_purfluous_waiting_room.json is not a valid bot config for the current schema. It is missing required fields including ot_id, 
ame, provider, model, and pi_key_env.
- Voxel bridge fell back to Path C filesystem mode because TCP was refused. This is functional fallback behavior but has severe performance impact.
- PUBCAST_JWT_SECRET and PUBCAST_OWNER_PASSWORD are unset in the test environment. Fine for construction testing, not okay for live use.

## Next Best Pass
1. Fix or quarantine the invalid waiting-room bot config non-destructively.
2. Add a lightweight health/status endpoint for voxel bridge mode so Path C fallback is visible in Pub Manager.
3. Add status memory for slow/empty Ollama model responses, especially the E2B background slot.
4. Continue scanning for ready-but-unwired systems and wire only those with real modules/tests behind them.
5. Keep Black Box external-only unless the user explicitly changes that rule.