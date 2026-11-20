# PubCast main-repository debugging, November 19, 2026

Work started from `main` at `c82069b47b04eac56cca1fb4f6a4eb16c44d32ae`. Repairs are on `codex/main-debug-20261119`, [draft PR 15](https://github.com/whatsupjosie/Beyond-October/pull/15).

## Recording acceptance

The original Linux Chromium 141 / SwiftShader run delivered increasing amounts of genuine encoded media every minute. At minute 22 the page had delivered 827 nonempty MediaRecorder chunks. Before minute 23 Chromium reported `Page.evaluate: Target crashed`. The original page held every chunk in RAM until Stop. There was no completed take to reopen. The crash's cause remains undetermined.

The replacement journals each chunk and its take metadata in the same IndexedDB transaction. Finalized recordings can use the journaled chunks without storing a duplicate media file. Existing single-blob takes remain readable. Until a take is finalized, the gallery labels journaled media INCOMPLETE. Only committed bytes are recoverable.

**Actual crash acceptance passed.** The test waited for committed bytes from at least 2.5 seconds of capture, deliberately crashed Chromium's studio tab, opened another tab on the same origin, found the partial take, played the 1280-wide video, downloaded it and decoded a frame using FFmpeg. The isolated regression finished in 20.56 seconds. It uses `tests/test_production25d_browser.py -k crashed_studio`. This verifies tab failure recovery in the same browser profile. It does not establish power-loss recovery or a complete 30-minute recording.

The first post-fix endurance attempt timed out waiting 30 seconds for the first nonempty chunk. A diagnostic run then observed normally increasing journal bytes and completed successfully. A further 30-minute attempt reached the one-minute checkpoint before the execution environment disconnected. Its final outcome was unavailable. **30-minute acceptance remains open.** Run `python -m pytest -qs tools/acceptance/studio_long_take.py` on a new checkout with Chromium, FFmpeg and ffprobe. Set `PUBCAST_EVIDENCE_DIR` to retain the export. Have it running in a foreground tab, and record measured frame rate and audio presence independently of elapsed time.

## Reproductions and corrections

| Area | Observed defect and check |
|---|---|
| Timeline transport | A loaded timeline was rejected on Play, pause and resume were not awaited, and seek called a missing method. Repaired transport, monotonic timing, event parameter dispatch and critical cue failure. Verified actual camera changes in a running host. |
| Timeline recording | Timeline cues could operate on recording metadata or stop a competing operator's take. A real timeline start/stop produced a 1920×1080 H.264 file from the virtual test source. ffprobe identified the stream and FFmpeg decoded a frame. The other operator's countdown survived. |
| Server capture | PANIC could reach persistence before stopping encoders. A disk fault, concurrent start/stop, and registration retry now have regression coverage. Camera pause previously changed only metadata. The POSIX test saw the real FFmpeg process enter the stopped state, resume and finalize readable media when stopped while paused. Unsupported active-encoder suspension returns an error. |
| Recording preservation | A failed metadata write could publish an in-memory change. External same-named tracks could collapse or disappear after restart. Verified distinct source bytes, restart, bundle relink and retry after simulated disk failure. Already lost historical bytes require an original source for recovery. |
| Multi-camera partial capture | With a real wide encoder and a missing file-camera input, the prior Stop response omitted all indication of the failed source. After repair the good media decoded, the result identified the exact missing camera, and that failure survived service restart. 30 focused recording, console and timeline tests passed in this round. |
| Output filename collisions | Three source IDs normalized to just two paths, and an existing output could be overwritten. The regression reproduced this before repair. The candidate allocates unique output names and supplies FFmpeg with its no-overwrite option. The execution host disconnected before the post-fix run. The two console HTML changes passed JavaScript syntax checks. Verify partial-failure display in both running consoles. |
| Camera configuration and playback | Both advanced-camera managers failed the save/reload round trip. Fixed persisted IDs, enums, and automatic switching rules. Scripted mode could replace a recorded move's final pose on the next frame. Browser regression now advances extra rendered frames before checking the ending pose. |
| Walkable studio | In an intermediate full run the host restored the room and character with an empty avatar selection. The repair serializes writes and retries the newest selection, and preserves the saved library choice while trying a demo avatar. 25 targeted browser/host/camera checks passed. A separate delayed-write harness verified one write in flight, newest selection wins, and recovery after a failed write. The final test assertion now polls the host directly. |
| 2i writing and bridge | A 40-edit browser burst advanced the IndexedDB revision 41 times. The regression checks one durable revision containing the final manuscript. Firefox's 15 file-workspace tests passed. The signed-in character bridge now uses the real owner and handles missing bots and Pete's genuine offline reply. |
| Rust renderer | The shipped executable acknowledged a dropped frame at avatar capacity and ignored the port supplied at launch. Rebuilt the Linux x86-64 renderer. With capacity one, the acknowledged sequence was success/frame 1, failure/frame 0, success/frame 2. The command-line port superseded the environment setting. The authenticated two-camera control probe passed and correctly reported no rendered frame-path proof. |

## Scope of executed checks

- The initial root Python run reported 2,245 passed and 11 skipped. A later intermediate run reported 2,251 passed and 11 skipped. They are not final-head results.
- An intermediate speech-enabled full run reported 2,263 passed, two skipped and one failure waiting for browser dialogue playback. A separate real speech run passed all 14 tests, including generated Kokoro audio, recorded dialogue and exact-text Whisper recognition. The full run also exercised the five browser cases skipped in the initial environment. A later full run exposed an intermittent Counter layout/restart failure. Obtain the exact assertion and repeat it before treating the Counter as verified.
- 74 root Node tests passed. Seven 2i bridge tests passed against a running host. The offline 2i DOCX build and dictionary checks passed. These do not establish 2i beta acceptance.
- The canonical Rust crate passed 23 library and nine renderer tests. Both recovery crates compiled and had zero tests. The historical Run 3 manifest lacks its own source directory. The optional full-animation system remains outside the default Rust build.
- The standard clean-room sandbox checked syntax for 372 Python files and 64 JavaScript files, booted the launcher, ran 33 backend and 39 browser tests with four optional browser skips, and exercised Blender 4.3.2. The imported GLB had two meshes, one armature and 3,942 vertices. Separate checks exercised the optional browser paths.
- The opt-in Alex research suite passed 137 tests. A 16-turn AlexCore fixture reloaded a baseline with 16 observations. This shows execution and persistence, not accuracy of an emotional reading. Other out-of-directory camera, twin-engine and wired tests yielded 7 and 28 passes respectively.
- A clean isolated installation of the base, developer and speech requirements passed dependency consistency checks for 77 packages. Undefined-name checks for the principal Python application directories passed.
- Default repository suites and focused runs overlap. Their counts should not be summed. No single all-green run of the final PR head is claimed.

## Continue from this branch

1. Recheck the filename-collision test and visual source-failure reporting first. Repeat crash/reopen, storage quota, partial-save, PANIC and multiple-take tests together. Exercise legacy single-blob recordings in the upgraded database.
2. Complete the 30-minute real-time recording on an isolated worker. Reopen the saved media, export, check packet span, and decode frames near the beginning, middle and end. Report actual frame cadence and any audio stream.
3. Reproduce the Counter layout/restart failure and speech playback timeout on the final source, isolate timing from application state, then rerun the full suite on a clean checkout with installed optional speech models and the supported Chromium.
4. Physical phones, camera/microphone sources, independent multi-device audio/video sync, real Resolve import, Windows packaging and the source-complete 4K replay master still require their own acceptance evidence. Work on this branch has not been merged or deployed.
