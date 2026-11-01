# PubCast Reach — Build-Level Engineering Handoff

This file belongs to the build, not to one chat/session. Update it whenever a custom workaround, compatibility seam, limitation, source-selection decision, or non-obvious integration choice is introduced.

## Build rule

Reach is the product build. Source archives/repos are preserved evidence and donors, not sacred final structure. Prefer the strongest proven implementation, but change in small reversible increments. Before changing unusual code, determine what it is, why it exists, who calls it, what contract/state it owns, what tests cover it, and whether the oddity is an intentional workaround/compatibility seam.

A component may be unfinished, but anything marked done must be real: no fake success, no placeholders/stubs presented as completion, no simulated verification.

## Source hierarchy in this build

1. Current Reach behavior that is verified by tests/runtime.
2. Later verified repairs / explicit consolidation winners from FULL_SESSION_HANDOFF.
3. Newer repos/uploads when they demonstrably preserve or improve verified behavior.
4. Historical donors only when current behavior is missing/broken and the donor contract is understood.

Chronology alone never wins.

## Reversibility

Original uploads/repos/archives are never modified. Before replacing code in Reach, save the displaced Reach version under `/mnt/data/reach_builds/backups/` and record the reason here or in a `REACH_IMPORT_*.json` manifest.

## Current intentional customizations / integration decisions

### Vision logging dependency fallback — 2026-09-13

**Files:** `modules/pubcast_vision_routes.py`

**Why it exists:** Camera/vision route startup was hard-blocked by `ModuleNotFoundError: structlog` in environments where optional structured logging was not installed. Camera functionality does not depend on structlog semantics.

**Decision:** Keep `structlog` when installed. If absent, use a small standard-library compatibility logger that preserves the event name and key/value fields. This is a logging fallback only; it does not simulate camera/runtime success.

**Do not remove unless:** `structlog` becomes a hard, installed runtime dependency in every supported deployment and preflight enforces it.

**Verification:** module compiles/imports without `structlog`; full-app startup can proceed past vision route import.

### Bubble Stack full-host registration — 2026-09-13

**Files:** `main.py`, existing `modules/bubble_routes.py`, `modules/bubble_jeremy_adapter.py`, `modules/room_conductor.py`

**Why it exists:** The recovered Bubble implementation and routes were real and tested, but historical handoffs explicitly recorded that they were not mounted in `main.py`. A later Horizon full-host implementation showed the intended safe wiring: mount the Bubble router, expose `get_bubble_summary()` to Jeremy/RoomConductor, and keep Bubble spatial state owned by the Bubble subsystem.

**Decision:** Reach mounts `bubble_routes.router`, creates `BubbleJeremyAdapter`, and gives RoomConductor the Bubble summary provider. No hardcoded demo physics route is promoted to production.

**Do not "simplify" by:** folding Bubble state into RoomConductor, treating the PIKPC demo app as the main Bubble API, or auto-claiming a room has spatial awareness before it is configured. Unconfigured rooms intentionally report `AI_BLIND`.

**Verification:** `/api/bubble-stack/schema` responds; `/api/internal/room-conductor/status` reports a live Bubble context provider.

### Room Conductor remains internal process infrastructure

Room Conductor/Jeremy is not a guest-visible character slot. The internal status endpoint explicitly reports `internal_only=true`, `guest_visible=false`, `character_slot=false`. This distinction is intentional and comes from the verified Horizon wiring pass.

## Known current integration work

- Restore proven Aug-24 fixes lost during consolidation: `/api/bots/{bot_id}/speak`, `/api/inference/status` and any companion source-level fixes confirmed by the repair handoff/tests.
- Mount and configure the full PubPartner spine in the full PubCast host without duplicating `/api/pubpartner/turns/live`; preserve the 2i `messages[]` compatibility contract while gaining the richer PubPartner live-loop/provider/vessel/receipt surface.
- Activate Pub Manager authority/control plane in full `main.py` using the deterministic authority store and existing BlackBox/governance contracts.
- Attach BYOK to the full PubPartner spine after BYOK boot.
- Initialize Pete Enhanced/e-PETE only through its real bridge/runtime contract; it may report degraded/fallback honestly when renderer hardware is absent.
- Continue route/service reachability audit. "File exists" is not equivalent to "system is wired."


