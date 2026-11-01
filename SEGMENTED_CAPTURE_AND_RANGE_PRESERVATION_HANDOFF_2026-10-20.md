# Segmented capture and range preservation — handoff
Prepared October 20, 2026 by Claude, for Curtsey and GPT.
Built against: Foresight_Boot_Integration_Working_Copy_2026-10-14 (october/ tree).

## What this is
Two new modules and one test file. No existing file was changed.

- `modules/segmented_capture.py` records a source, such as control-room audio, into short segments that FFmpeg finalizes one at a time. It keeps a hash-chained index that maps every segment to real UTC time.
- `modules/range_preservation.py` copies a time range (for example, 6:36 p.m. to 8:49 p.m.) into its own file. It never touches the original recording, and every request gets back a receipt saying exactly what happened.
- `tests/test_segmented_capture_and_preservation.py` has 17 tests that run real FFmpeg.

This closes two gaps from the October 20 review:
- **Crash recovery.** The old monolithic MP4 was lost on a crash. Now the worst case is losing one segment.
- **Preserving a range while recording continues.** This was not possible with the old MP4.

## How to install
Copy the three files into the same paths in the october tree. Then add one line to `requirements.txt`:

    tzdata>=2024.1

Windows has no built-in time zone database. Without tzdata, a request like "6:36 p.m. Los Angeles time" fails with a clear error instead of resolving.

## How it behaves

Capture:
- Each segment enters the index only after FFmpeg has closed it. Its size and SHA-256 are recorded at that moment.
- The index is append-only. Every record carries the hash of the one before it, so any edit, deletion or reordering is detected.
- Times come from a monotonic clock, so NTP corrections and daylight saving cannot move them. Each segment's UTC anchor is fitted from FFmpeg's own progress reports, and the spread of those reports is stored as a declared timing uncertainty.
- `status()["recording"]` is true only while media time is actually advancing. An encoder that is alive but producing nothing reports `stalled`. Other states: starting, restarting, crashed, stopped. Use this as the source for the Blackbox recording light. A process merely existing is not proof of recording.
- A crash is recorded as a crash. Whatever is readable from the unfinished segment is indexed as `partial`; anything unreadable is recorded as a `lost` interval.
- Optional bounded auto-restart. Each restart starts a new run, so the gap stays visible.
- If the whole program dies, the next start closes the abandoned run as `interrupted` and indexes any readable leftovers.
- Only one recorder may use a capture directory. An OS file lock enforces this and releases automatically if the process dies.

Preservation:
- **completed** means one verified file covers the whole range.
- **partial** means verified file(s) plus a list of gaps, each with its reason. Separate runs become separate parts; nothing is ever stitched across a gap.
- **failed** means nothing usable was produced, and the reason is given.
- Every source segment is hashed before and after the copy and compared with the index. A tampered source blocks the copy.
- Each output's duration is measured with ffprobe and checked against the expected duration before success is reported.
- Outputs are written to a temporary name and moved into place only after verification. Existing files are never overwritten.
- Format: audio-only AAC becomes .m4a and H.264 with AAC becomes .mp4, both playable on Windows without extra codecs.
- Mode `copy` (the default) doesn't re-encode. Audio is accurate to about 80 ms; video is accurate to the keyframe interval (1 s by default, forced at capture). Mode `exact` re-encodes for sample-accurate cuts.
- If a range runs past what has been recorded so far, the preserver waits briefly. If the end still isn't covered, it returns `partial` with a trailing gap marked "not recorded yet".

Local times:
- A request needs a date; nothing is guessed.
- A time that occurs twice (for example 1:30 a.m. on November 1, 2026) raises `AmbiguousLocalTimeError` with both UTC candidates, so the UI can ask which one.
- A time that never occurs (spring forward) raises `NonexistentLocalTimeError`.
- An end time earlier than the start time means the range ends the next day, and the result says so (`crosses_midnight`).

Blackbox:
- Capture records run start, end, crash and restart as `recording.state` events.
- Each preserve request is recorded twice: the request as `studio.action`, and the outcome as `legal.export` with scope, status, gap count and the export hash.
- Only existing event types are used, so `pubcast_event_adapter.py` did not need changes.
- Per-segment hashes live in the capture index rather than the Blackbox ledger, keeping the witness small as its spec requires. Each run_end carries the index head.

