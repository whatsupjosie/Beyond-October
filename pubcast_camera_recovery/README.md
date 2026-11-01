# PubCast Rust Virtual Camera Recovery

This archive is a **recovered and reconstructed working source tree** for the `pubcast_camera` crate discovered in the user's Library.

## Important provenance
- The exact original `CameraPacket` code was recovered verbatim from the archived transcript.
- The complete 28-file tree and module names were recovered from the transcript's static-analysis listing.
- The remaining source bodies were reconstructed from the recovered architecture, interfaces, camera presets, and behavior descriptions.
- This is therefore **not falsely presented as a byte-for-byte recovery** of every original `.rs` file.

## Recovered architecture
Four voxel virtual cameras:
- `cam_wide`
- `cam_host`
- `cam_reaction`
- `cam_orbital`

Pipeline:
`CameraEngine -> active camera -> VoxelCameraAdapter -> frustum culling -> VoxelRenderer -> CameraPacket`

## Build
```text
cargo build
cargo run
```

## Verification status
The source tree has been reconstructed into a dependency-free Rust 2021 crate to maximize portability. A Rust compiler was not available in the recovery environment, so an actual `cargo build` could not be executed here. The archive includes a static verification report instead.