### e-PETE full-host activation + re-entrant lifespan re-arm — 2026-09-13

**Files:** `main.py`, existing `modules/pete_enhanced.py`, existing `modules/pete_enhanced_routes.py`

**Why it exists:** Reach already mounted the Pete Enhanced control router but never assigned it a `PeteEnhanced` instance, so the route surface existed while every call returned 503. The later Horizon full-host source showed the intended placement: construct e-PETE only after the real `VoxelBridge` exists, initialize its real renderer/fallback diagnostics, then bind the instance. `motion_system` is currently retained by `PeteEnhanced` only as a compatibility reference and is not consumed, so Reach intentionally passes `{}` rather than inventing a fake motion runtime.

**Decision:** Instantiate `PeteEnhanced` after the real voxel bridge; bind it to the existing security-hardened `/api/pete-enhanced` router; expose read-only internal aliases at `/api/internal/pete/{status,diagnostics,runtime-components}`; pass the real instance into StudioControl, VoxelStudioIntegration, and MocapIntegration where those systems already accept a Pete reference. Preserve honest runtime states: renderer WebSocket activation is not reported as full WebRTC/SHM success.

**Re-entrant lifespan compatibility:** Reach intentionally has an app-singleton `_pubcast_booted` guard because repeated TestClient/lifespan entries previously re-registered routers and recursively re-wrapped ThinkingContext. e-PETE clean shutdown correctly terminates its owned renderer process and disconnects the bridge, which made later guarded lifespan entries inherit stale stopped diagnostics. Do **not** remove the boot guard. Reach now selectively re-arms only e-PETE on re-entrant lifespan entry and shuts it down again on exit.

**Do not "simplify" by:** removing the boot guard, keeping the renderer child alive after shutdown, creating a fake MotionSystem solely to satisfy the constructor, or treating `voxel_renderer_connected` as proof of full browser WebRTC/shared-memory runtime.

**Verification:** `tests/horizon_ref_epete_runtime_activation_pass_1.py`, `tests/horizon_ref_epete_voxel_bridge_pass_1.py`, `tests/horizon_ref_canonical_wiring_pass.py`, and `tests/test_pubcast_smoke.py` — **16/16 passed** after the re-arm fix.

### Pause checkpoint — 2026-09-13

**State at pause:** Stop requested after handoff completion. No further code changes should be made until the developer explicitly resumes work.

**Last completed wiring seam:** e-PETE full-host activation with re-entrant lifespan re-arm. The accepted implementation and rationale are documented immediately above. Regression gate remains **16/16 passed** across e-PETE runtime activation, real renderer bridge behavior, canonical wiring, and PubCast smoke coverage.

**Next integration seam (NOT YET CHANGED): PubPartner full-host authority**

Current Reach contains both:
- a legacy/compatibility full-host PubPartner path used by 2i-style callers; and
- a richer PubPartner router/runtime that owns the broader live-loop/provider/vessel/receipt surface.

The two surfaces overlap at `/api/pubpartner/turns/live`. Mounting both without reconciliation would create duplicate route authority and risk split state/contracts. Do not solve this by blindly mounting both routers or deleting the legacy path.

Before changing PubPartner wiring, the next engineer/session must:
1. Read the full standalone PubPartner host (`PubPartner-Best` / Horizon host donor), its tests, and the current Reach `main.py` compatibility endpoint.
2. Identify the canonical request/response contracts used by 2i (`messages[]` compatibility) versus the richer PubPartner live-loop contract.
3. Decide on **one** route authority for `/api/pubpartner/turns/live`, preserving backward-compatible request handling where tests prove it is required.
4. Construct and bind the real PubPartner state (Vessel, provider/BYOK path, authority/receipts, Alex/Jeremy bridge) only from existing real implementations; do not invent shim state.
5. Make the smallest change that closes the proven wiring gap, then rerun both legacy compatibility tests and the richer PubPartner reference suite before accepting it.

