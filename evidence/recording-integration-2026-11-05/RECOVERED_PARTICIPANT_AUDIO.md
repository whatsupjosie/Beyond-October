# Participant audio integration — November 1, 2026

Recovered work surface: `PubCast-2026-11-01-capture-recovery.zip`, Library
`libfile_7f7c0da286148191bcc5d0dd8eb7e477`, original upstream checkpoint
`3a60a29c129e2a6e03ed8c08f5dd82bbf8883cb6`. This local Git baseline preserves the
ZIP's source; it does not reconstruct missing upstream Git history. Nothing has
been pushed, merged, deployed or published.

## Architectural decision

Three approaches were evaluated against the existing canonical mixer and durable
capture journal:

1. Browser WebRTC contributions and authenticated signaling. This was implemented
   first, then rejected for this slice after a real Chromium probe stalled ICE
   gathering (no candidates) in this environment. Adding test flags did not
   establish a media route. No simulated RTP or passing network mock was substituted.
2. Bounded mono PCM over authenticated same-origin WebSockets, reusing the existing
   Blackbox PCM AudioWorklet. Chosen after the repro: reliable ordered frames,
   native device conversion to the host sample rate, fixed 500 ms PCM reserve,
   sequence checks, explicit underflow/overflow disconnect, upload backpressure
   and one-second bounded server forwarding. No second program mixer. This costs
   about 96 kB/s per 48 kHz mono source before transport overhead.
3. A separate SFU/server mixer. Deferred: adds deployment and mixing ownership
   before the canonical desk path is accepted.

The WebRTC implementation was removed. PCM is the real transport, not an
undocumented fallback or claim of low-latency Opus/SFU operation.
The local microphone previously entered a separate recording-only graph after
program audio. It now enters the same dialogue input graph as remote voices.
Inputs branch into an independent source stream before three-band EQ, fader,
mute and solo, then enter the existing dialogue bus/master/capture destination.
All existing music/SFX/VTR/room paths retain their canonical bus ownership.

## User path

Start a production, open PARTICIPANT AUDIO, and copy its invitation. A signed-in
participant opens it, consents to contribution and separate recording, then grants
microphone permission. The participant can disconnect at any time. The host gets
individual meters, level, mute, solo and low/mid/high EQ controls. Headphones are
needed when monitoring live microphones. There is no return program audio or
participant-to-participant transport in this slice.

Start recording to retain Program plus every live voice. Late arrivals and
reconnections get independent segments. Sources appear as VOICE entries beside
program takes. Select one to play, download original bytes, save resumably to the
server, or obtain its portable source archive using existing controls. Download
the session manifest for `parentTakeId`, source identity and production-clock
`offsetMs`/`startedAt` metadata. Inputs/mix changes are also production events.

Each source uses the existing ordered SHA-256 IndexedDB journal, lease and
backpressure stopping policy. Sources with a crashed/interrupted encoder appear
in the recovery list and are explicitly INCOMPLETE. They never become fabricated
complete program takes. Local originals are retained after server saving.

## Deliberate boundaries

- Transport is authenticated same-origin WebSocket PCM, not WebRTC. HTTPS/WSS
  is required outside localhost for microphone permission and secure transmission.
  There is no third-party STUN/TURN dependency.
- This shares the existing in-process camera architecture: one application
  worker. Reservations expire after 20 seconds; sockets have heartbeat/receive
  deadlines. A server restart closes the ephemeral invitation; reopen and
  reconnect with fresh consent. No unattended auto-rejoin of a microphone.
- Playout starts after a 500 ms PCM reserve, and disconnects an affected source
  if its audio clock underflows or its queue exceeds 1.5 seconds. This preserves sample order without silently
  dropping or speeding up voices. WAN jitter/long-term device drift still require
  physical testing; this is not a general low-latency conferencing service.
- Independent source bytes are the receiver's pre-EQ/pre-fader voice encoded by
  MediaRecorder. They preserve isolated voices through program mute/solo; they
  are not lossless original microphone PCM or sender-native encoded packets.
- Production clock metadata describes capture segment starts; sample-accurate
  cross-device audio/video synchronization and drift correction are not claimed.
- Physical devices, real microphones, background throttling, long takes, quota,
  power loss, WAN jitter and acoustic echo remain separate acceptance work.
- This does not complete replayable 4K source masters or an external finishing app.

## Current verification

Evidence and repro/fix results are appended after actual runs. Historical 2,227
passes at the recovered checkpoint are not treated as this branch's test result.

### Executed milestone and audits

- Focused acceptance: 30 passed, zero failed, one dependency deprecation warning,
  58.95 seconds. Real backend, Chromium 141.0.7390.37, two participant browser
  contexts, FFT gain/mute/solo/EQ checks, disconnect/rejoin segments, isolated
  decoded 440/880 Hz stems, original-byte server ZIP, renderer crash and SHA-256
  source recovery, canonical local mic, canceled late permission and dressing-room
  teardown. Command: `python -m pytest -q tests/test_participant_audio.py
  tests/test_participant_audio_browser.py tests/test_studio25d_recording_ingest.py`.
