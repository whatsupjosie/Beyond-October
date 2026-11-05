# Camera-pool engineering review

Review requested by the founder after the initial preview-pool implementation.
Branch: `lead-engineering-control-room-tv-studio-2026-10-31`.

Reviewed implementation: `58e6b008221d96be3112b301cd9c308958b6fa1b`.
Repairs: `6f28e144e96a4a7e62ffb3f9a327149046eb6e87` and
`a2f269c5f4dfe01859d7db592ad583fd29c27b82`.
Final tested source tree: `383aa7da4217dbdfc212e540f6cf5aa715a5c64b`.

**The review found real correctness bugs and overly permissive acceptance checks.
Those defects have been repaired locally. This remains a preview-sharing system,
with the full production-media gates open.**

## Defects repaired

| Finding | Resulting behavior | Verification |
|---|---|---|
| Releasing an unassigned camera in one pool could invalidate another pool's feed. A delayed release could affect a newer assignment. | A release requires an existing assignment in that pool. Optional expected assignment IDs reject stale releases. | Foreign release returns 404 without changing the JPEG; stale assignment release returns 409. |
| Program promotion left a preview worker's grant alive, and delayed client assignment state could suppress local Program confidence publication. | Canonical CameraManager events immediately revoke a promoted task and its media. Program cannot be delegated and publishes locally regardless of stale assignment caches. | CUT revocation, denied Program assignment and actual remote PANIC JPEG with a deliberately stale client cache. |
| An old scene could upload as current, while unchanged heartbeats needlessly changed the scene version. | Material scene changes increment a version and invalidate existing media. Uploads require that version, checked both before and after reading the body. Identical heartbeats retain the version. | Old images and late old-version uploads rejected; unchanged heartbeats retain frames. |
| Stale directors retained camera reservations and could exhaust pool capacity. Inactive members accumulated. | Six-second scene expiry releases jobs; 60-second director expiry reaps the pool. Inactive membership slots can be reused. Startup/shutdown explicitly own the CameraManager subscription. | Expiry, capacity reuse, removed-camera cleanup and application lifespan reentry tests. |
| Consent could be withdrawn while join was pending; asynchronous asset/encode/upload callbacks could outlive Stop or a new session. | Generation-owned work scopes cancel old operations and discard late replies. A canceled join is withdrawn if its response arrives. Idle participants do not load actor models. | Delayed join reply, delayed GLB response and late encoder callback tests in real Chromium. |
| Encoding, body decoding and image decoding could hang indefinitely. | Bounded operations include response bodies and decoders. Stop/source changes cancel them and release busy state. Legacy stage publishing and Director confidence viewing use the same lifetime principles. | Never-finishing encoder/decoder and cancellation tests; malformed acknowledgments rejected. |
| Quotas could be reset by reassignment. Healthy 2 fps workers could hit server rate limits due to encode/network jitter and unnecessarily back off. | Per-member/source and participant-wide FPS history survives reassignment. Outbound payload is charged before sends; successful ACK time paces the next job. Server consent caps remain enforced. | Reassignment/quota negatives plus sustained three-contributor browser traffic with no protection pause. |
| An already slow UI could admit more camera work. | A baseline above 75 ms refuses work. Recovery requires 45 clean intervals at or below 50 ms. Absolute stalls and repeated expensive jobs still pause or hold work. | Real busy animation-frame baseline admits zero renders, then recovers; deterministic backoff/quality tests. |
| A corrupt or late-decoded image could be presented as usable. View switching could disrupt the source heartbeat; failed close could look successful. | Monitors require a decoded image with matching assignment/version and valid age including transfer/decode time. View, source heartbeat and cleanup have separate lifetimes. Failed closure remains retryable. | Corrupt JPEG, held decode after close, view switch, source production end and failed-close retry tests. |
| Control JSON was unbounded; deeply nested or non-finite data could fail inside validation/error serialization. | Control routes cap streamed bodies at 32 KiB, bound read time and JSON complexity, and reject non-finite values. | Chunked oversize and nested/non-finite negative tests return controlled errors without mutation. |
| New pool controls inherited small native buttons. | Scoped controls have 44 px minimum targets, visible focus, wrapping labels and an internally scrolling traffic table. | Real 390 px viewport assertions and screenshots of the panel and consent page. |

Four principal backend regressions were also run against the original five
relevant modules extracted from commit `58e6b008...`: **all four failed**.
The same assertions pass on the repaired implementation. See
`evidence/camera-pool-review/original-regressions.xml` and the extraction hashes.
Only ephemeral test bearer/grant strings were redacted from that failure artifact.

