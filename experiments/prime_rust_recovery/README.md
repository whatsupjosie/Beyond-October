# Prime Rust recovery — October 24 experiment

Recovered verbatim from `whatsupjosie/The-Prime`: `camera.rs`, `irm.rs`, `lib.rs`, and `renderer.rs`. Kept separate from October's production modules.

## Build
`cargo test --manifest-path experiments/prime_rust_recovery/Cargo.toml`

The manifest was adapted to the isolated crate name and its absent `src/ws_renderer.rs` binary target removed. Compilation is NOT verified in this environment.

## Current evidence
- `camera.rs`: CameraEngine mode and compute-budget policy; ArrayQueue frame buffer; preheat and donation.
- `irm.rs`: IRMController health value.
- `renderer.rs`: RenderBackend trait with render_frame returning bytes; no concrete renderer implementation.
- Prime's original manifest declared ws_renderer but its flat Git tree did not include `src/ws_renderer.rs`.
- No Rust compiler executable found in Prime's tracked root or the inspected ZIP directory entries; the 69 MB upload ZIP could not be decoded through the connector.
- These files do NOT yet render a PubWorld frame or integrate with October's TwinEngineService.

## Experiment criteria
1. Compile and run unit tests for the isolated crate.
2. Map CameraEngine mode to October's canonical CameraManager and Rust camera-control protocol.
3. Implement or connect a real RenderBackend; verify output dimensions, pixel contents, and changed frame hash after camera pose/switch.
4. Load a real PubWorld voxel scene and GLB performer; no substitute avatar silently permitted.
5. Keep the experiment branch isolated until frame proof and regression checks pass.
