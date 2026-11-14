# PubCast recording endurance checkpoint — November 13, 2026

## Source and procedure

- GitHub: `whatsupjosie/Beyond-October`. Published `main` was `c82069b47b04eac56cca1fb4f6a4eb16c44d32ae`. The latest published recording branch was `gpt/guest-recording-triage-2026-11-13` at `ffd58a84e2a0038e566998b0fe240b0046c6eb26`, based on Fable checkpoint `764874a`. Its single added change instruments guest-recording test failures.
- Tested source tree `ef3aa55e83ee1f9959974b5f1f47d6f9a82620fc`, clean at launch, in local branch `gpt/recording-endurance-2026-11-13`. An earlier uncommitted `main` worktree was referenced in conversation but was not found in this environment. The Fable checkpoint describes its own worktree as clean.
- Linux, Python 3.12.14, project requirements, Playwright 1.56.0 pinned Chromium 141.0.7390.37, SwiftShader software WebGL, FFmpeg and FFprobe. All captures use temporary data, software rendering, and generated tones with independently authenticated guest browser processes.
- The Control Room links to the 2.5D Live Studio. The harness opens that same Studio page directly and clicks its production and recording controls. The photographic Control Room's own REC hotspot calls a separate server session action. Its recording behavior is an open integration check.
- Command from the checkout with the local environment and installed browser cache:

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/../.pubcast-browsers" PUBCAST_ENDURANCE_SECONDS=1800 ../.pubcast-venv/bin/python -m pytest -q -s -rs --tb=short --basetemp=../recording-run/endurance-work --junitxml=../recording-run/endurance.xml tools/acceptance/test_recording_endurance.py
```

## Acceptance criteria

Working means passing a component's observable checks. Integrated means operating through the normal UI with its real inputs and consumers. Finished requires all applicable criteria, recovery and regression evidence, and independent review of significant repairs.

| Component | Acceptance and verification |
| --- | --- |
| Controls and state | Start and stop an encoded take through the Studio controls, show actual preparing/recording/finalizing state, report failures, and preserve distinct takes. Verify Control Room entry and separately verify behavior of its REC hotspot with the selected Program source. |
| Program video and switching | Record at least 1,800 elapsed seconds and verify the exported media duration is at least 1,800 seconds. Verify recorded camera order and inspect gaps or freezes. The harness switches the existing canonical switcher, samples journal progress, and probes media duration. Decoded camera order needs its own check. |
| Audio and sources | Decode both independently admitted guest tones in the Program mix near start, middle, and end. Retain independent pre-fader voice segments, including the intentional disconnect/rejoin at minute 15. Exercise separately routed dialogue, SFX, and music with distinguishable cues. The current harness exercises dialogue, and the mixer has music and SFX buses. Separate music/SFX stems and their routing remain to be verified. |
| Clacker | Preserve a dedicated reference stem and keep its pulse out of Program. Verify the 15-second interval and measure encoded red-pixel/decoded pulse alignment. Existing short browser criterion is under 250 ms local audio/video offset and ±20 ms for the observed inter-pulse interval. Apply that local offset criterion at the beginning, middle, and end of the long take. Cross-device drift remains a separate measurement. |
| Finalization and recovery | Normal Stop yields readable media and releases completed journals. Induced interruption retains available bytes and marks the affected take incomplete. A fresh take must start and save without replacing the prior take. |
| Playback, archive, and export | Reopen the take and verify its bytes after browser reload. Verify original archive integrity after server restart and fresh import, preserve track identity and timing through export, and verify actual Resolve import when available. |
| Scene-source replay and native 4K | Existing status is an implementation gap. A complete independent replay package and selective native 4K rendering require their own verification. A Program proxy and a resized canvas are insufficient. |

## Evidence

- Server ingest, integrity, portable bundle, and confidence-feed guard: 36 passed on the tested checkout. The confidence feed is deliberately rejected as a server recording source.
- JavaScript capture, switcher, clacker-worklet, archive, and mixer checks: 28 passed.
- The 1,800-second attempt **failed** at its minute-12 sample (720.464 seconds after the second persisted checkpoint). The mixer dropped to one guest input, before the intentional clock stop scheduled at minute 15. The browser host reported “Participant audio clock stopped or exceeded its buffer”, then “Participant disconnected”. The 440 Hz guest reported lost connection. The 880 Hz guest remained connected, and Program continued writing through harness cleanup.
- Preserved the 37,159,009-byte Program WebM, SHA-256 `00ade393e9213baab915e05664730c2c6cd1f6b35a6d4ec97c25dc28e9ce1953`. FFprobe shows 1280×720 VP9 plus Opus. Last packet end timestamps: video 722.827 s, audio 722.910 s. Largest observed timestamp gaps: video 1.013 s, audio 79 ms. At 361.455 s both decoded tones were near 0.085 amplitude. At 714.910 s the 440 Hz amplitude was 0.00014 and 880 Hz remained near 0.085.
- The WebM has no container duration field. The acceptance test currently requires `info['format']['duration']`, which would fail on a comparable WebM even if the take reached 30 minutes. Measure duration from actual packets as a fallback while retaining the duration gate. The historical test finally block saves Program only, so the first run did not retain independent stems for inspection.
- Local raw evidence is in the sibling `recording-run/` directory: `endurance.log`, `endurance.xml`, `endurance-work/test_thirty_minute_program_two0/endurance.json`, the saved WebM, `partial-media-ffprobe.json`, and `partial-media-decoded-audio.json`. The server test and JS logs are `ingest.log` and `node.log`.

- Browser reruns: 13 passed, zero skips. The admitted-guest Stop failure and clacker timeout from the Fable checkpoint did not reproduce on pinned Chromium 141. The short clacker test measured video 32 ms and 50 ms behind its reference, with pulses 15.000 s apart. Local playback, distinct takes, interrupted capture, PANIC, server restart, original archive export and fresh import, and editor interchange passed the focused checks. Resolve is absent and actual import is still open.
- Controls, short guest audio, the short local clacker, recovery, and browser-to-server archive have scoped integrated evidence. The endurance requirement failed. Decoded camera order, music/SFX stems, long-run clacker drift, Control Room REC hotspot integration, physical media, Resolve and scene-source/native 4K remain open. There was no product code change in this phase.

## First Astra investigation

The receive worklet in `static/participant_pcm_worklet.js` emits an explicit `underflow` or `overflow`. The worker in `static/participant_audio_worker.js` collapses those into one UI message. Capture the actual reason and buffer/clock timing before attributing the dropout to drift, CPU scheduling, or relay. Keep the explicit error path and latency/continuity checks. The evidence shows the missing tone in saved media independently of the UI and test assertion. After a significant repair, require independent review and rerun the full target test. The short admitted-guest test does not substitute for endurance.

## Phase 2 — receiver fault diagnostics (November 13, Pacific)

The retained media proves dropout, but the original error did not distinguish an empty receiver queue from an overfull queue. No audio transport repair is justified by that evidence alone. Added bounded diagnostics without changing the 0.5-second startup lead, 1.5-second capacity, FIFO samples, or explicit fail/disconnect behavior:

- Receiver faults retain `underflow`/`overflow`, sample counters, Web Audio frame times, maximum inter-arrival gap in receiver frames, and twelve queue snapshots spaced five audio-clock seconds apart. Only numeric metadata is retained, never microphone samples. Per-block overhead is two counter/comparison operations; a small snapshot object is allocated every five seconds. No additional IPC occurs before failure.
- The worker attaches packet count and monotonic arrival timings. The host retains the structured result in `PubCastAudioDesk.lastFault` through disconnect/cleanup and resets it on opening a new desk. Console diagnostics exclude peer identity. Worker clock values and receiver frame times are different clocks and must not be subtracted directly.
- `receivedFrames` includes the packet rejected on overflow, while `queuedFrames` excludes it; `incomingFrames` identifies the rejected size. The final gap since the last packet can be computed from `faultAtMs-lastPacketAtMs`; `maxPacketGapMs` covers completed arrival gaps only.
- RAN: Node diagnostics tests — 4 passed, including exact FIFO sample preservation, forced underflow/overflow, bounded history, and fault lifecycle. RAN: real Chromium `test_two_peers_mix_controls_separate_durable_stems_and_original_server_export` — 1 passed in 27.17 s, including new assertions for the intentionally suspended sender's underflow metadata. Evidence: sibling `recording-run/astra-diagnostics-browser.log`.
- UNKNOWN: cause of the minute-12 spontaneous failure. Another full 1,800-second run with these diagnostics is required; this change does not claim to fix the dropout. Independent root source review completed; requested fault-reset and console identity refinements were implemented before commit. Guidance package cache was unavailable (`npx --offline` returned ENOTCACHED); no new browser API was introduced.


## Instrumented rerun — commit `23ed518`

- The second 1,800-second attempt failed at the minute-five sample (300.880 s). The 440 Hz guest had already dropped before the injected main-thread stall; the 880 Hz guest stayed connected. Program kept saving and the harness stopped it for evidence.
- Receiver fault was **underflow**, with zero queued samples. The queue trend fell from about 171 ms to 52 ms over the final 55 sampled audio-clock seconds, then reached zero. The receiver used 44.1 kHz and consumed every frame delivered to it. Maximum observed worker packet gap was 122.8 ms and maximum observed receiver delivery gap was 121.9 ms. At failure the worker had seen one more 4,096-frame packet than the worklet had received. This is evidence of a sustained supply deficit with packet timing variation; sender clock drift versus missing input blocks still requires sender-side evidence.
- The harness retained the Program WebM, two independent voice WebMs, and the clacker reference. It captured the diagnostic and all four files successfully. On this partial take, 20 decoded reference pulses matched 20 encoded red marks, with observed offsets from 5 to 133 ms. This is one local partial take and does not close the 30-minute or cross-device sync gate.
- The app marked the shortened source and the Program take complete. The take can be valid media while its expected contributor coverage is incomplete. Establish explicit coverage status for unplanned audio loss while preserving intentional disconnect/rejoin segments and successful Program finalization.
- Browser probe revisited the photographic Control Room: its 2.5D Live Studio link opens the recorder. Its own REC hotspot on the active Newsroom-wide source returns HTTP 400 (confidence images only) and leaves the Studio recorder idle. Route the operator to actual recording without accepting confidence frames as encoded video.
- The harness now drives camera changes with the visible controls, waits for actual take selection before downloading, and falls back to encoded packet timestamps for duration if WebM omits the header field. A 60-second check passed the packet fallback and reopen/hash checks on the earlier harness revision. The instrumented run exercised the updated failure retention and preserved all four files. Astra independently reviewed the final harness.
- Sibling evidence: `recording-run/instrumented.log`, `instrumented.xml`, `instrumented-work/test_thirty_minute_program_two0/endurance.json`, the four WebMs, `partial-clacker-measurement.json`, and `recording-run/control-room.log`. Resolve remained unavailable. No physical device was exercised.

Next test: add sender-side counters for produced PCM frames, render frames and absent input blocks, and correlate those with packet sequence and receiver frame progression. Confirm where the deficit originates before changing buffering or introducing cross-clock compensation. Rerun the full 30-minute acceptance after any production repair. Preserve original recorded media and explicit failure handling.
