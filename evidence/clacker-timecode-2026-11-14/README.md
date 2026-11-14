# Clacker timecode verification — November 14, 2026

The 30-minute guest-audio endurance test passed on the recording candidate with only an acceptance-harness change. The harness downloaded Program, the isolated clacker WebM, and the actual session manifest from the same take. The encoded Program spanned 1,803.497 seconds. Downloaded Program reopened byte-identically.

- Program SHA-256: `1fcd14b884e4366f16117bd2881917c22e0d740eac706c090e494639f4b6b6ce`.
- Clacker SHA-256: `52e39fe8655a67c29a26ec2d1e183ee6b3d8f4bc12f2a1a80dd7de8ee7f7bffe`.
- Environment: Linux, pinned headless Chromium 141, SwiftShader, two independently admitted guests with generated tones, FFmpeg/FFprobe.
- The analysis measures the first encoded red frame and the decoded reference onset in one-millisecond windows. Each stream is placed on the production timeline using its captured manifest offset. The source is variable frame rate. The 33.33 ms threshold is one frame at the requested 30 fps editorial timebase.

| Mark | Flash after blip | Blip after nominal production time |
| --- | ---: | ---: |
| 1 | 13 ms | 20 ms |
| 61 | 38 ms | 845 ms |
| 120 | 93 ms | 1,560 ms |

120 pairs decoded with no duplicate groups. The manifest logged mark 121 during finalization. Neither encoded stream reached that sequence's nominal production time: the two packet timelines ended near production time 1,814.4 and 1,814.8 seconds, before the 1,815-second mark. Treat this as a take-boundary bookkeeping gap and carry it explicitly in verification.

**The one-frame target failed.** 15 of 120 pairs were within 33.33 ms. Median flash lag was 98 ms and worst was 314 ms. Fits to production time were approximately +894 ppm for audio and +889 ppm for video. Most long-term deviation is shared. The relative flash lag varies across the take. A single fixed offset cannot correct both. The full measurements are in `measurement.json`. The raw synthetic media and exact manifest are in the run directory outside Git.

The existing editor/export core consumed the measured marks and two recorded camera-event times. It emitted two EDL entries and a JSON handoff retaining both track mappings. The fit's maximum residuals were 226 ms for Program and 118 ms for the reference. This checks interchange fields, with visual cut-frame and Resolve conform still pending. All 12 existing editor/interchange checks passed. See `interchange.json`.

## Next repair

Keep the 15-second reference silent in Program, and continue to use the original take and explicit cut events. Define one calibration from capture PTS to production time and persist its uncertainty. Separately measure the main-thread notification, canvas paint and actual encoded frame before changing flash scheduling. For genuinely frame-accurate output, emit the flash against a frame's assigned timestamp at capture or deterministic export. The current canvas path has variable frame intervals and can miss that target even after a clock fit. Trim recorded mark metadata to each track's committed media interval, while retaining later live events separately. Require independent review and repeat the paired full-take measurement before automatic alignment.
