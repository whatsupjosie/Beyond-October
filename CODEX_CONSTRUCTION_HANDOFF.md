# Codex Construction Handoff

Completed: 2026-06-14 09:16:38
Workspace: C:\Users\hardc\Downloads\big zip\codex_construction_pubcast_20260614
Original source protected: C:\Users\hardc\Downloads\big zip\pubcast_complete_debugged_2026-05-08\pubcast_codebase

## Safety
- Original build was copied before implementation.
- Original source build was not modified.
- No deletes.
- No installs.
- No system setting changes.
- Work is undoable by discarding this construction folder.

## Implementation Files Created Or Adjusted In Construction Copy

### GLB Motion
- static/avatar_glb_motion_consumer.js
  - Replaced copied old class export with final browser bridge.
  - Exposes window.PubcastGLBMotionConsumer.
  - Supports registerAvatar, unregisterAvatar, consumePayload, debugStatus.
  - Listens for pubcast:avatar-motion-commands and avatar_motion_commands.
  - Includes Manny/Sheila/PubCast/Mixamo-style aliases.
  - Preserves zero rotation instead of treating zero as fallback.
- static/avatar_glb_motion_consumer.pre_codex_20260614.js
  - Backup of the copied previous file.
- modules/glb_motion_retargeter.py
  - Normalizes avatar motion payloads.
  - Clamps rotations.
  - Drops unknown bones.
  - Maps Manny/Sheila GLB bones to canonical names.
- tests/test_glb_motion_retargeter.py
- tests/test_avatar_glb_motion_consumer_node.js

### Program Audio
- static/program_audio_runtime.js
  - Adds PubcastProgramAudio browser runtime.
  - Supports dialogue/music/SFX/UI/VTR/room buses.
  - Supports spatial gain/pan helper.
  - Supports music ducking while dialogue is active.
  - Supports stopAll recovery.
  - Does not autoplay by itself.
- modules/program_audio.py
  - Server-side contract/state helper for program audio actions.
- tests/test_program_audio_contract.py
- tests/test_program_audio_runtime_node.js

### Safe Console And Menu Coverage
- static/safe_console.html
  - Minimal recovery page.
  - No images, no canvas, no autoplay dependency.
  - Health, studio, mocap, avatar manifest, Pub Manager, and stop-sounds controls.
- config/menu_coverage.json
  - Player-first menu coverage manifest.
- tests/test_menu_coverage_and_safe_console.py

### Pub Manager Recovery
- modules/pub_manager_recovery.py
  - Dependency-free recovery/status scaffold.
  - Safe action allowlist.
  - Approval-required action list.
  - Snapshot, suggestions, and issue-report helpers.
- tests/test_pub_manager_recovery.py

### State And Validation
- CODEX_CONSTRUCTION_STATE.md
- codex_validation_outputs/round1_js_syntax.txt
- codex_validation_outputs/round1_python_ast.txt
- codex_validation_outputs/round1_python_ast_rerun.txt
- codex_validation_outputs/round2_node_tests.txt
- codex_validation_outputs/round2_pytest_focused.txt
- codex_validation_outputs/round2_pytest_focused_rerun.txt
- codex_validation_outputs/round3_file_presence.txt
- codex_validation_outputs/round4_contract_string_checks.txt
- codex_validation_outputs/round5_glb_rig_audit.json
- CODEX_8_ROUND_HARDENING_REPORT.md
- CODEX_CONSTRUCTION_HANDOFF.md

## Validation Summary
- JS syntax checks passed.
- Node GLB consumer test passed.
- Node program audio runtime test passed.
- Python AST checks passed after stripping BOM from new Python files.
- Focused Python pytest passed: 15 passed.
- File presence checks passed.
- Contract string checks passed.
- Safe Console dependency checks passed: no img, no canvas, no autoplay.
- Manny/Sheila GLB audit passed: 89 joints each, no duplicate joints, no bad weight rows, matching joint order.

## Issues Found And Fixed During Hardening
1. New Python files initially had UTF-8 BOM from PowerShell Set-Content.
   - Fixed by rewriting new files with UTF-8 no BOM.
2. Retargeter alias precedence returned pelvis instead of hips for Pelvis.
   - Fixed by checking aliases before canonical lowercase names.
3. menu_coverage.json had UTF-8 BOM.
   - Fixed by rewriting no BOM.
4. Safe Console explanatory text included the word autoplay, failing the strict no-autoplay check.
   - Fixed text to say automatic audio.

## Remaining Work / Not Wired Yet
- New files are implemented in the construction copy, not wired into main.py/control pages.
- Safe Console route is not mounted yet.
- Program audio runtime is not loaded by pages yet.
- Pub Manager recovery endpoints are not mounted yet.
- GLB consumer still needs to be called from the real GLB loader after Manny/Sheila load.
- avatar_motion_runtime.js equivalent still needs integration if the existing app has no event bridge.
- Full browser visual testing was not run.
- Full app startup and full pytest were not run.

## Suggested Next Fix-It Path
1. Mount static/safe_console.html as /safe-console in the construction copy.
2. Add script loading for program_audio_runtime.js on relevant pages, but keep it idle until user action.
3. Add Pub Manager routes that wrap modules/pub_manager_recovery.py.
4. Add the GLB registration call wherever Manny/Sheila GLTFLoader completes.
5. Add a browser smoke page or console snippet for PubcastGLBMotionConsumer.consumePayload.
6. Run targeted route tests.
7. Start the app from the construction copy and visually verify Safe Console, stage, control room, and Manny/Sheila motion.
8. Only after that, consider merging these files into the main build.
