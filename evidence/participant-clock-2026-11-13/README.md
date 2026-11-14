# Participant clock compensation candidate

Tested code: `f6004e6` locally, `dda3603` on GitHub. Both have tree `c1f4970d069fb710beba00b182d86467e977677d`.

## Baseline and repair

Sender instrumentation reproduced receiver underflow by minute five with zero missing input blocks in either sender's observed render span. The failing receiver's supply averaged about 44,005 samples per 44,100 receiver frames over its final 55 sampled audio-clock seconds. Relative rates measured in this browser run do not establish physical-device behavior.

The candidate applies bounded, queue-controlled fractional-rate conversion on the existing receive worklet. It preserves the existing ordered PCM transport, 500 ms startup lead, 1.5 s capacity, and explicit failure if audio runs out. Correction is capped at ±0.5%. It uses a windowed-sinc filter and exact pass-through at unity rate and integer phase.

Independent review rejected the first linear-interpolation candidate on measured high-frequency loss. The reviewed replacement passed seven Node cases, including both simulated drift directions and a fractional-delay comparison at 18 kHz. Independent review found near-Nyquist rejection and arbitrary-phase quality still need broader verification. The existing pre-fader stems contain host-aligned received audio after clock compensation. Sender-native recording and a persisted clock mapping remain open.

## Browser endurance evidence

The existing 1,800-second test passed in Chromium 141 on Linux with SwiftShader and generated audio from independently admitted guest processes. Both guests remained present at every minute sample. The planned minute-15 sender suspension triggered a disconnect, then explicit rejoin while Program remained active. The result spans 1,805.170 seconds by encoded packet timestamps. Program reopened after reload with the exact SHA-256 of the downloaded original. The saved session contained three complete voice segments and a complete sync-reference track. The test recorded 121 audio and 121 visual clacker marks in session metadata. Those counts do not establish encoded pixel alignment.

In a separate decode of the saved Program, all 1,805 one-second windows contained energy above the configured floor within ±8 Hz of both generated tones. This test tolerates small frequency shifts from clock compensation and does not establish sample-exact continuity. The result and method are in `decoded-coverage.json`. Raw logs and generated media are in the workspace under `recording-run/bandlimited-work/`.

The result covers Program and guest-audio endurance in this environment. Physical microphones, full-band filter quality, sender-native recording, long-run encoded clacker alignment, Control Room REC hotspot integration, and actual Resolve import remain open.

Focused browser regressions on the same code: 11 passed. This includes participant mix/stem export, admitted-guest recording, clacker, interruption recovery, immediate PANIC, and the loopback transport timing check. The loopback check uses a wall-clock offset and is separate from audio sample-clock drift coverage.