**Reason this is paused instead of changed now:** the overlap is architectural, not merely a missing `include_router()` call. The program already has working behavior on both sides, so the correct next step is contract reconciliation, not a broad mount/rewrite.

**Build principle reinforced at this checkpoint:** weird/duplicate-looking code may be deliberate compatibility or workaround scar tissue. Before modifying it, determine what it is, why it exists, who calls it, what tests cover it, and what would break if it were removed. Record any new custom workaround or limitation here at build level, not only in session notes.

## Hardening / defucking-stacking checkpoint — 2026-09-13

This section records the audit work performed after the earlier pause checkpoint. The developer explicitly resumed work and requested a hard review of the wiring already added, with special attention to shortcuts, rushed assumptions, hidden lifecycle ownership, security boundaries, test pollution, and misleading success states.

### Pete / e-PETE lineage clarification

Reach contains multiple Pete/e-PETE lineages with different responsibilities. Do **not** deduplicate by name alone.

- `modules/evo/epete.py` is the EVO inference/system governor lineage.
- `modules/pete_enhanced.py` is the twin-engine/renderer diagnostics/orchestration lineage.
- Historical builds also contain Pete character/persona layers and compatibility shims.

The later full-host sources carried these lineages side-by-side. Similar naming is historical scar tissue, not proof of duplicate responsibility. Before changing any Pete/e-PETE component, trace its callers, owned state, transport, and tests.

### WebSocket compatibility + lifecycle repair

**Files:** `main.py`, `tests/test_04_websockets.py`, `tests/test_06_regression.py`

A later Aug-24 repair had restored `/ws/studio` and `/ws/unity` compatibility aliases before the generic `/ws/{room}` catch-all because Starlette route ordering is load-bearing. That repair existed in a stranded duplicate `modules/main.py` but was missing from the root `main.py` that Reach actually boots.

Reach now restores those aliases in the real entrypoint. The Studio alias uses the current `StudioWebSocketHandler` lifecycle (`connect -> receive_json -> handle_message -> disconnect`) rather than the obsolete/nonexistent `.handle()` call.

WebSocket tests were also hardened to tolerate legitimate startup `presence`/`history` frames and to avoid fixed room IDs that caused persisted history from prior test runs to masquerade as current messages.

**Do not simplify by:** moving the catch-all ahead of the compatibility aliases, restoring the obsolete `.handle()` call, or assuming the first frame on every socket must be chat.

### Test runtime isolation

**File:** `conftest.py`

Full-host pytest runs previously wrote legitimate runtime persistence into the candidate's real `data/` tree: BlackBox files, room history, user/bot profiles, emergency-bridge commands, SQLite stores, production state, and structured logs. That made tests order-dependent and contaminated the source candidate.

Reach now uses the existing `PUBCAST_DATA_DIR` hook before `main.py` import to create a disposable per-pytest-process copy of `data/`, and removes it at session finish. Direct tests that intentionally inspect checked-in fixtures such as `data/bots/*.json` still read the source fixture paths.

Known residue that could be attributed directly to earlier test commands was moved to `/mnt/data/reach_builds/backups/test_runtime_quarantine_20260913/` rather than deleted blindly. Ambiguous historical data was left untouched.

### Bubble Stack production hardening

**Files:** `modules/bubble_routes.py`, `modules/bubble_stack.py`, `tests/test_bubble_route_hardening.py`

Mounting Bubble made previously disconnected state-changing endpoints reachable. Reach now requires the existing `mod` production role for Bubble mutations while leaving read-only diagnostics available under the established security model.

The fallback Bubble grid is eager and its skeleton-frame work is O(bubbles x bones). Unbounded/non-finite geometry could therefore create runaway allocations or non-terminating behavior. Reach now:

