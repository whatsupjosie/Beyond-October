# Original encoded studio takes: server preservation and recovery

Initial implementation: `e131e649a0d62d44cf9abe9a3223d3f093a832d9`.
Capture-clock correction: `ea16d3d843f90681b02b4dfb9fde2c9e2bdca7cd`.
Final ownership/streaming implementation:
`26211a946628c34f0a23339b0ceca03520bb7049`.
Final source tree: `085d403dc4bee239051f9fbfa4392c7295bd396a`.
Branch: `lead-engineering-control-room-tv-studio-2026-10-31`.

**A completed local studio recording can now be saved on the server, resumed after
an interrupted upload, reopened after server/browser restarts, and exported with
its original bytes and session metadata.** Local recordings remain intact.

This connects actual encoded Program video and audio to the existing
RecordingService. It does not promote JPEG confidence frames into a recording,
change the canonical camera switcher or create a second program-audio mixer.
It archives the browser Program proxy; it is not a replayable 3D shoot master.

## User workflow

1. Start a studio production and record a take. Stop recording and select the
   saved local take under **Session recordings**.
2. Choose **Save selected take on server / retry**. This is an explicit action;
   there is no automatic media upload. A production role is required to reserve a new take; existing takes remain
   accessible to their authenticated creator when their production role changes.
3. The page reports confirmed byte counts, then validates the assembled video.
   **Saved on server** appears only after a validated durable completion receipt.
   Pause stops local transfer. Downloads use a bounded wait for headers and a
   per-read inactivity deadline, so a progressing large transfer can take longer
   than two minutes. Gzip transport lengths are kept separate from original bytes. A lost response leaves the save unconfirmed and
   the local take available. Retry resumes from the server's committed position.
4. **Refresh my server takes** discovers recordings for the current account.
   A fresh browser with no local sessions can open and play a completed take,
   download its original media, or download a source ZIP through RecordingService.
5. An unfinished upload can be ended explicitly. Its source pieces are retained;
   that reservation stops accepting new chunks and no longer consumes a pending slot.

Server transfers are kept out of active capture: saving requires a stopped
recording; an upload must be paused before another take starts. Starting capture
cancels a pending server download. The browser's existing offline recording path
continues to work without a server save. Upload retries resume confirmed server
progress; canceled downloads can be requested again, but partial download buffers
are not retained between requests.

## Architectural decision

| Path | Assessment |
|---|---|
| One POST containing the entire finished video | Simple, but interrupted large uploads restart from zero and ambiguous acknowledgments risk duplication or false success. |
| Resumable numbered chunks of a completed take | Implemented. Bounded requests, immutable source pieces, durable progress, safe retries and exact reconstruction fit the existing recorder and RecordingService. |
| Live encoded ingest / WebRTC capture during production | Still required for stronger in-progress preservation and live multi-source production. It needs capture journaling, media/clock ownership, backpressure, crash recovery and independent tracks; a completed-take archive does not substitute for it. |

The dedicated router is `modules/studio25d_recording_ingest.py`, attached in
`main.py`. RecordingService owns session creation, the final artifact/receipt
commit, restoration, portable source export and import. SQLite files are portable
interprocess mutexes; recording metadata remains the canonical catalog.

## Data and failure contract

- Each take is owner-bound with an opaque ID derived from authenticated identity
  and client take ID. Conflicting content/metadata for that identity is rejected.
  The camera label identifies the initial Program view; cuts remain in the
  client event manifest. This file is the composited Program, not independent
  footage from every camera. Studio labels are historical provenance; saving after restart does not
  require recreating a live camera or alter its Program state.
- Requests carry at most **256 KiB** of media. The current take limit is **2 GiB**.
  Chunk lengths/order and SHA-256 are checked before commit. Identical retries
  return committed progress; changed bytes at an occupied index are rejected.
- Capture start/end stay separate from upload start/completion. The selected
  take's original timestamp is retained even when an older take is uploaded later.
  Production-relative and legacy timing are supported; missing/ambiguous capture
  clocks are explicitly marked unknown. No timezone is guessed.
- A chained manifest binds chunk hashes, sizes and order. The browser persists
  an immutable upload specification separately from the growing local session.
  Resuming skips confirmed chunks and retains the original metadata snapshot.
- A piece is synced and published before the progress JSON is atomically synced.
  A retry repairs a crash between those two commits without rewriting the piece.
  Per-take locks serialize competing writers. Final media and its validated receipt
  are published through RecordingService. A failed metadata commit is retryable.
- Assembly recomputes the chain and complete source SHA-256. FFprobe checks the
  actual container/stream dimensions; FFmpeg must decode a first video frame.
  Invalid media remains an unfinished upload with its pieces retained. These checks
  do not certify every frame of a long recording.
- Server playback verifies stored bytes against the saved hash. The browser also
  checks the downloaded chunk proof. Export compares the exact archived source
  against the committed receipt. Matching original-container export performs no
  conversion or upscale; optional other-container derivatives remain separate.
- Uploaded takes are private to their creator across both the new API and older
  recording/export/action routes. Reading, source export and resuming a reserved
  take depend on ownership, not the creator retaining a production role. A role
  without production privileges cannot reserve a new take. The client also stops
  a save if the signed-in account changes. Imports bind access to the importing operator
  before publication while retaining the original operator as provenance.
