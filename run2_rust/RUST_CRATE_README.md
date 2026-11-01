# rust_crate — build notes

Real, verified state as of 2026-08-23 (Run 2/3 sessions). Read this before
re-discovering any of it the hard way.

## Toolchain

No Rust toolchain is preinstalled in the Claude sandbox environment.
`rustup.rs` is blocked by the network allowlist (403). Use apt instead:

```
apt-get install -y rustc cargo
```

This installs rustc 1.75.0 (Ubuntu's packaged version), which matches
`edition = "2021"` in Cargo.toml and has been confirmed to build the crate
cleanly.

## Build targets

```
cargo build --lib                          # core skeleton + bridge types — clean, 0 warnings
cargo build --bin ws_renderer               # the actual WebSocket server — clean, 2 trivial unused-import warnings
cargo build --lib --features full-animation # gated animation subsystems — STILL FAILS, see below
cargo test --lib                            # 23 tests, all passing
```

## The `full-animation` feature

`lib.rs` gates four modules (`avatar_animation_system`,
`animation_data_library`, `avatar_fitting_system`,
`complete_animation_controller`) behind `#[cfg(feature = "full-animation")]`.
As shipped before 2026-08-23, this feature was referenced but never declared
in `Cargo.toml` — meaning it could not be turned on at all. Fixed by adding:

```toml
[features]
full-animation = []
```

One real bug was found and fixed once this became buildable:
`animation_data_library.rs` was missing `use super::JointTransform;` (it
relied on a glob import that doesn't transitively re-export that type).
Fixing that resolved 16 of 23 compile errors under the feature flag.

**7 errors remain, unfixed on purpose.** Five types referenced in
`complete_animation_controller.rs` — `BoneMask`, `AnimationLibrary`,
`TransitionCondition`, `AnimationStateMachine`, `AnimationBlendTree` — are
not defined anywhere in the crate. This is unfinished design work, not a
wiring bug. See `RUN3_HANDOFF_2026-08-23.md` for the reasoning on why these
weren't guessed at and implemented under audit/run pressure.

## Running the renderer for real

```
PUBCAST_WS_PORT=8765 RUST_LOG=info ./data/bin/ws_renderer
```

Two things worth knowing:
- **`--port` on the command line is silently ignored.** Only the
  `PUBCAST_WS_PORT` env var is actually read (checked in `ws_renderer.rs`,
  not fixed yet — flagged as a small cleanup item).
- With no `RUST_LOG` set, the binary prints nothing on startup even though
  it's running correctly — it just doesn't log by default. Don't mistake
  silence for failure; check the port directly if unsure.

## Where the binary needs to live

`modules/doctor.py`'s health check (`_check_rust_bridge_binary`) looks for
it at `data/bin/ws_renderer`, resolved from `DATA_DIR` in `main.py` (which
is `Path(settings.data_dir)`, i.e. `data/` relative to repo root — traced
through `modules/appconfig.py`). **Not** `rust_crate/bin/` and **not**
`rust_crate/target/release/` directly — copy the built binary out:

```
cargo build --release --bin ws_renderer
cp target/release/ws_renderer ../data/bin/ws_renderer
chmod +x ../data/bin/ws_renderer
```

Verified this run: `run_doctor()` reports `pass` once the binary is there,
and `AvatarPerformerManager` (the real Python-side counterpart — see below)
goes from "not available" to "ready" at boot.

## The Python-side counterpart

**It is `modules/avatar_performer.py`, not `modules/unified_bridge.py`.**
`unified_bridge.py` (and `bridge_bulletproof.py`) describe a separate
C++/shared-memory protocol (V3.9-BULLETPROOF-DUAL-VOXEL-DX12) on a different
transport entirely. `ws_renderer.rs` is a plain WebSocket server;
`avatar_performer.py`'s `PerformerStreamer` / `AvatarPerformerManager`
classes are the real client, both defaulting to `ws://localhost:8765`. This
was confirmed by grepping for the literal port number across `modules/*.py`,
not assumed from either file's name or docstring.

**A real, live round trip was verified**: built binary → real socket
connect → real `PerformerStreamer.send_frame()` with correctly-shaped
`BridgeBoneData` payload (`position: [f32;3]`, `rotation: [f32;4]`) → server
logged `New avatar registered: <id> [MANNY]`. The production code path in
`avatar_performer.py` already builds correctly-shaped payloads; a hand-written
test using a bare array instead of the full position/rotation object was
correctly rejected by the server — that was the test's mistake, not a bug.

**Still open:** `AvatarPerformerManager` is instantiated in `main.py` but
`.start()` is never called anywhere. It initializes to "ready (not started)"
and stays there — nothing in the current app boot sequence actually connects
it to a running renderer. This is a real, separate gap from anything fixed
this session.

## Missing dependencies, now declared

`websockets` and `posix_ipc` are real, used-in-production dependencies
(`avatar_performer.py` and `bridge_bulletproof.py` respectively) that were
missing from `requirements.txt`. Added 2026-08-23. `posix_ipc` is POSIX-only
(marked with an environment marker); on Windows the bridge falls back to
"Path C" (filesystem), which the bridge's own logging calls out as a severe
performance impact.

*Rear View Foresight LLC — Feic Mo Chroí*
