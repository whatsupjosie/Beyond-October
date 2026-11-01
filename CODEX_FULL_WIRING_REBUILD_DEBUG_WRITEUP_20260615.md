# PubCast Full Wiring, Rebuild, And Debug Write-Up

Date: 2026-06-15
Build copy: `C:\Users\hardc\Downloads\big zip\codex_construction_pubcast_20260614`

This write-up documents the current wired foundation so PubCast can be rebuilt, debugged, or continued without guessing. It is based on the copied Big Zip construction build, not the original source folders.

## Non-Destructive Rules

- Work in the Big Zip construction copy unless the user explicitly says otherwise.
- Do not delete files.
- If something looks obsolete or dangerous, put notes or copies in a `rubish` folder for the user to review later.
- Make backups before editing important files.
- Keep Black Box external-only. Do not expose Black Box logs or controls through player or in-game menus.
- Prefer small reversible wiring passes with tests.

## Required First Read

Every continuation pass should first read:

`C:\Users\hardc\Downloads\CODEX_PUBCAST_AUTONOMOUS_SPINE (2).md`

That file defines the stabilization mission: runtime spine, canonical event flow, performer authority, station registry, locomotion, animation arbitration, and reversible work.

## Current Verified Status

Focused regression command last run:

```powershell
& 'C:\Users\hardc\anaconda3\python.exe' -m pytest -p no:cacheprovider tests\test_ready_wiring_routes.py tests\test_beefed_up_recovery_wiring.py tests\test_menu_coverage_and_safe_console.py tests\test_pub_manager_recovery.py tests\test_pub_partner_chat.py tests\test_ai_runtime_slots.py tests\test_runtime_spine.py -q
```

Verified result:

```text
30 passed in 6.66s
```

## High-Level Runtime Flow

```text
User/player/menu request
  -> FastAPI route in main.py
  -> Pub Manager / Switchblade / AI slot / runtime spine helper module
  -> JSON status, route preview, chat response, or safe recovery report
```

Motion side target flow from prior GLB bridge work:

```text
mocap frame / emotion / intent
  -> AvatarBehaviorRuntime
  -> avatar_motion_commands event
  -> PubcastAvatarMotionRuntime browser bridge
  -> PubcastGLBMotionConsumer
  -> Manny/Sheila Three.js GLB bones
```

## Core Files Currently Important

### FastAPI Wiring

- `main.py`
  - Route layer for AI slots, menu coverage, runtime spine status, Pub Manager recovery, Switchblade route preview, and Pub Partner Chat.

Current important route declarations:

```text
2029: @app.get("/api/ai/model-slots")
2033: @app.get("/api/menu/coverage")
2042: @app.get("/api/runtime-spine/status")
2072: @app.get("/api/pub-manager/safe-actions")
2079: @app.get("/api/switchblade/status")
2099: @app.post("/api/switchblade/route-preview")
2110: @app.get("/api/pub-manager/status")
2117: @app.post("/api/pub-manager/action")
2128: @app.get("/api/pub-manager/issue-report")
2136: @app.get("/pub-partner-chat")
2140: @app.get("/api/pub-partner-chat/status")
2148: @app.post("/api/pub-partner-chat/message")
```

### Runtime Spine

The canonical runtime spine package exists and imports successfully:

```text
runtime/spine/event_bus.py
runtime/spine/runtime_state.py
runtime/spine/performer_registry.py
runtime/spine/station_registry.py
runtime/spine/performers/performer_state.py
runtime/spine/performers/locomotion.py
runtime/spine/performers/animation_authority.py
runtime/spine/performers/replication.py
runtime/spine/stations/base_station.py
runtime/spine/stations/camera_station.py
runtime/spine/stations/director_station.py
runtime/spine/stations/pub_station.py
runtime/spine/__init__.py
```

The read-only endpoint `GET /api/runtime-spine/status` verifies expected files and imports these exported classes:

```text
EventBus
PerformerRegistry
RuntimeState
StationRegistry
AnimationAuthority
LocomotionSystem
```

This proves the spine is ready as a foundation, but it does not mean the full 3D world is walking avatars through scenes yet.

### Pub Manager Recovery

- `modules/pub_manager_recovery.py`

Purpose: dependency-light recovery and diagnostic contract for menus, safe console, and future Pub Manager AI explanations.

Safe actions currently include:

```text
program_audio.stop_all
animation.stop_all
avatar.reset_pose
mocap.pause
room.reload_assets
websocket.reconnect
recording.status
assets.check_manifest
issue.export
ai.model_slots
ai.switchblade_status
runtime.spine_status
```

Approval-required actions currently include:

```text
visual_patch.save_permanent
asset.replace_original
system.install_dependency
files.delete
```

Current Pub Manager covered systems:

```text
runtime
websocket
assets
avatar
motion
audio
recording
visual_patch
conversation_ai
alex
jeremy
evo
eq
model_slots
switchblade_router
background_math
runtime_spine
storage
```

Important behavior:

- Unknown or approval-required actions are not executed silently.
- `GET /api/pub-manager/status` builds a snapshot from current runtime availability.
- `GET /api/pub-manager/safe-actions` lists safe and approval-required actions.
- `POST /api/pub-manager/action` validates action safety, but runtime execution is intentionally minimal in this construction pass.
- `GET /api/pub-manager/issue-report` creates a structured report.

### Menu Coverage

- `config/menu_coverage.json`

Current menus include:

```text
play_stage
character
scene_room
audio
performance
visual_patch
recording_show
director_advanced
help_recovery
settings_safety
safe_console
ai_conversation
pub_partner_chat
```

Recent wiring added menu visibility for:

```text
switchblade_router
auto_switchblade
background_math
runtime_spine
runtime_spine_status
pub_manager_safe_actions
switchblade_status
switchblade_route_preview
```

Black Box remains intentionally absent from player-facing menus.

### AI Runtime And Switchblade

Relevant files:

```text
config/ai_runtime.json
modules/ai_runtime.py
modules/ai_providers.py
modules/ai_runtime_slots.py
modules/switchblade_router.py
modules/pub_partner_chat.py
```

Current active local model wiring in `config/ai_runtime.json` points to Ollama on:

```text
http://127.0.0.1:11435
```

Important configured profiles:

```text
ministral_3b_local -> ministral-pubcast:3b, enabled true
gemma3_1b_q4_local -> google_gemma-3-1b-it-Q4_K_L:latest, enabled true
gemma4_compute_q5_e2b_local -> gemma4-compute-q5:e2b, enabled true
gemma3_1b_local -> gemma3:1b, enabled true
ollama_gemma3 -> gemma3:1b, enabled true
echo_test -> echo backend, enabled false
gemma4_e2b_local -> gemma4:e2b, enabled false
gemma4_e4b_local -> gemma4:e4b, enabled false
gemma4_e4b_q4_local -> gemma4:e4b, enabled false
```

Current intended role logic:

```text
Alex creative/dialogue -> ministral_3b_local
Jeremy live support -> gemma3_1b_q4_local
Background math/process -> gemma4_compute_q5_e2b_local
Fallback where needed -> gemma3_1b_q4_local or echo_test depending route/config
```

Switchblade route preview endpoint:

```text
POST /api/switchblade/route-preview
```

This endpoint does not call a model. It lets the menu/Pub Manager preview which role and model slot would be chosen for a message.

Example body:

```json
{"role":"auto","message":"calculate the percent and verify the ratio"}
```

Expected decision slot:

```text
background_math
```

### Pub Partner Chat

Relevant files:

```text
modules/pub_partner_chat.py
static/pub_partner_chat.html
```

Routes:

```text
GET /pub-partner-chat
GET /api/pub-partner-chat/status
POST /api/pub-partner-chat/message
```

Purpose:

- Gives the user a chat interface even before the 3D world is ready.
- Allows Alex/Jeremy/background math slots to respond through the configured model profiles.
- Stores chat history under the build data directory.
- Includes Switchblade decision details in the response.

### GLB Motion Consumer Bridge

Relevant known files:

```text
static/avatar_glb_motion_consumer.js
modules/glb_motion_retargeter.py
tests/test_glb_motion_retargeter.py
tests/test_avatar_glb_motion_consumer_node.js
```

Purpose:

```text
mocap/behavior command
  -> browser command consumer
  -> mapped GLB bones
  -> Manny/Sheila visible skeleton movement
```

Design note: this is a conservative live bridge, not final high-end animation. It applies small safe rotations to prove the command pipeline and keep rigs from breaking.

### Visual Patch Kit And Voxel Systems

Relevant files seen in modules:

```text
modules/visual_patch_approval_bridge.py
modules/visual_patch_voxel_adapter.py
modules/voxel_asset_manager.py
modules/voxel_block_kit.py
modules/voxel_llm_adapter.py
modules/voxel_set_contract.py
modules/voxel_studio_integration.py
```

Current design intent:

- Visual Patch Kit can support 2D and 3D patch concepts.
- Temporary voxel patches can cover visual errors, outfit clipping, bad object/avatar fit, and proportional interaction issues.
- Permanent inventory/room saves must require explicit approval or approved auto-approve behavior.
- Object adaptations should be tied to avatar presence and regress/cache after the avatar leaves.

Next debug need: expose voxel bridge mode and fallback status in Pub Manager so Path C filesystem fallback is visible before performance suffers.

### Black Box

Black Box is the impartial flight recorder/witness system.

Current rule:

- Do not expose Black Box through player or in-game menus.
- It should be accessed outside the program so in-game systems cannot tamper with it.
- It should record important access and event facts, not speculation.
- It should stay tiny and low-load.
- During crash indication, it should preserve as much final state as possible.

Relevant tests/files seen:

```text
tests/test_blackbox_event_language.py
```

Do not wire this into player menu unless the user explicitly changes the design.

## Tests To Run By Area

### Ready Wiring Regression