## Wiring steps for GPT (main.py is yours; these are the only touch points)
1. In lifespan startup, create `SegmentedCaptureRecorder` for control-room audio:
   - Root: `DATA_DIR / "blackbox_media" / "control_room_audio"`.
   - Input: `dshow_audio_input(<device name>)`. The device name comes from `list_dshow_audio_devices()` and the saved microphone preference.
   - Pass the existing `blackbox_witness`.
   - Call `await recorder.start()` with the program; call `await recorder.stop()` in shutdown.
2. Create `RangePreserver(root, DATA_DIR / "blackbox_media" / "preserved", source_id="control_room_audio", witness=blackbox_witness, recorder=recorder)`.
3. Add a console action `recording.preserve_range` (safety `confirm`) next to the existing actions:
   - Payload: either `date`, `start`, `end` and optional `tz`, `start_fold`, `end_fold`; or `utc_start` and `utc_end`.
   - Call `preserve_local(...)` or `preserve(...)` and return `receipt.to_dict()`.
   - Map `AmbiguousLocalTimeError` to HTTP 409 with `candidates_utc`. Map `NonexistentLocalTimeError` and `RangeRequestError` to HTTP 400.
   - The route must await the preserver, because `execute_studio_action` is synchronous.
4. Feed `recorder.status()` into the recording indicator.
5. Do **not** add any route that lists, reads or serves files under `blackbox_media`. The narrow channel returns receipts and status only.

## Decisions still owned by Curtsey
- Which media Blackbox must record. This build handles any FFmpeg input; control-room audio is the assumed first source.
- What "save" means. It is not implemented, because its meaning is undefined.
- Retention: how long segments are kept, and when the iteration-wallet rollover is offered.
- Segment length. The default is 5 seconds, which is also the worst-case loss on a hard crash.

## Evidence (run in Claude's Linux workspace, FFmpeg 6.1.1)
Command:

    python -m pytest -p no:cacheprovider tests/test_segmented_capture_and_preservation.py -q

Results: 16 passed on two consecutive runs; after adding the video test, 17 of 17 passed twice. The neighbouring Blackbox suites, run together with the new tests, gave 29 passed. pyflakes reports no problems.

What the tests prove with real media:
- **Content, not just length.** The tone steps 400, 600, 800… Hz every second. The preserved file for seconds two to four contains 800 Hz then 1000 Hz, and the step falls within 60 ms of where it should.
- **Originals untouched.** Hashes match before and after every copy.
- **No overwriting.** A repeated request writes a new file.
- **Crashes.** A killed encoder produces `restarting`, then a new run. Preserving across the crash returns `partial`, with the gap reported and no part spanning two runs.
- **Stalls.** A frozen encoder reports `stalled`, not `recording`.
- **Program death.** An abandoned run is closed as `interrupted` on the next start.
- **Tampering.** An edited index and an altered segment are both detected and refused.
- **Video.** A copy cut decodes cleanly from its first frame.
- **Local times.** The 6:36–8:49 p.m. example, the DST fall-back and spring-forward cases, and the overnight case all resolve correctly.

## PASS / UNVERIFIED
- **PASS (Linux, synthetic sources):** everything listed under Evidence.
- **UNVERIFIED — Windows microphone capture through DirectShow.** The device-list parser is tested only against sample text in both FFmpeg output formats.
- **UNVERIFIED — Windows behaviour of the file lock (msvcrt) and of asyncio subprocess pipes under uvicorn.** These need the Proactor event loop.
- **UNVERIFIED — UTC accuracy on a real device.** Synthetic lavfi input runs a few hundred milliseconds ahead of real time; a real microphone cannot. Device input latency is not measured, and the declared uncertainty covers only progress-report spread.
- **UNVERIFIED — multi-hour soak.** The longest test run was seconds. Run at least the length of a real show before trusting long sessions.
- **UNVERIFIED — mounting in main.py, console action routes, and the indicator UI.** None of it is wired yet.

## Known limits
- In copy mode, video cuts land on keyframes. Use `exact` mode when frame-accurate video bounds matter.
- Preserving hashes every source segment twice. That is cheap for audio and slow for hours of high-bitrate video.
- One recorder per source. Several microphones means several recorders, or one FFmpeg input that mixes them; that is a choice for Curtsey.
