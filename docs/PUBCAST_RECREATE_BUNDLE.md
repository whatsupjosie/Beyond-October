# PubCast Recreate Bundle Contract

Status: release-candidate contract, not yet fully wired to export.

PubCast must preserve enough production truth to recreate and rerender a show later. A flat video export is not enough.

## Required Fields

- `session_id`, `project_id`, `scene_id`, `take_id`
- `final_program_ref`: final program video or planned export reference
- `camera_timeline`: preview, program, cut, fade, unavailable-feed, and marker events with timestamps
- `mocap_events`: mocap stream references or captured mocap frame/event data
- `avatars`: avatar identity, asset URI, rig version, and skeleton version
- `stage_environment_version`: stage/environment asset or scene version
- `lighting_events`: lighting state changes
- `audio_refs`: audio track references or captured audio metadata
- `chat_log`: public/control chat or operator event log when enabled
- `ai_participation_log`: AI/bot participation, model, role, and prompt/result references where relevant
- `system_warnings`: dropped frames, failed feeds, unavailable systems, auth failures, export warnings
- `export_status` and `recreate_readiness`

## Current Repo Hooks

- `modules.recording.RecordingSession` already captures `session_id`, sources, profile, artifacts, and markers.
- `modules.recording_pipeline.ServerRecordingSession` already flushes `session.json`, camera switches, chat, markers, and EDL.
- `modules.timeline_routes` exposes timeline status and controls.
- `modules.mocap_integration` defines mocap frame/rig concepts and `/api/mocap/status`, `/api/mocap/start`, `/api/mocap/stop` exist in `main.py`.
- `modules.avatar_skeleton_system` defines a standard skeleton export concept.
- `modules.recreate_bundle` now defines the minimum JSON-compatible bundle shape.

## Next Engineering Gate

Wire recording stop/export to emit a recreate bundle beside the existing recording metadata. It should merge:

- active `RecordingSession.to_dict()`
- pipeline `session.json`
- camera program/preview events from the director switcher or hub
- mocap status/frame references
- avatar asset and skeleton metadata for Manny, Sheila, Pete, Repeat, and Sir Purfluous
- stage/environment version
- AI/bot participation log
- export warnings and missing-feed markers
