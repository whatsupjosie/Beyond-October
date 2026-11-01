# Verification record

- GitHub file existence was confirmed via connector for core, renderer, storage, app and HTML on the integration branch.
- No browser-based acceptance test has been performed in this run; runtime status remains **UNVERIFIED**.
- No automated test run result is asserted without an actual executed test.
- Owner previously verified the separate Bella Faux Pas walkable world in Chrome; that does not verify the new production interface.

## 2026-10-30 — connector-backed isolated JavaScript checks
Execution method: fetched current integration-branch JavaScript source through the connected GitHub connector and evaluated trusted pure modules using an isolated JavaScript engine with controlled mocks. This is NOT a browser test, GitHub CI run, Node test command, or server execution.

**Passed in isolated V8 checks:** syntax parsing of 2.5D core, renderer, storage, app, shared switcher bridge and program audio runtime; seven packages validate with distinct bounded viewports; every app UI bound ID present in HTML; audio master gain set to 0.32 and media capture track available using a mocked audio context; shared switcher mock registered five news cameras, selected Preview, atomically took Program and Preview, dissolved, delivered state callbacks, and truthfully reported offline mode.

**Not executed:** pytest and Node test files added to repository (require a local or CI run), browser MediaRecorder capture, actual three.js avatar rendering in production studio, audio across tabs, server switcher route on actual FastAPI runtime. Do not mislabel mock checks as real integration results.

Further isolated V8 checks (not browser runtime): latest studio core validated eight distinct genre configurations, bounded camera viewports (including seven political-roundtable presets), distinct blocking positions; director console inline JavaScript parsed, no synthetic audio meter animation detected; Control Room scripts, audio runtime, stage app and bridge parsed; DOM binding IDs matched existing 2.5D HTML. Actual FastAPI and MediaRecorder acceptance still untested.

## Three-round audit / latest concrete evidence
- Isolated V8 source checks: 10 JavaScript modules parsed; inline script of Director Switcher and image Control Room parsed; 45 2.5D UI IDs matched their app binding requirements.
- Isolated V8 behavior (mocked network, NOT server): **12/12 passed**, covering 8 package configurations and bounded viewports, shared camera registration/atomic select/CUT, two independently published camera frames, publisher stop, monitor display and object URL cleanup. Previously a test fixture lacked a `style` field, which was corrected; not a production bug.
- JPEG SOF parser algorithm checked against one genuine PIL 64x64 JPEG inside local container; full FastAPI pytest remains unrun.
- GitHub CI workflow triggered; jobs show `failure` with empty step lists; redirected log blobs unavailable. The actual test commands cannot be confirmed to have started. No green CI claim.
- **NOT VERIFIED:** browser UI render and GLB animation, actual 2.5D frame reception across browsers, MediaRecorder WebM/MP4 output and IndexedDB playback, audio and mic capture, FastAPI route acceptance, Blackbox, full video stream server recording, mobile GPU/CPU, long-running repeated production and owner acceptance.
- Latest code review also converted all known CUT entrypoints (`modules/switcher_routes.py`, `modules/production_routes.py`, `modules/studio_console_actions.py`) to CameraManager.take(); runtime regression pending.


## 2026-10-30 — Minimal editor isolated audit (NOT actual browser testing)
- 12/12 `tests/test_editor_sync_interchange.cjs` test cases executed via a V8 test-function adapter against the live GitHub-fetched CommonJS source; passed. Tests include 15-second clacker, 30ms offset, drift rejection, split/lift/ripple, 24/25/30 fps, cumulative EDL frame rounding, quality provenance warnings.
- Seven edited JavaScript files parsed in isolated V8 without syntax error: `editor_sync_core`, `editor_sync_store`, `editor_sync_station`, `editor_interchange`, `control_keys`, `control_stations`, `switcher`.
- `static/control.html` editor wiring: 48 referenced IDs present, no duplicate IDs among 203 IDs, editor script loaded after core/interchange/store.
- Fake DOM and fake IndexedDB-store smoke: editor initialization, New Shoot, import two video/audio proxies, select camera, save 0.030-second manual offset, mark clacker #0 at 5 seconds; zero synthetic runtime errors.
- **Still unverified:** real browser IndexedDB, audio/video playback timing under media load, all click actions on actual HTML, full Node `node --test` command, GitHub CI runner, Resolve Free EDL import/relink, high-quality source-level re-render. Do not report as passed.