- rejects non-finite origin/dimension/radius/spacing values;
- estimates the grid upper bound before allocation;
- defaults to a 20,000-cell safety ceiling;
- allows deliberate override through `PUBCAST_BUBBLE_MAX_CELLS` after capacity validation;
- uses `Field(default_factory=list)` for actor IDs instead of a mutable model default.

This ceiling is an implementation safety guard, **not** a permanent creative/studio-size limit.

### Restored endpoint/security hardening

**Files:** `main.py`, focused authorization/regression tests

- `/api/bots/{bot_id}/speak` is restored from the proven Aug-24 repair and now follows the current Reach `mod` role boundary in enforced-auth mode, preventing guest bot impersonation while preserving relaxed local behavior.
- lighting preset application no longer turns a successful lighting-state change into a false API failure merely because `hub` is unavailable during partial initialization.
- the old Purfluous sentinel regression guard was **not** blindly restored because the current BotManager callback path no longer matches the historical feedback-loop contract; that item remains a contract-re-evaluation issue rather than cargo-cult repair.

### SystemMemory + Room Conductor restoration and lifecycle

**Files:** `main.py`, existing `modules/system_memory.py`, existing `modules/room_conductor.py`, `tests/test_system_memory_conductor_wiring.py`

UniversalMemorySystem did **not** replace SystemMemory; later full-host evidence shows the two have distinct responsibilities. UniversalMemorySystem remains character/general memory, while SystemMemory provides Jeremy/Room Conductor operational/protocol briefing state.

Reach now constructs the distinct `SystemMemory`, gives it to Room Conductor, closes it at lifespan exit, and reopens only that connection on guarded re-entrant lifespan entry. Room Conductor shutdown is also honored so owned watcher tasks do not survive app shutdown.

**Do not unify these memory stores solely because they overlap conceptually.** Their ownership/semantics differ.

### Shared VoxelBridge lifecycle ownership

**Files:** `main.py`, `modules/pete_enhanced.py`, `modules/twin_engine_service.py`, `tests/test_shared_bridge_lifecycle.py`, `tests/test_full_host_shared_bridge_lifecycle.py`

The hardening audit found that root `main.py`, PeteEnhanced, and TwinEngineService could all call `connect()` on the same VoxelBridge, while shutdown ownership was ambiguous. This produced repeated connection attempts and risked parallel transport state.

Current Reach contract:

- one shared VoxelBridge object;
- TwinEngineService is the full-host lifecycle owner of that shared bridge;
- PeteEnhanced accepts `owns_bridge` (default `True` for standalone/backward compatibility); Reach passes `owns_bridge=False`;
- TwinEngineService reuses an already-connected bridge instead of reconnecting it;
- root `main.py` no longer performs a separate raw pre-connect;
- shutdown stops PeteEnhanced-owned renderer/diagnostic pieces first, then TwinEngineService closes the shared bridge once;
- guarded re-entrant lifespans re-arm in the same ownership order.

A real full-app probe verified one new bridge connection attempt per lifespan while retaining the same shared bridge object across guarded re-entry.

The full-host lifecycle regression test itself was later hardened to measure **attempt-count delta per lifespan** rather than assume a brand-new app singleton with an absolute counter of 1. This matters because Reach intentionally retains its app singleton across TestClient entries.

### Current camera / Vision / renderer archaeology — investigated, NOT YET PROMOTED

No new Vision/camera runtime wiring from this archaeology has been promoted yet. These are current findings for the next seam.

