# Current state — 2026-10-30

Branch: `pubcast-25d-production-integration-2026-10-30` (separate from working Bella preview and main).

## Implemented in branch, runtime UNVERIFIED
- `static/production25d_core.js`: eight declarative genre packages, shot geometry, event/session core.
- `static/production25d_renderer.js`: layered procedural backgrounds, middleground, furniture/foreground, camera cropping, GLB drawing, graphics and scores.
- `static/production25d_storage.js`: IndexedDB transactional session and media storage.
- `static/production25d_app.js`: browser directing surface, camera cut/dissolve, cue controls, GLB loading, microphone capture/mixer, MediaRecorder, persistence and playback.
- `static/production25d.html`: responsive studio interface and preview/program monitors.

## Not complete / not verified
- Browser runtime and actual end-to-end recorded production not witnessed; run full acceptance sequence.
- Existing Control Room stations and backend orchestration NOT fully integrated; the new browser surface is a provisional local console, not the complete established Control Room.
- Blackbox and server recording integration not verified; local MediaRecorder must not be called full Blackbox.
- Camera rig/keymap, teleprompter, multiple audio channels, VTR, saved camera moves and studio entry point need integration review.
- Genre package staging and avatar occlusion/scale require browser inspection.
- Owner-supplied final images and Control Room photographs pending.

## Next engineering queue
1. Execute Node syntax/unit tests and browser launch of production25d.html.
2. Fix any renderer/recorder/runtime errors observed; validate actual video and manifest.
3. Trace existing Control Room source, keymap, station events, audio/video switcher and backend; integrate without duplicating.
4. Integrate teleprompter, VTR, camera rig and Blackbox as supported.
5. Verify each genre, 3D actor movement, audio, mobile layout, offline behavior.
6. Run objective observation, correction rounds, and full owner handoff.

Always continue after a milestone if actionable work remains.

## Additional integration work
- Added two Node test suites: `tests/test_production25d_core.cjs` and `tests/test_production25d_wiring.cjs` (written but NOT EXECUTED).
- Linked the established `static/control_room.html` navigation to the new 2.5D studio, preserving the existing controls.
- Added `LAUNCH_AND_ASSETS.md` with reproducible local launch, genre verification, asset replacement and recording checks.
- Examined `static/control_switcher.js` (server `/api/switcher/*`), `static/control_stations.js` (recording, chyron, teleprompter, VTR, audio), `static/camera_rig.js` and `static/control_room.html`. Full integration remains outstanding. Existing audio station had console-only mixer behavior; this has now been replaced with checked backend updates (runtime unverified).
- Attempted local GitHub access with `git ls-remote`; failed due container DNS (`Could not resolve host: github.com`). This prevents cloning for local execution via that path. Continue independent source integration and consider other verified test execution routes.

## Shared switcher/audio milestone (October 30)
- Owner directive: **same video switcher and audio mixer** for both environments. Video switcher reference imagery still pending from owner; not a technical blocker.
- Server `modules/switcher_routes.py`: CUT swaps Program/Preview atomically, dissolve validated, write routes require moderator authority.
- `static/production25d_switcher_bridge.js`: stage cameras register into canonical switcher; external source state reported; explicit local-only mode if backend cannot be reached.
- `static/production25d_app.js`: shared switcher attach and backend-driven Preview/CUT/dissolve; local canvas render is not server media ingest.
- Existing Control Room `static/control_switcher.js` now displays command failures.
- Shared `modules/program_audio.py`, `modules/program_audio_routes.py`, `static/program_audio_runtime.js`: authoritative master volume, initial-state sync, browser capture of shared audio bus mix.
- `static/control_stations.js` audio Apply now updates master/dialogue/music via server; removed console-only stub.
- 2.5D local recorder captures mixed audio stream plus optional mic (actual browser execution NOT verified).
- Added test sources `tests/test_shared_studio_switchers.py`, `tests/test_production25d_switcher_bridge.cjs`.
- Isolated trusted-JavaScript parse/mocks PASSED for core, renderer, storage, bridge, app, audio runtime; eight genre viewports validated; all required UI IDs present; shared switcher state changes and local fallback simulated. **This does NOT prove actual browser/pytest integration.**
- Outstanding critical: real browser and FastAPI testing, remote media ingest, Blackbox, full stations/recording wiring.