## What the acceptance checks now establish

The former combined browser case could pass after a few accepted frames even
when all contributors subsequently paused. It did not establish sustained usable
sharing. Its historical recording/tone observation remains recorded in
`CAMERA_POOL_IMPLEMENTATION.md`; it must not be described as a new continuous
three-computer audio/production acceptance result.

The new checks separate these questions:

1. Three authenticated identities and browser contexts, including a real Control
   Room contribution iframe, each render a different lightweight set camera.
   Each must deliver at least six frames, achieve at least **1.4 fps** in the
   measured five-second window at an assigned **2 fps**, remain `running`, and
   supply a decoded **640×360** image to the actual Control Room. The scene
   deliberately has no actors; this isolates allocation, pacing and media flow.
2. A separate worker loads the actual bundled GLB and produces an accepted JPEG.
   The same camera then renders without that actor. Pixel differences in the
   actor region must exceed the threshold; a model merely present in memory or
   a bright set cannot pass. Both JPEGs are retained for inspection. This proves
   actual 3D pixels, not sustained three-worker 3D capacity on hardware GPUs.
3. Fault tests exercise busy baseline refusal/recovery, pending consent,
   encoding/model-load cancellation, failed limits changes, corrupt/late image
   decoding, failed close, independent source heartbeats and Program priority.
4. The actual studio performs CUT and PANIC. With intentionally stale assignment
   state, its remote Program JPEG still becomes black. The source is local, with
   no pool-assignment header. JPEG black is allowed a codec rounding tolerance
   of 3/255 per channel; the observed image was uniformly 1/255.

These run on one Linux host with Chromium 141 and SwiftShader. They do not measure
whole-device CPU/GPU share, physical audio output, three-machine bandwidth or
long-session hardware capacity. Payload rates count JPEG bytes over five seconds,
not total network overhead or available Internet capacity.

## Executed results

| Check | Result |
|---|---|
| Original four regression assertions against extracted `58e6b008...` modules | 4 failed as expected; retained negative evidence |
| Complete Python suite on first repair `6f28e14...` | 2,196 passed, 1 failed, 2 skipped, 635.42 s |
| Related backend/media/switcher/API compatibility checks on final source | 40 passed |
| Real camera-pool browser checks on final source | 13 passed, 67.70 s |
| Focused Node async/guard/confidence/studio/avatar/mixer checks | 33 passed |
| Existing `npm run test:node` | 9 passed |
| New `npm run test:camera-pool` | 18 passed; overlaps the 33 focused cases |
| Complete Python suite on `a2f269c5...` | **2,200 passed, zero failures, 2 skipped, 643.46 s** |

The first full run's sole failure was the static API-reference checker interpreting
the concatenated router base as a complete endpoint. URL construction now includes
an explicit trailing slash; the existing checker passes without exceptions or
weakened assertions. No missing runtime endpoint was fabricated to silence it.

Two development browser failures were test-oracle errors: demanding exact zero
after JPEG encoding (observed uniform RGB 1) and waiting for wording that differed
from the actual assignment-wait message. Their XML is retained separately. The
final browser run passes both corrected checks. Overlapping runs are not additive
test totals.

`npm run test:camera-pool` and the new backend/browser checks are wired into the
existing integrity workflow. This is local executed evidence, not a claim that
GitHub Actions has run successfully. Source was frozen during each full rerun.

## Remaining gates

The earlier Twin/distributed media dispatch and placeholder processors are still
not the production worker system. Full-rate encoded camera ingest, independently
preserved source audio/video, complete animation/gesture/prosody and asset replay,
clock synchronization, deterministic reconstruction and genuine native 4K export
remain open. A 640×360 preview cannot close those gates.

Physical modest computers/phones, three independent machines and networks,
long sessions, contention and measured audio continuity while sharing require
their own acceptance. Cooperative guards can react to an expensive completed
frame; they cannot preempt synchronous GPU/JavaScript work or promise that no
device will ever show its first stall. Custom unsupported scene assets remain
rejected rather than silently substituted. Restart ends this ephemeral pool and
requires fresh consent.

The branch remains local. A previous automatic approval review blocked GitHub
publication pending explicit authorization; this review did not bypass it.
Nothing was merged, deployed or sealed.

Subsequent implementation: [ENCODED_TAKE_INGEST.md](ENCODED_TAKE_INGEST.md)
adds durable server preservation of completed browser Program takes. The preview
pool remains scoped as tested here; live camera distribution and full shoot
master/replay gates remain open.
