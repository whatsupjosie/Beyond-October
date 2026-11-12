# Active studio recording: local checkpoints and crash recovery

Implementation: `3a60a29c129e2a6e03ed8c08f5dd82bbf8883cb6`.
Source tree: `7baca898546b44d6e8c2c3ca20a94b55b7205072`.
Date: November 1, 2026. Branch: `lead-engineering-control-room-tv-studio-2026-10-31`.

**The studio now saves encoded recording chunks while a take is running. After an
interruption, the operator can recover the committed portion as an explicitly
incomplete take, play/download it, and preserve it on the server.**

The preceding completed-take archive remains described in `ENCODED_TAKE_INGEST.md`.
This change closes its specific local before-Stop gap; it does not implement live
participant media transport or a replayable source-level shoot master.

## Observable behavior

- Recording begins only after a journal reservation commits. Each arriving
  MediaRecorder chunk receives a SHA-256 and is stored in an ordered IndexedDB
  transaction with its capture clock, byte count and session event snapshot.
  The UI reports confirmed local bytes and the latest checkpoint.
- Successfully committed chunks leave the writer's memory queue. The default
  backpressure threshold is 8 MiB or eight pending chunks. Exceeding either stops
  recording and retains the queued data, including the threshold-crossing event
  and final stop event. Browser timeslices are advisory; a delayed single browser
  event may exceed that threshold. This is a stop threshold, not an absolute
  browser-process memory ceiling.
- Normal Stop verifies the journal, combines its original chunks with any retained
  unsaved suffix, and saves the take. Canonical media/session data and the journal's
  completed flag commit in one transaction. A failed save keeps the existing
  recovery download/retry path; committed journal pieces remain available.
- On reopening, **Interrupted recordings** lists unfinished journals. Choose
  **Recover incomplete take** after its active-tab lease expires (15 seconds,
  renewed every two seconds). Recovery verifies chunk order, hashes and length,
  preserves the original capture clock, labels the take INCOMPLETE, and opens
  playback. Original chunks remain intact. A recording with no committed media
  cannot recover media that never reached storage.
- Tab ownership is checked in the same write transaction. An unexpired lease prevents another tab from claiming a take, and a stale owner cannot append or finalize after ownership
  changes. Final completion prevents duplicate recovery. Sessions and completed
  media from IndexedDB versions 1 and 2, including existing server-save receipts,
  survive the version 3 migration.
- Recording setup can be canceled while audio initialization or microphone
  permission is pending. Repeated Start is rejected. PANIC/End Production cancel
  pending setup. A later microphone result is stopped and cannot affect a newer
  recording. Per-attempt resources are kept separate from the adopted recorder.
- The existing canonical Program canvas and ProgramAudio capture output remain
  the source. No new switcher or independent production mixer is introduced.

## Implementation choice

| Approach | Assessment |
|---|---|
| Repeatedly checkpoint the growing complete Blob | Possible locally, but republishes a progressively larger object and makes write pressure and partial replacement harder to manage. |
| Journal native chunks locally | Implemented: preserves original encoded order, supports offline capture, releases committed memory and exposes exact saved progress. |
| Stream directly to the server during capture | Useful for off-device durability, but requires separate live ingest/clock/backpressure contracts and cannot replace offline checkpoints. The existing explicit post-take archive remains available. |

`production25d_storage.js` owns storage and transactional ownership;
`production25d_capture.js` owns ordering, hashing, buffering and verified assembly;
`production25d_app.js` owns recorder lifecycle and operator feedback.
Capture timestamps are set at the actual MediaRecorder start, after reservation,
and persisted with the first committed chunk. Recovery time stays separate.

## Executed checks

`evidence/active-capture-recovery/` contains commands, results, development failures
and real captured media. Tests use the actual backend, Chromium/SwiftShader,
MediaRecorder, browser disk storage and FFmpeg rather than substituting sample video.

- **Eight new browser checks passed**: renderer crash with exact original bytes,
  video/audio playback and server preservation; full Chromium process crash and
  profile reopen; other-tab exclusion and stale writes; pending microphone cancel
  followed by a new take and late result; PANIC during pending permission;
  slow-storage backpressure preserving all emitted bytes; version 2 media/receipt
  migration; stale permission denial ignored after a new recording starts. The permission and slow-disk cases deliberately control those inputs.
- **24 overlapping browser checks passed** before the final seven-case run:
  six new cases plus all existing studio and completed-server-archive browser
  cases. The later seventh case adds the whole-browser process crash.
- **36 focused Node cases passed**, including four new journal cases for byte
  order/memory release, failed-write suffix recovery, backpressure retention and
  refusal of corrupt/missing chunks. These overlap prior archive/pool checks.
- **Full frozen-source regression on `3a60a29c...`: 2,227 passed, zero failures,
  two explicitly disabled research tests skipped**, 740.97 seconds. All browser
  checks ran; no browser case was skipped. `full-python-final.xml` and the saved
  log record that complete execution.

The before probes supply the previous implementation's app script from commit
`26211a94...` to the actual browser. Both fail as expected: after renderer crash,
zero media bytes and zero journal records survive; after Stop while microphone
permission is pending, a late stream starts a recording. Their source and failing
XML are retained. Development-first/second XML record two test-wait defects:
an asynchronous Playwright predicate returned a truthy Promise before a checkpoint,
and a predicate accessed a journal before initialization. They were corrected to
wait for actual committed synchronous progress, without weakening media assertions.
Generated authentication strings are redacted in saved XML.

A subsequent cancellation audit reproduced a denied old microphone request
putting an error over a new take. `late-rejection-before.xml` records that failure;
`3a60a29c...` discards the stale rejection, and all eight browser cases pass.
The first broad run was interrupted for this correction at roughly 45%; it had
printed one F but produced no final failure detail or XML. It is not a passing
suite result. Ordered progress suggested the separate camera-try browser case;
that case then passed alone (10.17 s). This is an inference about the interrupted
output, not a diagnosed cause. The final full run passed on the frozen source and supplies accepted regression evidence.

## Remaining limits and next work

Only committed checkpoints survive a crash. Encoder-held or uncommitted final
material may be lost; recovery never labels an interrupted take complete. A hard
power failure, OS disk loss, eviction of browser storage, private browsing,
Safari/MP4, physical phones and long sessions remain unverified. Strict transaction
durability is requested where supported; this is not a power-loss certification.
Local capture now requires HTTPS or localhost for browser SHA-256 integrity.
Background tab timer throttling can expire a lease; a new claimant fences the
old writer rather than allowing competing commits. The browser profile is the
local-storage boundary, as with earlier local takes.

Original journal chunks and the canonical completed Blob are retained, so local
storage can approach twice the media size. No automatic deletion policy was added.
A quota/write failure stops capture rather than discarding encoded chunks to
pretend the recording remains healthy. Capture journals live on the originating
device; server transfer remains an explicit action after recovery/Stop.

The next production work is real participant audio/video transport with independent
source tracks, measured clock/clacker alignment, complete replay dependencies and
selected native high-resolution rendering. Multi-device performance and every
Control Room station still need commissioning. The studio is unsealed; nothing
was pushed, merged, deployed or offered as a public beta.
