# Consent-based camera preview pool — October 31, 2026

Implementation commit: `58e6b008221d96be3112b301cd9c308958b6fa1b`.
Implementation tree: `3ff2ff06cc8995426345bae190174589e4bebbc0`.
Branch: `lead-engineering-control-room-tv-studio-2026-10-31`.

**Historical first implementation.** The subsequent founder-requested review in
[`CAMERA_POOL_REVIEW.md`](CAMERA_POOL_REVIEW.md) repairs correctness defects and
replaces the permissive combined load check with separate sustained lightweight
sharing, real 3D pixel and failure-recovery checks. Use that report and the current
handoff for the latest source and acceptance boundary. Results below belong to
the earlier commit explicitly identified here.

**A working first path now distributes actual camera preview rendering to
consenting session participants and shows measured feedback in the Control Room.**
This is preview sharing, not full-rate distributed broadcast/recording, native
4K rendering, or a completed Twin Engine worker pipeline. Those gates remain open.

## Using the option

1. In the 2.5D studio, load the bundled set/performers and choose **Create preview
   pool from this studio**. This starts a production if needed. The studio remains
   the source of scene snapshots and native local Program recording.
2. Share the invitation link. It opens the existing Control Room. A participant
   signs in, selects **Contribute from this device**, chooses limits and explicitly
   checks consent. The contribution controls run inside the Control Room; an
   inactive/hidden standalone worker page pauses rather than silently spending CPU.
3. The director selects a camera, consenting participant and frame rate, then
   assigns the task. Separate views can be assigned to separate people. The
   participant may stop immediately or change limits, which releases existing
   assignments before any new assignment is accepted.
4. The panel reports the person, camera/task, requested versus achieved frame
   rate, actual received frame dimensions, received frame/byte totals, payload
   upload and relay output rates, named delivery flows, source age, and reported
   UI/render timing with running/reduced/paused state. No CPU/GPU percentage is
   fabricated. Rates use a five-second window and count JPEG payload, not all
   network overhead or the connection's available capacity.
5. Ending the source production closes its pool. Closing a pool invalidates the
   assignments and current pool frames. A failed closure reports that server
   confirmation is missing; fresh-scene expiry independently pauses remote work.

The currently supported task is `camera_preview`, using registered fixed genre
camera views and bundled MakeHuman performers. One canonical CameraManager and
the existing media/mixer authorities are retained. The new allocator is not a
second switcher or audio mixer.

## Participant experience comes first

- Consent is off by default and specific to a session/participant instance.
  Limits cover camera count, per-camera frame rate, camera upload payload and a
  render wall-time budget target. The latter is cooperative scheduling, not an
  enforceable fraction of the machine's entire CPU or GPU.
- Calibration collects 45 UI animation-frame intervals after actor assets load.
  A UI interval over 180 ms pauses donated work for four seconds. Sustained high
  frame delays reduce work rate and the rendering budget; recovery is gradual.
- Three consecutive camera jobs taking over 180 ms hold contributions until the
  participant explicitly applies new settings. An already completed expensive
  frame cannot be preempted: these guards react to measured cost, and do not
  guarantee that every device will avoid its first visible stall.
- A participant separately permits quality reduction. Only then may shared
  previews fall from 640×360 to 320×180, with actor rendering pixel scale reduced
  too. Lower preview resolution stays stable through rate recovery to avoid
  repeated costly attempts to raise quality. Applying new settings permits a
  fresh calibration. The founder's acceptable future 4K→2K tradeoff is a policy
  direction, not a claim that this preview implementation renders either format.
- Outgoing camera payload is budgeted before sending, including attempted sends
  that fail. The server separately validates admitted frame rate and payload
  quotas. A quota failure pauses contributions instead of endlessly retrying.
- No successful contact for four seconds pauses local jobs; a participant's
  heartbeat expires after 12 seconds. A source scene older than six seconds
  pauses jobs and invalidates serving its pool frames. Rejoining requires consent
  again. Stale helper output falls back to the studio's local Preview renderer.
- Program recording stays on the local 1280×720 canvas. Shared preview quality
  does not change that capture size. These previews do not replace source media,
  source-level shoot preservation or the full-quality render/export gates.

## Architecture decision

| Path considered | Decision |
|---|---|
| Reuse the existing distributed/Twin UDP worker implementation | Preserve it, but do not advertise its placeholder media jobs or broken dispatch as production processing. It lacks the necessary bulk media/result path. |
| Build full-rate encoded peer camera streams and a complete replicated scene/asset timeline first | Required for full production sharing, but it needs encoded transport, clocks, backpressure, source recovery and full scene fidelity. Preview JPEGs must not stand in for those gates. |
| Allocate bounded browser camera jobs through the canonical CameraManager and existing real JPEG media route | Implemented as the first usable path. It supports actual views, explicit consent, strict scope, actual media and feedback while preserving local Program capture. |

The coordinator is `modules/camera_pool.py`; it assigns a camera job rather than
shipping executable code. `main.py` attaches it to the existing media router.
`static/camera_pool_worker.js` renders the assigned scene/view and posts actual
JPEGs. `camera_pool_panel.js` supplies the same controls to the television studio,
Director and Control Room. An unassigned view performs no worker rendering.

Grants change on reassignment. Upload authorization is checked before reading
the body and again before committing bytes, so withdrawal/reassignment during a
stream cannot resurrect a feed. Non-operator members can read only assigned feeds
in their own active pool, not arbitrary studio sources. Anonymous access remains
denied even in relaxed development mode. Session membership does not grant
director assignment or global camera-control permission.