```powershell
& 'C:\Users\hardc\anaconda3\python.exe' -m pytest -p no:cacheprovider tests\test_ready_wiring_routes.py tests\test_beefed_up_recovery_wiring.py tests\test_menu_coverage_and_safe_console.py tests\test_pub_manager_recovery.py tests\test_pub_partner_chat.py tests\test_ai_runtime_slots.py tests\test_runtime_spine.py -q
```

Expected current result:

```text
30 passed
```

### Runtime Spine Only

```powershell
& 'C:\Users\hardc\anaconda3\python.exe' -m pytest -p no:cacheprovider tests\test_runtime_spine.py -q
```

### Pub Partner / AI Slot Only

```powershell
& 'C:\Users\hardc\anaconda3\python.exe' -m pytest -p no:cacheprovider tests\test_pub_partner_chat.py tests\test_ai_runtime_slots.py -q
```

### Pub Manager / Menu Only

```powershell
& 'C:\Users\hardc\anaconda3\python.exe' -m pytest -p no:cacheprovider tests\test_pub_manager_recovery.py tests\test_menu_coverage_and_safe_console.py tests\test_ready_wiring_routes.py -q
```

## Known Warnings / Weak Spots

These were observed during tests or prior live checks and should be handled in future hardening passes.

### Invalid Waiting Room Bot Config

File:

```text
data\bots\sir_purfluous_waiting_room.json
```

Observed issue:

```text
Missing required fields: bot_id, name, provider, model, api_key_env
```

Recommended non-destructive fix:

1. Copy the file to a backup folder first.
2. Either repair it to match the current `BotConfig` schema or move a copy to `rubish` for user review.
3. Add a test or schema validation check if this bot should remain active.

### Voxel Bridge Path C Fallback

Observed issue:

```text
TCP connection refused
Bridge using Path C (File System) - severe performance impact
```

Recommended fix path:

1. Add a lightweight bridge status helper that reports active mode: TCP, SHM, or filesystem fallback.
2. Add that status to Pub Manager raw status.
3. Add safe recovery suggestion for voxel bridge degraded mode.
4. Only then tune performance or attempt bridge startup changes.

### Environment Secrets Not Set

Observed warnings:

```text
PUBCAST_JWT_SECRET is not set
PUBCAST_OWNER_PASSWORD is not set
```

Construction build can run like this, but live use should set these explicitly.

### E2B Background Model Slow/Empty Risk

Prior observed behavior:

- `gemma4-compute-q5:e2b` can be slow.
- Direct generation worked slowly, but one PubCast route produced an empty response after a long wait.

Recommended fix:

1. Add model health memory per profile.
2. Temporarily skip E2B after timeout or empty response.
3. Fall back to 1B Q4 for background math until E2B health recovers.
4. Expose recent model health through `/api/ai/model-slots` and Pub Manager.

## Rebuild Checklist From Current State

1. Copy the Big Zip construction build if starting a new experiment.
2. Read `CODEX_PUBCAST_AUTONOMOUS_SPINE (2).md`.
3. Confirm `config/ai_runtime.json` points to the intended local Ollama endpoint.
4. Confirm Ollama is running on `127.0.0.1:11435` if using current model config.
5. Run the ready wiring regression test command.
6. Open or call these status endpoints:
   - `/api/menu/coverage`
   - `/api/runtime-spine/status`
   - `/api/pub-manager/status`
   - `/api/pub-manager/safe-actions`
   - `/api/switchblade/status`
   - `/api/pub-partner-chat/status`
7. If those pass, test `/api/switchblade/route-preview` with creative, support, and math messages.
8. If model service is available, test `/api/pub-partner-chat/message` with Alex/Jeremy/background math roles.
9. Only after this foundation is green should more world/stage systems be wired.

## Next Best Development Passes

1. Non-destructively repair or quarantine the invalid waiting-room bot config.
2. Wire voxel bridge mode into Pub Manager status.
3. Add model health memory and E2B timeout fallback handling.
4. Add safe console buttons or status panels for the newly exposed endpoints if not already present in UI.
5. Continue runtime spine integration into actual stage/world movement without changing WebSocket contracts abruptly.
6. Keep GLB motion bridge conservative until Manny/Sheila skeleton mapping is inspected on real loaded GLBs.
7. Revisit UI utility consolidation only after routes and recovery are stable.
8. Keep Black Box external-only.

## Continuation Prompt

Use this to continue later:

```text
You are continuing PubCast construction work in C:\Users\hardc\Downloads\big zip\codex_construction_pubcast_20260614. First read C:\Users\hardc\Downloads\CODEX_PUBCAST_AUTONOMOUS_SPINE (2).md. Work non-destructively only in the Big Zip construction copy. Do not delete files. Inspect existing code before editing and back up touched files. Continue wiring ready systems with real implementation behind them, add focused tests, and run the current regression set. Keep Black Box external-only. Prioritize fixing invalid bot config, exposing voxel bridge health, improving model-slot health/fallback behavior, and keeping Pub Manager/menu recovery accurate.
```