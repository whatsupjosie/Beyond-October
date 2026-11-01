# Reach Camera → Renderer Contract v1 — 2026-09-13

Status: **authority contract accepted; GPU frame transport not yet implemented**.

This document records the smallest canonical contract established during the 2026-09-13 camera-authority run. It exists specifically to prevent another parallel camera registry or a send-only bridge from being mistaken for renderer integration.

## Authority

`modules.cameras.CameraManager` is the single full-host owner of:

- registered camera sources;
- program source;
- preview source;
- camera transform/FOV values stored on `CameraSource`.

Every successful program/preview change emits one `CameraSwitchEvent`. Invalid and idempotent switches do not emit.

`modules.vision.PubcastVisionManager` consumes/operates this authority. It does not own a second camera registry.

`modules.twin_engine_service.TwinEngineService` is an adapter in the full host. It derives camera status from CameraManager and translates renderer-capable camera events toward the existing bridge. Its legacy internal registry exists only in standalone/backward-compatible mode.

`AdvancedCameraManager` is preserved/incubating and is not booted in canonical Reach.

## Current renderer transports

### 1. Bulletproof `VoxelBridge`

Live full-host object: `modules.bridge_bulletproof.VoxelBridge`.

It already defines camera command types:

- `REGISTER_CAMERA`
- `SWITCH_PREVIEW`
- `SWITCH_PROGRAM`
- `PTZ`

It also exposes `register_voxel_camera()` and `switch_camera()`.

Current environment result: **EMERGENCY filesystem fallback**. TCP renderer connection is refused and POSIX shared memory is unavailable. A command being queued/accepted by this bridge is therefore **not renderer proof**.

TwinEngine forwards only `CameraTransport.VOXEL_3D` sources into these renderer/engine camera commands. Physical sources and ordinary `VIRTUAL` cameras remain CameraManager state only.

### 2. Rust `ws_renderer`

Live packaged binary: `bin/ws_renderer`.

Verified protocol: `BridgeMotionPayload` for avatar skeletal motion.

A historical `CAMERA_MODE_SWITCH` donor payload was sent to the real packaged binary during this run and was explicitly rejected:

`{"error":"missing field `avatar_id` ...","ok":false}`

Therefore `ws_renderer` is **not a camera-control receiver** today.

The e-PETE diagnostic now reports this accurately as `renderer_websocket_connected` with protocol `avatar_motion`; it no longer claims the GPU voxel renderer is operational.

### 3. Preserved wgpu/voxel renderer lineage

Real wgpu renderer/voxel/scene source exists in preserved recovery/components material, but it is not compiled into the live `rust_crate` / `bin/ws_renderer` path in canonical Reach.

Consequently there is currently no proven runtime that accepts CameraManager transform/FOV and produces a real GPU voxel frame.

### 4. CPU `camera_rasterizer.py`

Real headless software rasterizer. Useful as verification/debug/fallback evidence only. It is **not** production renderer authority and must not be mounted as a shortcut around the missing GPU integration.

## Accepted state flow

Current canonical flow:

`UI / Vision / Studio / Stage / production API`
→ `CameraManager`
→ `CameraSwitchEvent`
→ `TwinEngineService adapter`
→ renderer-capable transport **only for VOXEL_3D sources**

There must be no route-specific camera bridge patches after this point.

## Future renderer command requirements

A future real GPU receiver may use the historical `CAMERA_MODE_SWITCH` name or another versioned envelope, but it must carry at minimum:

- protocol/version identifier;
- camera/source ID;
- destination/state (`program`, `preview`, standby/donor if implemented);
- world position XYZ;
- world rotation XYZ;
- FOV;
- monotonic state/revision or sequence;
- timestamp.

The receiver must reply with evidence that distinguishes:

1. command parsed;
2. canonical renderer camera state applied;
3. a frame was rendered using that applied state.

A socket `send()` returning successfully, a bridge queue accepting a command, or a generic `{ok:true}` ACK is not sufficient for stage 3.

## End-to-end acceptance test

Camera integration is not "done" until a test proves:

1. switch a canonical CameraManager VOXEL_3D source to program;
2. renderer receiver observes that exact camera ID and transform/FOV;
3. renderer applies it to the active camera uniform/state;
4. renderer produces a real frame after that revision;
5. acknowledgement/telemetry identifies the applied camera revision/frame;
6. CameraManager still reports the same program camera;
7. switching through a different caller (Vision or Studio action) follows the exact same path;
8. teardown/re-entry leaves no duplicate subscriptions, renderer sockets, or stale camera authority.

## Deliberate non-actions

- Do not restore historical `camera_engine_bridge.py` literally. Its route-only hooks and presumed Rust receiver were never real end-to-end.
- Do not teach the avatar-only `ws_renderer` to say "camera accepted" unless it is actually connected to the GPU camera/render state.
- Do not re-enable AdvancedCameraManager as a parallel authority.
- Do not classify ordinary `VIRTUAL` sources as `VOXEL_3D` merely to make the bridge fire. That is a separate source-authority decision requiring renderer evidence.