## Executed evidence and corrections

Final results are recorded in `evidence/2026-10-31/camera-pool-tests.xml` and
`camera-pool-node.xml`. These are scoped tests, not a new complete-repository test
claim. The earlier broad 2,166-pass run remains historical.

| Final check on implementation `58e6b008...` | Observed result |
|---|---|
| Combined camera pool, real three-client browser, existing studio browser, media, switcher and camera broadcast tests | **52 passed**, zero failures/skips, 140.46 seconds; one existing Starlette deprecation warning |
| Node guard, outbound quota, studio scene/wiring/switcher, confidence publisher/viewer, avatar and mixer checks | **24 passed**, zero failures |
| Downloaded Program take | Actual 1280×720 WebM with a decoded 440 Hz test signal; 54,720 audio samples at 48 kHz, six steady 100 ms windows, minimum RMS 0.079817 |

```sh
PUBCAST_POOL_EVIDENCE_DIR=docs/missions/pubcast-lead-engineer-2026-10-31/evidence/2026-10-31/camera-pool .venv/bin/python -m pytest -q tests/test_camera_pool.py tests/test_camera_pool_browser.py tests/test_studio25d_media_routes.py tests/test_production25d_browser.py tests/test_shared_studio_switchers.py tests/test_camera_broadcast.py --junitxml=docs/missions/pubcast-lead-engineer-2026-10-31/evidence/2026-10-31/camera-pool-tests.xml
node --test --test-reporter=junit --test-reporter-destination=docs/missions/pubcast-lead-engineer-2026-10-31/evidence/2026-10-31/camera-pool-node.xml tests/test_camera_pool_guard.cjs tests/test_studio25d_confidence.cjs tests/test_production25d_core.cjs tests/test_production25d_wiring.cjs tests/test_production25d_switcher_bridge.cjs tests/test_avatar_glb_motion_consumer_node.js tests/test_program_audio_runtime_node.js
```

The real browser case uses three independently authenticated identities and
browser contexts on one Linux host with Chromium 141/SwiftShader. One helper joins
from an iframe in the actual Control Room. All opt in through real UI controls,
receive different named cameras and produce accepted JPEGs with decoded,
differentiated actual scene pixels. The test records a real local 1280×720 Program
take while sharing is active. FFmpeg decodes its controlled 440 Hz audio and checks
for silent 100 ms windows after excluding the first/last 250 ms. This does not
measure physical output latency or exclude shorter audio glitches.

The same case exercises a real UI stall, stopped rendering during protection,
Control Room performance feedback, explicit withdrawal, immediate stale-feed
rejection and pool closure when the production ends. Backend negatives include
missing/false/non-boolean consent, identity/grant theft, over-assignment, FPS and
upload limits, expired heartbeat/scene, lower-limit release, reassignment and
withdrawal while an HTTP body is in flight. Node checks cover baseline/backoff,
recovery, hidden/held work, stable permitted quality reduction, outbound budgets
and unaffected feeds during a delegated lease handover.

Important failures found and addressed during development:

- Pydantic's `Literal[True]` accepted integer `1`; consent now requires an actual
  boolean true.
- A delegated camera's intentional HTTP 409 could start the local publisher's
  global error cooldown and affect unrelated feeds. Only that explicit handover
  response is now excluded from the failure cooldown; no acknowledgment is forged.
- Loading spikes contaminated baseline timing, and a very poor baseline could
  permit a later 450 ms stall. Calibration now follows asset loading and the
  critical pause threshold is absolute.
- Preview freshness initially used download time. It now subtracts server frame
  age, so fetching an old JPEG cannot make it appear newly rendered.
- A one-second recording test stopped before a first data chunk under shared
  software-GPU pressure. Acceptance now waits for actual MediaRecorder bytes and
  verifies decoded media, rather than assuming a fixed sleep proves recording.
- Early stress assertions expected every latest-frame GET to stay successful
  after all helpers had completed their work. That contradicted protective pauses
  and the five-second media lease. Evidence capture now retrieves actual fresh
  media on acknowledged uploads, and stale frames are allowed to expire honestly.

The one-host stress run deliberately exposes contention: some contributors pause
and some feeds become stale. This is not evidence of continuous multi-machine
throughput. Neither hardware GPU speed nor three-machine LAN/Internet performance
is established by three contexts on a shared software-rendered host.

## Remaining engineering and publication boundary

Full-rate encoded camera ingest, independent full-quality tape/source capture,
asset-complete scene replication (including exact gesture/prosody/animation and
camera histories), deterministic replay, true selected native 4K rendering,
multi-device clock/network measurements and physical-device load acceptance remain
open. Custom set images/performer replacements are rejected by this first preview
path rather than silently rendering a different scene on helpers. Pool allocation
is ephemeral; restart ends participation and requires fresh consent.

The code and evidence are committed locally. Automatic approval review rejected
publishing them to GitHub because the engineering request was not considered an
explicit authorization to publish these contents. No bypass was attempted. An
explicit approval to push this working branch, including source and evidence,
is the remaining publication input. Main merge, deployment and sealing are not
part of that push.
Read-only verification after the rejection found the remote branch still at
`c40e92e67b23ee7c6f4a9685c6899e9d2ce3a5aa`; the new local commits are not published.
