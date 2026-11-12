# Local recorded clacker — executed evidence, November 5, 2026

Scope: one Linux Chromium/SwiftShader host and one shared Web Audio clock.
This is not independent-device synchronization or a sample-accurate video claim.

## Implementation and decisions

Compared three timing paths: main-thread timers (drawing can delay them), an
AudioWorklet on the existing audio clock (chosen for exact sample intervals),
and a separate native/backend reference clock (would add an independent clock
and deployment dependency without solving browser video presentation).

The worklet generates a 50 ms, 1 kHz pulse every fifteen seconds, beginning at
fifteen seconds after the production origin. It feeds a dedicated journaled audio
source; it never joins the audible Program bus. Video carries a 500 ms red dash.
Each take and reference segment points to its own immutable clock-generation ID;
after an audio-clock failure, a fresh generation does not overwrite the previous
take's origin/marks. Interrupted generations and affected media remain incomplete.
Sources preserve the existing original-byte, recovery and server-save contracts.

The first real media check found that a 120 ms flash could be absent from encoded
video at the measured software-rendering rate. The mark was extended to 500 ms,
with an explicit canvas-track frame request. A startup flash was also removed:
the first pulse/mark is at fifteen seconds, not a partial mark at session zero.

Measured video delay still exceeded 250 ms (244 and 318 ms). Source inspection
showed Program and Preview rendering the identical GLB pose twice in a frame.
Compared priority/timer changes, exact pose-render reuse, and a new worker-based
video compositor. Reusing the current pose was the bounded change: Preview uses
the same current-frame pixels only when frame stamp, resolution and appearance
match. A new frame or changed appearance renders normally; teardown releases the
copy. No actor animation, image resolution, shader or consent guard was removed.

After that correction, an actual encoded-media run measured 79 and 152 ms video
delay for two successive pulses. Actual reference pulses were exactly fifteen
seconds apart; Program audio contained no blip. These are observations, not a
guaranteed delay bound on other devices. `pytest-*-measured-clacker.json` preserves
the before/after measurements, including failures.

## Executed checks and failures

- Initial expanded-neighbor run: thirteen passed, one failed. The slow-storage
  injector had started delaying the new reference track instead of Program;
  it now explicitly delays Program and retains the exact-byte preservation
  assertion. Progress callbacks also no longer overwrite an interruption error.
- Initial media run: one passed, one failed (one of the short red marks missing).
- Expanded browser run: thirty-three passed, two failed (startup flash and an
  old UI count expecting only video buttons, before sync recordings existed).
  The revised count still requires two original video takes and now separately
  requires their two sync recordings; original media-hash checks remain intact.
- Timing recheck: two passed, one failed at the unchanged 250 ms timing bound.
- After exact-frame reuse: eleven passed, covering measured media, clock-stop
  recovery, all eight genres and actual rig animation.
- Final targeted application run: thirty-five passed; one additional test failed
  because its spy patched a Three.js prototype method that the renderer installs
  on instances. Replaced the blind spy with observations of actual native WebGL
  draw calls. That same pixel-equality/new-frame test then passed separately.
- Final Node recording/sync/archive/audio checks passed; see the saved log for
  the exact case count.

Full-suite integration baseline finished on local `aacf59d` / published
`f997d541`: **2,328 passed, six skipped, zero failed, sixteen subtests passed**,
217 warnings, 921.01 seconds, exit zero. All current recording, clacker,
frame-reuse and camera-pool checks passed. The skips are two disabled Alex
research modules, three real speech-model cases and one optional decoder
dependency case. Final Node recording/sync/archive/audio checks: 37 passed.

No failed run is relabeled as a successful one. Earlier pool performance
failures stay recorded; this pass does not certify physical-device performance.
This is a pre-profile/group integration baseline, not either required
post-feature debugging round.

The raw full-suite log/XML were copied into this directory locally but were not
published before the environment became unavailable. The summary above was
directly observed. See the session-ending handoff and profile recovery record
for the exact interruption state and the unpublished profile work.

## Reproduction

Use the repository's `.venv` after installing `requirements.txt` and
`requirements-dev.txt`, and real Chromium plus FFmpeg/FFprobe. In this environment
set `PLAYWRIGHT_NODEJS_PATH` to the installed `node` executable; the bundled
Playwright Node executable is not executable here.

Targeted command:

`python -m pytest -q tests/test_clacker_recording_browser.py tests/test_studio_actor_frame_reuse_browser.py tests/test_recording_integration_browser.py tests/test_participant_audio_browser.py tests/test_studio25d_capture_browser.py tests/test_studio25d_archive_browser.py tests/test_production25d_browser.py`

Whole-suite integration baseline: `python -m pytest -q`.

Actual media tests decode the real saved WebM with FFmpeg, identify pulse onsets
and red video frames, compare their production-clock offsets, check no reference
leaks into Program, and verify all original recovery/voice/authorization behavior.
Oscillators in participant tests replace physical microphones only. Hardware,
Windows/PowerShell 5, other physical devices, cross-host guest identity and
long-session acceptance remain open.

