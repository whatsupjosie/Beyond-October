# PubCast Recording, Save, Import, Export Status - 2026-06-18

## Honest Status

PubCast can now create a real recording artifact from a virtual camera source when FFmpeg is available. This pass connected the previously separate FFmpeg capture engine to the active production recording routes and studio action path.

## What Is Working

- Recording session lifecycle:
  - `/api/recording/preflight`
  - `/api/recording/start`
  - `/api/recording/{session_id}/activate`
  - `/api/recording/{session_id}/stop`
  - `/api/recording/{session_id}/pause`
  - `/api/recording/{session_id}/marker`
- Studio console action recording:
  - `recording.start`
  - `recording.stop`
- Real media artifact registration:
  - `RecordingService.register_artifact(...)`
- Export:
  - `/api/recording/{session_id}/export`
  - Zip contains metadata JSON plus `media/...` files.
- Import:
  - `/api/recording/import`
  - Restores session metadata and media artifact records from zip.
- Project save/autosave:
  - `/api/projects/{slug}/autosaves`
  - `/api/projects/{slug}/savefile/preview`
- Generic file import/upload:
  - `/api/upload`
- VOD listing:
  - `/api/vod` now handles `RecordingSession` objects and returns completed sessions with artifacts.

## Fixes Made

- Wired `modules.capture.FFmpegCaptureEngine` into `modules.production_routes`.
- Added graceful FFmpeg shutdown with `q`, so MP4 files finalize instead of being killed empty.
- Changed FFmpeg process stdout/stderr to `DEVNULL` to avoid pipe deadlocks during long captures.
- Normalized profile bitrates for FFmpeg:
  - `50Mbps` -> `50M`
  - `320kbps` -> `320k`
- Mapped capture/export H.264 to `libx264` and added `yuv420p` for compatibility.
- Added `RecordingService.register_artifact(...)`.
- Fixed `/api/vod` artifact filtering.

## Proof Run

Real capture smoke:

- FFmpeg engine available: true
- Captured file: `wide_shot.mp4`
- Captured size: `641233` bytes in the direct smoke test
- Session artifacts after registration: `1`

Export/import smoke:

- Exported zip: `smoke_export_import.mp4.zip`
- Zip members:
  - `media/wide_shot.mp4`
  - `smoke_export_import.json`
- Imported session artifact count: `1`

## Validation

Passed:

```text
21 passed in 5.27s
```

Focused tests covered recording lifecycle, studio action routes, camera preflight, program audio, and console manifests.

## Still Not Final Broadcast Polish

- Virtual cameras currently record FFmpeg test-pattern video until the real renderer/program feed is connected as an input.
- NDI/RTMP/SRT sources will only record when those real endpoints exist and FFmpeg supports the transport.
- The recording pipeline records event/session data and EDL, but richer edit exports should be hardened later.
- `PUBCAST_JWT_SECRET` is still using an insecure default in the local test environment. That must be set before any real deployment.