- Genre coverage expanded to eight packages: formal debate and political roundtable are distinct, with four individually blocked panelists in the roundtable. Director switcher now loads canonical camera registry, checks server command responses, removes invented audio/VU bars and displays actual bus states; monitor output remains explicitly unbound pending real video-feed integration.

## Three-round adversarial engineering audit — latest October 30 checkpoint
- **Round 1 (shortcuts):** camera IDs without real frames; fake/optimistic switcher, fake VU/timecode, stale GLB loads, missing true recording path; gaps identified.
- **Round 2 (media/defects):** authenticated, bounded JPEG confidence frame media plane and mounted FastAPI route, real Program/Preview frame publisher and remote Director reader, per-camera encode isolation/throttling, lease/tombstones/cleanup/backoff, atomic pair activation and server dissolve timestamps; 2.5D source declared NOT server-recordable without full ingest.
- **Round 3 (systems):** PANIC actually requests backend capture stop, audio stop/master zero, blackout cue and error reporting; no unacknowledged PAUSE/MARK/BARS/PANIC/knob fake successes; synchronized image Control Room, camera banking across 8 genre presets, safety of stale GLB loaders, corrected server cue precedence, all camera CUT entry points use CameraManager.take().
- Pivotal decision: use **browser-origin actual video + canonical shared switcher**, with independent local offline fallback. Implemented low-rate real JPEG confidence feeds, not broadcast-grade full-rate media. See THREE_SOLUTIONS_PIVOT.md.
- No browser or full FastAPI acceptance run yet. Cross-client audio, server full-rate video ingest, Blackbox and recorded media remain release blockers.
- 12 isolated V8 behavior/geometry checks passed; ten JS modules and both Control Room inline scripts parsed (proper inline extraction). These do not prove browser/runtime operation.
- GitHub Actions jobs showed failure with zero steps and no retrievable logs; cannot claim test commands started. CI runner investigation remains blocked.
- **Next:** obtain an executable checkout/runner; run Node and pytest; exercise real production, remote video, local recorder and PANIC; address failures; implement full-rate media and Blackbox integration; performance/debug pass; owner review only after evidence.


## Minimal shoot assembly/editor bridge — 2026-10-30 (branch implementation; UI runtime UNVERIFIED)
- Original compact Control Room editor is now wired: project, proxy bin, viewer, In/Out, source-level selections, split, lift, ripple delete, move shot, close gaps and transport. Non-destructive plan only, not a finishing suite.
- Clacker timebase = 15 seconds; per-track offset supports +0.030 s at microsecond precision. Local IndexedDB project/proxy storage and simple JSON sidecar interchange.
- Standard CMX3600 non-drop **24/25/30 fps cuts-only** EDL with cumulative frame rounding; lossless source-byte download as a separate action. EDL drops multitrack audio and subframe corrections; sidecar retains them. **Import into DaVinci Resolve not runtime validated.**
- Source/master provenance audit refuses to assert cinema-master quality from a preview or merely tagged 4K input. Existing browser recorder is only 1280×720 nominal 3Mbps; it does not meet the user's hard high-quality export gate.
- Live-switcher keyboard is disarmed when editing, so Space for playback cannot issue an unintended live CUT.
- Added 12 regression cases in `tests/test_editor_sync_interchange.cjs`; all **12 passed in an isolated V8 harness** using the actual fetched modules. CI wired but not evidenced as working. No Node, browser or Resolve run has been claimed.
- Binding finishing boundary and acceptance tests: `EDITOR_AND_FINISHING_BOUNDARY.md`. Next critical gate is deterministic source-level replay master + native high-quality 4K frame/selected-render output, not extra editor effects.