- Reach contains the canonical Python `CameraManager` plus `AdvancedCameraManager`; the latter is constructed but appears to have no clear current host authority and needs an explicit integrate-or-incubate decision before startup cleanup.
- The later `modules/vision.py` directly targets Reach's actual `modules.cameras.CameraManager` and was smoke-probed successfully against all six canonical camera sources, including real program-camera switching, invalid-camera rejection, frame generation, broadcast task start, and clean shutdown.
- Root `main.py` currently does **not** mount that later Vision manager. Older Aug-31 evidence shows Vision was once host-mounted, but the older `pubcast_vision_integration.py` lineage could fall back to standalone behavior because it expected a legacy camera-manager API.
- Therefore the intended next Vision move is **not** to restore the Aug-31 patch literally. Adapt the existing `/api/vision` route surface to the later `modules/vision.py`, its async contracts, lifecycle, and current Reach authorization model.
- The reconstructed 28-file Rust `pubcast_camera` camera-brain recovery is already preserved under Reach's recovery materials. It is a separate shot-intelligence/virtual-camera lineage, not a replacement for Python CameraManager. Historical assessment proved a reconstructed version compiled/ran, but its renderer integration remained unfinished.
- A separate Rust broadcast `CameraEngine` lineage with `FrameBuffer`, `PreheatState`, `DonationState`, and `ComputeBudget` has now been recovered from multiple historical reservoirs. This corrects the earlier historical assessment that the May broadcast engine had never been found.
- Reach already contains a Python `camera_engine_bridge.py` and camera switch endpoints call it, but current investigation found no host call to `set_connection(...)`/`boot_voxel_cameras()`, and the current `ws_renderer` motion WebSocket does not presently expose a proven `CAMERA_MODE_SWITCH` receiver. Treat this as a half-connected seam until end-to-end transport is proven.
- The GPU renderer lineage is separately preserved and includes real wgpu camera uniforms, voxel/scene rendering, skeleton/mocap systems, and v5.5 hardening work. Do not invent a second production renderer merely to connect cameras.
- `camera_rasterizer.py` is a real headless CPU software rasterizer and is useful as a verification/debug renderer, but it expects a different Python mesh contract and is not current production authority.

**Target architecture under investigation, not yet accepted as implementation:** one canonical Python camera/source authority, one real renderer process/transport, explicit adapters for shot intelligence and broadcast resource control, and no duplicated camera state that can split-brain between Python and Rust.

### Full handoff / fossil-record rule reinforced

The original `FULL_SESSION_HANDOFF` / MASTER_SESSION_HANDOFF remains mandatory archaeology input. Recent uploads, filenames, timestamps, and even working code do not supersede it automatically. When sources disagree, record the observation with its exact build lineage, then let current Reach behavior/tests establish present truth.

For Alex-related systems in particular: deliberate complexity must not be flattened because similarly named memory, persona, cognition, routing, governance, PubPartner, Jeremy/Cricket, EVO/VDI, or compatibility components look redundant. If purpose is not established: **PURPOSE NOT YET ESTABLISHED — DO NOT MODIFY.**

## Snapshot verification checkpoint — 2026-09-13

Immediately before creating the downloadable Reach snapshot, the focused hardening gate was run across:

- WebSocket compatibility/lifecycle tests;
- Bubble route hardening;
- main-route authorization parity;
- SystemMemory/Room Conductor wiring;
- shared PeteEnhanced/TwinEngine bridge lifecycle;
- full-host shared-bridge re-entry behavior.

Initial combined run exposed a suite-order assumption in the new bridge lifecycle test (absolute lifetime counter expected `1` despite intentional app-singleton reuse). The test passed alone; it was corrected to assert the per-lifespan **delta** instead. Final combined gate: **27/27 passed**.

### Immediate next engineering target

1. Finish camera authority map with the full fossil record in scope.
2. Repair/mount the later Vision manager against canonical `CameraManager`; adapt route async/lifecycle/security contracts.
3. Re-run camera/studio/voxel regression cluster.
4. Resolve `AdvancedCameraManager` authority (integrate unique capability or stop booting it and mark preserved/incubating).
5. Trace/close the Rust broadcast CameraEngine -> real renderer transport without inventing another renderer or declaring send-only success as end-to-end integration.
6. Then return to the paused PubPartner route-authority seam and remaining startup/reachability audit.

Foresight UI is currently being worked by another engineer/agent; avoid modifying that lane unless a backend contract requires coordination.
