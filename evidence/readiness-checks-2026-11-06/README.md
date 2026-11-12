# Remaining readiness checks — observed evidence

**Overall: NOT CLEARED.** Read `handoffs/SESSION_ENDING_2026-11-06_READINESS_CHECKS.md` for the gate table, failures, limitations and three verified editorial repairs.

- `environment.json`: actual device/application inventory. Physical Windows/phone/GPU/mic/camera and Resolve are unavailable.
- `finishing-readiness-final.json` (final source), `finishing-readiness.json` (earlier run), `finishing-before.*`, `finishing-after.*`: real stage capture, original/server ZIP/import hashes, actual UI selects, 30,000 µs correction, 24/25/30 fps EDL/sidecar, reload and relink reproduction/repair.
- `editor-bounds-before.log` / `editor-bounds-after.log`: three failing boundary checks, followed by fifteen passing new/existing Node cases. The new checks now live in `tests/test_editor_source_bounds.cjs`.
- `renderer-probe.json`: requested 3840×2160 canvas, actual supported 1280×720 drawing area; native 4K gate FAIL. Observation test passing does not make the requirement pass.
- `mobile-emulation.json`: touch viewport recording/reload PASS for emulation only.
- `virtual-timing.log/.xml`: failed first harness with zero intercepted worker frames; not an application failure or jitter pass.
- `virtual-timing.json`, `virtual-timing-proxy.*`: actual TCP proxy forwarding/jitter/skew and explicit stall disconnect PASS in a narrow virtual scope. Physical alignment and sample-accurate video sync remain NOT VERIFIED.
- `endurance-browser-unavailable.*`: initial restored-environment browser missing, one skip, not a pass.
- `endurance.log/.xml` where available, `endurance-first.json`: thirty-minute attempt failed at approximately four minutes, zero audio inputs. Initial failure media was not retained by the initial harness.
- `endurance-diagnostic.*`, `endurance-diagnostic.json`, `diagnostic-decoded-audio.json`: diagnostic stopped on a spectral snapshot while connections and decoded tones were still present; metric corrected and this run never counted as endurance acceptance.
- `endurance-confirmed.*`, `endurance-repeated.json`: repeated thirty-minute-target attempt actually failed in approximately one minute with one dropped input and explicit timing-buffer fault.
- `retained-failed-media.json`: hashes, sizes and actual FFprobe metadata for partial recordings preserved after failed attempts; large raw generated media stays outside Git.
- `affected.log/.xml`: 27 affected Python/browser/backend cases passed.
- `node-regressions/`: intermediate 108-case run; `node-final/`: final 30 files, 109 reported cases, all exit zero.
- `audio-edl-before.log` and `audio-relink-before.*`: additional reproduced audio/video-type defects. `editor-final.log`: sixteen final Node cases passed; `finishing-final.*`: two strengthened actual browser cases passed.
- `tested-source.json`: source tree and exact changed-file hashes. No current whole-suite rerun is claimed.

Commands executed in this Linux environment (with isolated data roots):

```sh
PLAYWRIGHT_NODEJS_PATH=$(command -v node) .venv/bin/python -m pytest -q -s tools/acceptance/test_finishing_transfer.py
PLAYWRIGHT_NODEJS_PATH=$(command -v node) .venv/bin/python -m pytest -q -s tools/acceptance/test_virtual_peer_timing.py
PLAYWRIGHT_NODEJS_PATH=$(command -v node) .venv/bin/python -m pytest -q -s tools/acceptance/test_render_and_mobile_boundaries.py tests/test_studio25d_archive_browser.py tests/test_recording_portable_bundle.py tests/test_recording_integrity_audit.py tests/test_shared_studio_switchers.py
PLAYWRIGHT_NODEJS_PATH=$(command -v node) .venv/bin/python -m pytest -q -s tools/acceptance/test_recording_endurance.py
PUBCAST_ENDURANCE_SECONDS=300 PLAYWRIGHT_NODEJS_PATH=$(command -v node) .venv/bin/python -m pytest -q -s tools/acceptance/test_recording_endurance.py
node --test --test-reporter=tap tests/test_editor_source_bounds.cjs tests/test_editor_sync_interchange.cjs
```

Actual commands additionally selected distinct `--basetemp` roots under `../readiness-checks-2026-11-06/` and named JUnit/log outputs to preserve each attempt. Node regressions were run separately per file with ninety-second timeout. Counts overlap and are not a unique product-completion total. Test authentication values are redacted where found. Non-finite spectral telemetry is represented as its string value in the copied JSON, preserving the observation while keeping valid portable JSON. No owner data or private production media is included.

Unimplemented scene-source replay/native rendering and unavailable Resolve/hardware checks remain FAIL/BLOCKED respectively. No larger canvas, proxy upscale, emulator, XML test count or FFmpeg decode is used to claim those gates fulfilled.
