# PubCast Reach — Post-Baseline Integration Final Handoff

**Integration date:** 2026-10-01 (America/Los_Angeles)  
**Starting rollback artifact:** `PubCast_Reach_CURRENT_PROGRAM_ROUND9_CORNER_AUDITED_2026-09-28.zip`  
**Starting SHA-256:** `9c847322844b9f0269e4022f68741b4ed2c5e5792380e18f5ebfa38bdb368951`  
**Method:** preserve the accepted/recovered September ledger; do not restart the full verification campaign; integrate only identified post-baseline work and concrete gaps into a clean copy of the sealed baseline.

## Result

The current package is no longer just the September 28 starting build. It contains the starting program **plus the post-baseline integration layer recovered/identified in the recent audit and commissioning chats**.

A clean assembled tree passed **172 focused tests** covering the new integration seams and existing neighboring contracts. This was deliberately not a rerun of the historical full 1,042-test campaign.

## Promoted into the current integrated tree

### 1. Canonical camera authority repair
- `CameraManager` remains the full-host authority.
- Added canonical `CameraSwitchEvent`, `CameraPoseEvent`, validated `update_pose()`, subscriptions, and atomic Program/Preview `take()`.
- Invalid/idempotent switches do not emit duplicate switch events.
- `TwinEngineService` accepts the canonical manager in full-host mode instead of operating a competing camera registry.
- Twin forwards renderer commands only for `VOXEL_3D` sources; ordinary physical/virtual sources remain canonical state only.
- False/rejected bridge sends now degrade honestly instead of silently looking successful.
- `AdvancedCameraManager` is preserved but quarantined by default; it requires explicit legacy opt-in.
- Existing Vision wiring was already on the canonical manager and was intentionally preserved.

### 2. Reconstructed September 13 Rust camera Stage-1 control plane
The recovery audit proved the accepted contract survived but the named later Rust source did not. The missing source has therefore been **reconstructed from the accepted contract**, not mislabeled as recovered original code.

Added:
- `modules/rust_camera_runtime.py`
- `modules/rust_camera_routes.py`
- `rust_crate/src/camera_control.rs`
- camera-message multiplexing in `rust_crate/src/ws_renderer.rs`
- `scripts/probe_rust_camera_control.py`
- `scripts/test_rust_camera_control.ps1`

Behavior:
- guarantees at least two canonical `VOXEL_3D` slots without changing Program/Preview merely because they exist;
- requires `PUBCAST_CAMERA_CONTROL_TOKEN` when mutation transport is enabled;
- uses versioned `pubcast.camera.control.v1` envelopes, exact request IDs, and restart-tolerant revisions;
- rejects stale revisions;
- never accepts direct external `take` authority;
- ACKs explicitly report `stage: 1` and `frame_path_proven: false`.

### 3. Reviewed 2.5D PubWorld Stage V1 runtime
Added `modules/pubworld_stage/` with:
- corrected perspective solver (signed pitch, off-frame horizon retained, degenerate-line reporting);
- expanded portable manifest schema (canvas, scale calibration, lighting, blocking marks, interaction anchors, surface connections, performance profile, asset manifest, explicit shot mode);
- atomic manifest save/list/export and path-contained ZIP import (Zip-Slip blocked);
- authoritative mutable `StageService` separate from authored manifest state;
- actor state, local-vs-Program screen focus, subscriptions, revisioned stage events;
- `/api/stage/*` routes.

This intentionally does **not** pretend a fixed painted plate supports arbitrary orbit shots.

### 4. Director / switcher integration
Added:
- deterministic `AutonomousDirector` with injected clock;
- speech activation/release debounce and silence return logic;
- separate decision authority from camera state authority;
- `SwitcherService` and `/api/switcher/*` Preview/Program/CUT/transition/PTZ state surfaces.

Existing production camera APIs/hotkeys remain intact; this is an additional integrated director/switcher layer rather than a UI rewrite.

### 5. EQ development evidence recorder
Added append-only `EQMonitoringRecorder` with separate streams for:
- exact two-sided transcript;
- observed telemetry;
- affect mathematical trace with baseline before/evaluation/baseline after;
- intervention trace;
- provider pipeline;
- outcomes;
- reviews.

Wired into:
- Hub exact committed chat path;
- Alex affect evaluation path;
- PubPartner live provider/final-response path.

Missing telemetry remains missing; inter-message latency is not mislabeled as typing speed. Recorder failures do not change a successful user-facing chat/provider result.

