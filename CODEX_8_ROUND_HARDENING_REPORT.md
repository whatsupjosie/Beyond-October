# 8-Round Debugging, Troubleshooting, And Hardening Report

Completed: 2026-06-14 09:16:38

## Round 1 - Syntax And Parse
Result: found BOM in new Python files. Fixed and reran.
Status: passed after fix.

## Round 2 - Focused Unit Tests
Node:
- tests/test_avatar_glb_motion_consumer_node.js passed.
- tests/test_program_audio_runtime_node.js passed.
Python:
- Initial run found 4 failures.
- Fixed alias precedence, JSON BOM, and Safe Console text.
- Rerun: 15 passed.
Status: passed after fix.

## Round 3 - Required File Presence
All required new implementation/scaffold/test files are present.
Status: passed.

## Round 4 - Contract String Checks
Confirmed expected contract names exist:
- PubcastGLBMotionConsumer
- registerAvatar
- consumePayload
- debugStatus
- pubcast:avatar-motion-commands
- avatar_motion_commands
- PubcastProgramAudio
- stopAll
- spatialGain
- duckMusicTo
- playUISound
Status: passed.

## Round 5 - GLB Rig Audit
Manny and Sheila:
- 89 joints each
- 0 embedded animations
- no duplicate joints
- no bad weight rows
- matching joint order
Status: passed.

## Round 6 - Safe Console Independence
Safe Console contains no img tag, no canvas tag, and no autoplay text/attribute.
Status: passed.

## Round 7 - Menu And Recovery Coverage
config/menu_coverage.json includes:
- Help / Recovery
- Out-of-session Safe Console
- Audio recovery
- Performance recovery
- Character/avatar recovery
- Recording recovery
- Scene/room recovery
Status: passed via focused tests.

## Round 8 - Final Readiness Review
Ready as construction-copy implementation scaffolding, not yet production-wired.
Status: passed for current scope.

## Bonus Follow-Up And Fix-It Path
1. Wire these in the construction copy only.
2. Add FastAPI route for /safe-console.
3. Add Pub Manager API endpoints.
4. Add page script tags for program_audio_runtime.js and avatar_glb_motion_consumer.js only where needed.
5. Register Manny/Sheila after GLB load.
6. Run browser smoke tests.
7. Run route tests.
8. Then decide whether to promote to the main build.
