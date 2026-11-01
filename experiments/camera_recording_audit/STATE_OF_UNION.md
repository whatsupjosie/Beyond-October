# October 24 camera and video recording state of the union

Branch: `october-24-prime-rust-recovery`. Source-level audit against October default source files and branch. **No claim of full runtime integration.**

## Confirmed code paths
- `modules/cameras.py`: authoritative simple camera registry, pose events, program/preview and take().
- `modules/cameras_advanced.py`: independent advanced camera manager with FFmpeg frame capture for supported USB/OBS/IP/file transports; voxel TCP HELLO is a connection check, not frame capture. NDI backend explicitly unavailable.
- `modules/rust_camera_runtime.py` + `rust_crate/src/camera_control.rs`: optional WebSocket control; Stage 1 ACK explicitly `frame_path_proven=false`.
- `modules/twin_engine_service.py`: state synchronization and optional bridge. `main.py` mounts it with bridge but no renderer (`mount_twin_engine(app, bridge=voxel_bridge, camera_manager=cameras)`).
- `modules/production_routes.py`: instantiates FFmpegCaptureEngine, starts it on ACTIVE recording, stops it and registers artifacts. The countdown path correctly defers capture until activation.
- `modules/capture.py`: `virtual` maps to `lavfi testsrc`, not PubWorld video; `voxel_3d` expects a real stream at the endpoint.
- `modules/recording.py`: session lifecycle, privacy checks, encoding profiles, FFmpeg export/transcode, import/export metadata.
- `modules/recording_pipeline.py`: separate event/EDL/timeline persistence, not a media encoder.
- `blackbox_recorder`: append-only witness/event recording, not a substitute for video frames.
- Prime recovery source: `experiments/prime_rust_recovery/src` has camera mode/frame queue and renderer trait, but no concrete GPU renderer.

## Executed tests
- Local FFmpeg generated a real 320x180 MPEG-4 MP4 from lavfi testsrc: ffprobe reported 15 frames, codec mpeg4, 320x180. This validates local FFmpeg encode, not PubCast's running API.
- New executable pytest contract suite added at `experiments/camera_recording_audit/test_camera_contract.py`. It is **not run** here because October's Python source is available through the GitHub connector but not mounted into the local runtime.
- Cargo/rustc not available in this local execution environment. No Rust build or GPU frame test completed.

## Priority defects/risks
1. `virtual://` recordings may be mistaken for real PubWorld output because capture substitutes a test pattern. Explicitly label synthetic output; ideally fail closed unless a deliberate test-pattern mode is selected.
2. `TwinEngineService` mounted without renderer: camera-state health does not mean frames are rendered.
3. Advanced camera frame-capture and canonical program/preview camera paths are separate; verify that the desired physical source is the source being recorded.
4. Rust control ACK is not GPU frame proof. Add frame ID, dimensions, checksum, and readback/recording verification.
5. Capture, event timeline, blackbox, and recordings have separate lifecycles. Test synchronization, pause/resume, partial FFmpeg failures, privacy, and crash recovery.
6. Check that the API's start/countdown/activate/stop returns the correct recording artifacts and that each output is decodable by ffprobe.

## Release gates
- Run `python -m pytest -q experiments/camera_recording_audit/test_camera_contract.py` from October root.
- Test API recording lifecycle with a deliberate test-pattern camera and ffprobe the artifact.
- Capture a real PubWorld/GLB scene through voxel camera and compare two camera poses' decoded frames.
- Test two real physical camera inputs and program/preview cuts; then verify resulting media and event timeline.
- Run Cargo tests for both Rust camera control and isolated Prime crate; do not conflate compile success with GPU proof.

No changes to October production files and no merge.