### 6. Affect → choreography
The existing `affect_choreo_bridge.py` was present but not on the active Alex processing seam. Alex now invokes the bridge best-effort after a valid affect reading when a choreography controller exists. A choreography failure cannot erase the affect reading or break the chat response.

### 7. Avatar performance adapter and live handoff
Added `modules/performance/`:
- capture-neutral normalization for PubCast mocap / mapping / MediaPipe-style landmarks;
- canonical joint aliases and blendshape preservation;
- automatic pelvis derivation;
- preserved Lumen +1.35m vertical calibration;
- conversion into the existing `PrecisionMocapFrame` / `AvatarPerformerManager` pipeline;
- `/api/performance/avatar/{avatar_id}/frame` crew route.

The existing Rust avatar-motion WebSocket remains avatar motion; it is not falsely relabeled as camera control or GPU camera rendering.

### 8. Recreate-bundle stop wiring
`RecordingService.stop_session()` now writes `recreate_bundle.json` from the actual pipeline state at the same stop boundary. It includes real camera/chat evidence and any registered final program artifact reference. Missing avatar/mocap/audio/stage evidence remains an explicit not-ready reason rather than fabricated completeness.

## Findings from earlier passes that were already fixed in the current tree
These were **not reopened or rewritten** because direct inspection plus neighboring tests showed the current source already had the repairs:
- legacy `/ws/{room}` authentication/role gating;
- durable SQLite DM consent/persistence and cross-worker visibility;
- governance audit HTTP routes;
- Vision using canonical `CameraManager`;
- PubPartner shared-auth/provider authority paths;
- existing EVO/IRM and Switchblade repairs represented by the accepted baseline tests.

## Focused validation run
The clean assembled tree passed:
- new post-baseline integration tests;
- shared bridge lifecycle;
- recreate-bundle contract;
- stage compatibility;
- durable and cross-worker DM authority;
- routing;
- Alex bridge;
- EVO protocol + Round9 EVO/IRM bridge;
- PubPartner shared-auth authority;
- studio camera preflight;
- existing startup and regression suites.

**Final focused result: 172 passed.**

See `FINAL_FOCUSED_TEST_REPORT.txt`.

## Genuine remaining gates — not hidden as "done"

1. **Rust compile / Windows promotion gate.** This environment has no Cargo executable, so the reconstructed Rust Stage-1 source could not be freshly compiled here. `scripts/test_rust_camera_control.ps1` is included to run the intended Windows gate: Rust tests/build, isolated authenticated renderer launch, two-camera probe, and false-frame-proof guard.
2. **GPU Stage 2 / Stage 3 camera proof.** Stage 1 means authenticated, ordered control state accepted. There is still no legitimate claim that the actual GPU view uniform consumed the revision or that a real frame was rendered after it. That requires the renderer/frame integration gate from `CAMERA_RENDERER_CONTRACT_V1.md`.
3. **Visible browser/media acceptance.** The container can verify Python/runtime contracts but not certify the user's actual Windows GPU/browser/audio device stack. The code is wired for that gate; it is not silently called accepted.
4. **Conversation Core v2 / Sheer.** The recovered September 28–29 material is research/contract work, not accepted production code. It remains preserved rather than being invented into a third conversation authority.
5. **PEQ/CRE-EQ donor authority.** Preserved donor work conflicts with the current Alex/Affect authority unless comparative evaluation selects it. It was not bulk-promoted.
6. **Personal Cricket Corps full implementation.** The revised specification explicitly leaves cartridge/protocol/permission-vocabulary details requiring a reviewable proposal. Existing Jeremy/Cricket infrastructure is preserved; new execution privilege was not invented.
7. **Conversation vault Stage1 source.** The recovery handoff says the named offline source was not recovered. It therefore remains an acquisition/reconstruction gap rather than fake integrated code.

These are the actual remaining boundaries. They are not a request to restart discovery.

## Included preservation references
`handoffs/recovered_progress/` contains the exact reference documents used for this integration:
- `PUBCAST_EQ_DEV_MONITORING_HANDOFF_2026-09-28.md`
- `CAMERA_RENDERER_CONTRACT_V1.md`
- `PubCast_Reach_2_5D_Stage_Engine_Spec_and_Review.md`
- `Pubcast_Integration_Handoff_2026-10-02.md` (the completed recovery/disposition ledger carried into this integration)

## Integration source manifest
`POST_BASELINE_CHANGED_SHA256.txt` lists every promoted/reconstructed source file in this integration delta and its SHA-256.