- JSON, body read times, pending reservations and decoder concurrency are bounded.
  Disk errors/capacity failures cannot generate a saved receipt. Original pieces,
  completed originals and browser copies are not automatically deleted.
- Local IndexedDB version 2 adds a separate upload-receipt store. Version 1
  sessions/media are preserved. Blocked/version-change connections close cleanly;
  legacy takes without a separate take ID are normalized without replacing bytes.

## Executed verification

| Check on the final implementation | Observed result |
|---|---|
| Final backend/browser acceptance plus portable-recording regressions | **38 passed**: 17 dedicated backend cases, two browser journeys, 15 portable-recording regressions and four API-compatibility checks |
| Focused Node archive/async/guard/confidence/studio checks | **37 passed**, including nine archive protocol/cancellation/streaming cases |
| Existing `npm run test:node` | **9 passed** |
| Existing `npm run test:camera-pool` | **18 passed**, overlapping the focused Node checks |
| Dependency consistency | `pip check`: no broken requirements |
| First complete repository Python suite on `e131e649...` | **2,215 passed, zero failures, two disabled research tests skipped**, 658.18 seconds |
| Complete Python suite after clock correction on `ea16d3d8...` | **2,218 passed, zero failures, two disabled research tests skipped**, 668.31 seconds |
| Final complete repository Python suite on `26211a94...` | **2,219 passed, zero failures, two disabled research tests skipped**, 663.48 seconds |

The real browser creates an actual 1280×720 Program take using loaded bundled GLBs
and a controlled 440 Hz signal through the established mixer. The server commits
a chunk, the test deliberately loses its acknowledgment, then the host restarts.
The browser reloads, resumes without resending that chunk, and finishes validation.
The first browser is closed; the server restarts again. A completely fresh browser
with **zero local sessions** discovers the saved take and plays the actual video.
Its downloaded ZIP contains the exact original media bytes.

`verified.json` records the retained video's exact byte length, source SHA-256,
original capture time, separate upload time, decoded audio RMS and tone frequency.
The actual 1280×720 take contains a strong approximately 440 Hz signal after the
archive round trip. This proves preservation of that controlled signal, not
physical speaker output or multi-client continuity. The fresh reader uses a valid
viewer-role token for the same owner, proving that media access does not require
continued production privileges. Host restarts use the same disposable data and
fixed test signing secret.

Backend negatives exercise ownership, legacy-route privacy, duplicate concurrent
requests, changed chunks, wrong order, incomplete media, tampering, disk pressure,
failed piece/final metadata commits, abandonment, discovery by a second service
instance, bounded/non-finite input and malformed imported metadata. The browser
also migrates an actual version 1 IndexedDB fixture, preserving its original bytes.
The migration fixture uses synthetic byte-preservation data; the separate capture
case supplies the actual playable video/audio proof. Phone-layout controls are
checked at 390 px with 44 px minimum targets.

The clock audit found that original timing survived inside the client manifest
but the canonical summary used upload time. All three new delayed-upload clock
assertions failed before correction. They now pass with an absolute tolerance
of one microsecond (zero relative tolerance), including older-take selection,
production offsets and legacy single-take metadata. Exported summary timestamps
match the actual browser take; transfer lifecycle timestamps remain separate.

Development failures and corrections are retained under `evidence/encoded-take-ingest/development/`:
an HTTP test supplied a bytearray instead of bytes, a legacy test double lacked
the service's lookup method, a zero-crossing tone estimator was replaced with a
spectral measurement, and the migration fixture was given its required login.
The final acceptance tests pass; overlapping runs are not additive totals.
The ownership audit also reproduced a 403 when an authenticated creator with a
viewer role tried to read their existing take. That policy is corrected without
allowing that role to reserve new takes. Stream tests exercise slow progress,
stalls, same-size corruption, gzip lengths and an account switch before upload.

## Remaining production gates

Capture still becomes a recoverable local take at Stop. A browser crash before
that commit can lose an in-progress recording: live capture journaling/ingest is
still a critical next step. There is no new promise of live broadcast transport,
independent camera coverage, participant audio streams or separate source stems.
Blackbox receives an artifact witness/hash; full shoot-media integration is open.

Scene/asset-complete replay, exact animation/prosody, authoritative clacker timing,
selective native 4K rendering and external finishing round trips remain open.
Camera pooling still shares low-rate previews only. Server source pieces plus the
assembled original currently use roughly twice the media size, before exports;
retention and aggregate per-owner quotas need their own product policy.

This is one Linux/Chromium/SwiftShader host. Physical phones, Safari/MP4 capture,
long takes, modest-device performance, separate machines/networks and server
deployment capacity still require acceptance. Per-take disk locking does not
implement live multi-server/switcher federation; the wider runtime still needs
its own deployment and multi-worker acceptance. FFmpeg/FFprobe must be installed
for server saving; browser integrity checks require HTTPS or localhost. No new
provider credentials are needed for this path.

Code/evidence remain local. The prior GitHub publication approval boundary remains
in force; nothing was pushed, merged, deployed or sealed.

## Subsequent local capture journal

`ACTIVE_CAPTURE_RECOVERY.md` describes implementation `26aabe64...`, which adds
local before-Stop checkpoints, interrupted-take recovery and startup cancellation.
The open before-Stop statements above describe this archive implementation's
original scope. The later journal preserves committed chunks on the originating
browser profile; server ingest during active recording and independent source
media remain open.
