# Three-probe synchronization preflight — design review

Owner direction: Josie Curtsey Cobbley. Engineering review: Codex / ChatGPT Work,
2026-11-05 (Los Angeles session). **Design reviewed; this preflight is not yet an
implemented production feature.** Do not confuse it with the implemented fix that
paints a clacker mark immediately on its audio-clock notification.

## Current decision

Proceed with the tested shared-audio-clock marker path and preserve observed
timestamps. Keep three-probe preflight, measured compensation, zero-offset
simultaneous operation and director override as documented options. Their UI and
automatic calibration are not claimed as implemented. Reliability and honest
uncertainty take precedence over an unsupported guarantee.

## Conclusion

The proposal is coherent: spend a small preparation interval to measure output
latencies, then schedule outputs against one future presentation time. There is
one clock and one scheduler. Simultaneous firing is the zero-offset case;
compensated firing uses measured per-path offsets. Auto chooses the parameters,
not a second timing engine.

## Operator workflow

| State | Actual work | Action button |
| --- | --- | --- |
| Preparing | Open the clacker view; warm the real render/audio/encoder paths and satisfy browser activation/device permissions | Not ready |
| Calibrating | Run three isolated test cues through representative paths; collect output timestamps and variation | Not ready |
| Ready | Show selected mode, tested configuration, estimates and uncertainty | Enabled |
| Uncalibrated | Expose missing/unstable measurements or timeout; retain an explicit conservative override | Enabled only after director override |
| Recording | Apply the selected parameters consistently and preserve actual timestamps; monitor drift | No silent mode changes mid-take |
| Review | Compare actual test footage and invalidate calibration if devices/settings/load materially changed | Recalibrate between takes when needed |

Browser audio may initially be suspended until a user gesture. Keep a separate
Prepare / Enable audio control available while Action is disabled; never require
the disabled Action button to unlock the test that would enable it. Once the
browser reports a running audio context, proceed with automatic calibration.
Chrome reference: https://developer.chrome.com/blog/autoplay/ .

Tests must not emit audible blips into Program, flash the live broadcast or activate
physical performer actions. Isolating their outputs must not replace the real
pipeline with a cheaper simulation that hides its latency. Capture path identity,
codec, resolution, sample rate, device and workload conditions with the result.

## Timing and selection

For a planned presentation time T and measured path delay L_i, the dispatch time
is T minus L_i. T must leave enough time after the user's click for the slowest
ready path and a safety margin. Faster live inputs may require buffering; a cue
scheduler cannot send a command before the user has requested it.

Three samples provide an initial estimate only. Retain all three, their median/
mean, observed range and measurement uncertainty. Three samples do not establish
a reliable tail percentile. Prefer simple zero-offset scheduling when actual
output skew is already within the specified tolerance; use measured offsets
otherwise. Unknown paths remain uncalibrated. Mark unstable paths rather than
presenting a precise-looking average as a guarantee.

Separate predictable latency from jitter. Repeated fixed delay can be compensated;
unpredictable stalls require headroom and monitoring. Browser timers are not
hard real-time. Prepared speech/media/animation should be ready before the cue;
a variable-duration generation job cannot be made deterministic by averaging it.

Define the presentation target explicitly: operator preview, audience playback
or recorded media. Measure arrival at that boundary. A function returning or a
canvas being painted does not establish when an encoded frame is presented.
Different devices need mapped clocks and drift checks, not an assumption that
wall-clock timestamps match.

## Validation required before implementation is claimed

- Three tests run automatically after required browser/device permission is ready.
- An early Action attempt has a clear state; no invented readiness or indefinite lock.
- Compare zero-offset and compensated results on the same recorded outputs.
- Verify that timing changes do not reduce image resolution, performer fidelity or
  ordinary frame rate, and that test cues never enter the real broadcast.
- Exercise variable render load, delayed encoding, changed devices, backgrounding,
  interrupted tests, timeout, override and calibration invalidation.
- Keep exact recorded observations and uncertainty alongside chosen parameters;
  verify on native Windows and physical audio/video devices separately.

## Current evidence and boundary

A real decoded recording in the second broad debugging round showed video-minus-
reference offsets of 285 ms and 132 ms. The immediate marker-dispatch repair then
measured 100 ms and 26 ms in its focused test. The same 250 ms regression assertion
was retained. Inside the subsequent full confirmation run, the measured offsets were 8 ms and 90 ms. Those results concern one Linux Chromium setup. They are not a
universal device delay, a lip-sync accuracy standard or proof of this proposed
three-probe automatic preflight.

Primary reference reviewed: GStreamer latency design,
https://gstreamer.freedesktop.org/documentation/additional/design/latency.html .
Its relevant principles are calculating latency before playback, sharing a
pipeline clock and accommodating the slowest live path through buffering.
PubCast currently uses browser media APIs; this reference is architectural
support, not a claim that GStreamer is installed or used by PubCast.

## Post-completion audit clarification — November 6 UTC

The 250 ms assertion is a regression guard for this capture path. It does not establish single-frame alignment at 24/25/30 fps, millisecond accuracy, a universal lip-sync tolerance or a guaranteed maximum latency. Observed values must remain labeled by run/device/load. A shared audio clock gives exact reference cadence on that clock; the main-thread video/encoder observation can still lag. Automatic calibration and compensation remain unimplemented design options. Full scene-source replay/native 4K and cross-device timing acceptance remain open.