## Prepared multi-camera control plane — 2026-09-13

Reach now contains an **interim Stage-1 control receiver** for the canonical camera path. This does not supersede the GPU acceptance test above.

### Canonical two-or-more camera runtime

`modules.rust_camera_runtime.RustCameraRuntime` is a non-authoritative coordinator over the existing `CameraManager` registry. On host boot it guarantees at least two `CameraTransport.VOXEL_3D` slots (`rust_cam_1`, `rust_cam_2` when no other voxel cameras already satisfy the minimum) without changing the existing Program or Preview source merely because those slots exist.

`CameraManager` now also owns:

- `CameraPoseEvent` and `update_pose(...)` for validated position / rotation / FOV mutation;
- atomic `take()` for Program/Preview exchange. Both authority fields change before notifications are emitted.

The Rust runtime subscribes to the canonical switch and pose seams. It mirrors only desired Rust control state; it cannot originate a production take and cannot make itself camera authority.

### Versioned receiver

Prepared Rust source in `rust_crate/src/camera_control.rs` and `rust_crate/src/ws_renderer.rs` multiplexes a second tagged message family on the existing WebSocket server:

`pubcast.camera.control.v1`

Legacy `BridgeMotionPayload` avatar traffic remains the fallback parse path and is not changed by camera messages.

Supported external actions are deliberately narrow:

- `hello`
- `status`
- `register`
- `set_mode` (`Program`, `Preview`, `Donor`)
- `update_pose`

`Transition` is **not** accepted from Python. Sending `Preview` is canonical; the actual Rust `CameraEngine::update_mode(Preview)` enters its internal Transition/preheat state itself.

A direct external `take` is also **not** accepted. `CameraManager.take()` remains the only production take authority; Rust receives the resulting per-camera Program/Preview state changes.

### Authorization and network boundary

The existing renderer server listens on `0.0.0.0` for compatibility with historical performer clients. Camera mutation therefore must not be an unauthenticated side channel.

The new camera protocol is disabled unless the Rust process has a non-empty:

`PUBCAST_CAMERA_CONTROL_TOKEN`

Reach likewise refuses to arm its camera WebSocket transport when `PUBCAST_ENABLE_RUST_CAMERA_CONTROL` is true but the token is absent. The Python transport sends the token on the versioned camera envelope only; legacy avatar traffic is unchanged.

This token provides authorization, not transport encryption. Remote/untrusted-network deployment still requires an appropriate trusted network/tunnel/TLS boundary.

### Revision and ordering contract

Every mutating camera command carries:

- camera ID;
- restart-tolerant 64-bit revision;
- wall-clock timestamp;
- exact request ID.

Python revisions are based on epoch nanoseconds with a process-local `last + 1` floor. This avoids the common restart failure where Python restarts at revision 1 while a surviving Rust receiver remembers a higher revision.

Rust stores the last applied revision per camera and rejects stale/non-increasing revisions. ACKs are matched to the exact request ID by the Python client. A mismatched ACK tears down the capability connection instead of being applied to the wrong command.

### Stage boundaries

A `pubcast.camera.control.v1` ACK currently proves only:

**Stage 1 — control-plane accepted:** Rust parsed, authenticated, ordered, and applied the command to `CameraFleet` / `CameraEngine` control state.

It deliberately returns:

`frame_path_proven: false`

until later renderer work proves:

**Stage 2 — renderer state applied:** the actual GPU camera uniform/view state consumed the requested camera revision.

**Stage 3 — frame evidence:** a real rendered frame was produced after that applied revision and telemetry ties the frame back to it.

Do not collapse these three stages into a generic `ok` status.

### Broadcast engine implementation divergence retained

The May architecture document described 60-second preheat and a 300ms donation hold. The recovered/compiled `camera.rs` implementation uses **2000ms preheat** and **500ms donation hold**. Reach does not silently change these timings during transport integration. They remain an explicit design-vs-implementation decision for a later tuning pass.

The recovered `FrameBuffer` did contain one objective contract bug: `latest()` called FIFO `ArrayQueue::pop()` once and therefore returned the oldest queued frame despite the architecture's latest-frame-priority requirement. The Reach copy now drains stale frames and returns the newest frame, with Rust unit tests prepared for the Windows build gate.

### Promotion gate

The Rust additions cannot be called compiled/green from this Linux environment because Cargo is unavailable here. The user's Windows toolchain has already proven the baseline `pubcast_camera_engine v0.1.0` builds, but the new fleet/receiver changes require a fresh build.

Use:

`scripts/test_rust_camera_control.ps1`

The script:

1. runs the `rust_camera_engine` tests;
2. runs the `rust_crate` tests;
3. builds `ws_renderer`;
4. launches an isolated renderer instance with a one-run camera-control token;
5. runs `scripts/probe_rust_camera_control.py` to register two cameras, set Program/Preview, and update pose;
6. fails if the control plane falsely claims GPU frame proof.

Passing this gate promotes **Stage 1 only**. The final camera definition-of-done remains the GPU/frame acceptance test earlier in this document.