- Earlier preservation checks: 26 passed across original studio and active
  capture browser suites, plus signaling checks at that intermediate revision;
  24 baseline audio/ingest checks passed before edits; Node's existing
  `npm run test:node` passed (9 entries). Broader final results follow separately.
- Adversarial audit: no media IDs, successful JSON, test tones or confidence
  frames are presented as a network audio implementation. Oscillators replace
  physical microphone waveforms only; relay, mixer, capture, crash and decoding
  are exercised. Raw stems remain separate from processed Program. No claim of
  lossless sender capture, sample-accurate A/V sync or physical-device acceptance.
- Repro/fix audit: actual WS requests uncovered an inherited HTTP-only router
  dependency (fixed with HTTPConnection). Dialogue mute previously invoked every
  external stop hook: a separate input-session stop registry now closes transport
  for Stop All/PANIC while mute retains source recording. Stale microphone grants
  cannot close a newer contribution. A 250 ms lead underflowed during browser
  setup; 500 ms lead is explicit. A late source now disconnects independently
  instead of closing other participants. Crash recovery merges existing recovered
  voice metadata when reconstructing Program, preventing stem loss.
- Cross-system audit: source bytes pass through the existing RecordingService,
  durable chunk receipts, owner authorization, decoder validation and portable
  original-source archive. Voice capture timestamps remain distinct from upload
  timestamps. Existing video dimension/first-frame validation remains required.


### Wider-run repros and corrected transport

Frozen implementation `29373ae`: full pytest run returned **2,237 passed, 3 failed,
2 disabled research modules skipped**, 211 warnings, in 823.87 seconds. This is
retained as the actual result, not retroactively reported as an all-pass run.

The three failing nodes were:
- `test_camera_pool_browser.py::test_three_participants_sustain_real_camera_preview_traffic`:
  the iframe Join button was enabled before its script installed its runtime.
  Product fix: keep Join disabled in HTML; enable only after initialization.
  No preview FPS, render budget, consent or quality assertion was weakened.
- `test_frontend_contract_compat.py::test_no_broken_static_api_refs_after_startup`:
  new URL-construction base omitted its trailing slash. Fixed the URL builder;
  no dummy API endpoint or exception to the route contract was introduced.
- `test_participant_audio_browser.py::test_two_peers_mix_controls_separate_durable_stems_and_original_server_export`:
  main-thread PCM scheduling hit its latency bound under studio drawing load.
  A larger delay was rejected as the repair. Dedicated Workers now own sockets
  and directly transferred AudioWorklet ports; a receiver AudioWorklet owns the
  bounded PCM ring on the audio clock. Drawing neither sends nor schedules PCM.
  Sender AudioContexts match the host's declared sample rate; browser-native
  MediaStreamSource conversion handles physical-device rates. No custom cheap
  resampler, dropped samples, periodic clock reset or audio acceleration was added.

Corrective implementation: `8184299`. The focused transport/recording/contract
run passed **34 tests** in 68.69 seconds before final resource-teardown cleanup.
It includes a deliberate **900 ms studio-main-thread busy loop** while both
voices continue, decoded Program silence during bus mute with the separate raw
voice still audible, and a suspended participant audio clock that removes only
that participant. Final broader affected-suite results follow after execution.

Socket closure releases worklet ports and processors. A bounded worker cleanup
timer is scoped to the old worker, so closing an old connection cannot terminate
a newer contribution. All existing capture-journal ownership/backpressure rules
continue to apply.


### Final observed verification

Final implementation `fba3c47` adds dialogue-stop recovery to `8184299`. Stopping
an input closes its contribution; Stop Dialogue closes the desk. Stopping the
local input releases its microphone tracks and updates MIC OFF. Mute retains
raw source recording. Extra recovery checks: **19 passed**, zero failed, in
144.50 seconds, including existing capture cancellation and crash recovery.

The broader affected-suite run returned **78 passed, 1 failed** in 258.31 seconds.
Its sole failure was the camera assertion `reduced == running` under parallel
browser load. Preview FPS and byte checks passed; the resource guard reduced
work and was not bypassed. After the other browser run finished, the exact
unmodified camera test passed **1/1 in 15.26 seconds**, including three real
streams, distinct JPEG bytes, traffic/FPS, release and cleanup. Performance on
physical devices remains an unsealed gate.

JavaScript verification: Node suite (9), camera pool (18), studio/recording/editor
selection (42), all passed. New Worker/Worklet scripts parse. `git diff --check`
passes. Exact installed versions and suite results are in
`evidence/PARTICIPANT_AUDIO_VERIFICATION.json`. The whole 2,240-case suite was NOT
repeated after corrections. Do not turn the initial three failures into a claim
of a final whole-suite all-pass result.

Resume from `PubCast-2026-11-01-participant-audio.zip`, then root
`CURRENT_STATUS.md`. Next work: implement and measure the recorded 15-second
clacker audio/video reference and alignment, then actual devices and long takes.
Keep the 500 ms transport reserve explicit in those measurements.
