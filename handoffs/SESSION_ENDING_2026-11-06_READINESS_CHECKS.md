# Session-ending handoff — remaining readiness checks

Signed: Codex / ChatGPT Work, November 6, 2026. Branch `chatgpt-work-2026-11-05`.
**State: CHECKS CONDUCTED; READINESS NOT CLEARED.** Passing regression tests below do not override failed or unavailable acceptance gates.

## Gate results

| Requested check | Result | Executed evidence / boundary |
| --- | --- | --- |
| Physical Windows, phone, camera, microphone and GPU | BLOCKED — unavailable | Actual environment inventory found Linux, no `/dev/video*`, `/dev/snd/*` or `/dev/dri/*`, and no native Windows/PowerShell runtime. No connected physical machine control is exposed. |
| Mobile layout / touch recording and reload | PASS — EMULATION ONLY | Chromium 390×844 touch viewport records actual stage output, saves and reopens the same take. This is not a phone, Safari, Android audio or real GPU pass. |
| Virtual peer latency/jitter/skew and failure behavior | PASS — NARROW VIRTUAL SCOPE | Separate Chromium processes, genuinely signed/admitted guest, real protocol/worklets/backend and transparent TCP proxy. Injected 40–160 ms forwarding delays, publisher-page wall-clock skew approximately +120 seconds; over one MB traversed the proxy, audio remained present, and an intentional stall explicitly disconnected that microphone. No physical clock-drift or sample-accurate A/V claim. |
| Long multi-peer continuity | FAIL | Thirty-minute acceptance was attempted, not completed. First run lost both contributor inputs by approximately four minutes while video/journal recording continued. A repeated default thirty-minute attempt lost one input by the first minute; detailed host state identified the receiver's timing-buffer protection. Do not call either attempt a thirty-minute pass. |
| Encoded take → server bundle → fresh data import | PASS — CURRENT ENCODED-MEDIA SCOPE | Actual animated stage recording, raw-byte download, server ingest/export ZIP, new recording data directory, importer and SHA-256 equality. Output is 1280×720 encoded Program, not all original virtual scene inputs. |
| Rough-cut +0.030 s and 24/25/30 fps transfer | PASS — BROWSER / FORMAT CHECKS | Fresh browser imports actual recorded source, applies correction, creates a select, exports actual CMX3600 EDL and full JSON at three rates, preserves exact 30,000 µs in the sidecar, saves/reloads project and exports source bytes unchanged. Actual professional-finisher conform remains untested. |
| Complete replayable scene-source master | FAIL — IMPLEMENTATION GAP | Inspected actual ZIP contents: encoded Program media, recording metadata and integrity manifest. No complete asset/dependency/performance package sufficient to reconstruct the shoot independently. Existing event metadata does not close this requirement. |
| Selective native 4K render | FAIL — IMPLEMENTATION GAP | Real browser calls the existing renderer with a 3840×2160 canvas. The renderer still paints its 1280×720 space; the requested outer region is transparent. A larger canvas is not a native 4K scene renderer. Source-level replay/selected rendering is absent. |
| Actual DaVinci Resolve import/relink | BLOCKED — application unavailable | No Resolve executable/install present. FFmpeg/FFprobe decode and our EDL checks do not substitute for a real Resolve session. |

## Defects reproduced and repaired

1. **EDL selected unavailable source footage.** A two-second track accepted a select ending at 2.5 seconds, and a +0.030-second correction could move an otherwise valid end past the source. Three new checks failed first. Export now rejects requested ranges beyond known source duration; the handoff audit records a source problem. User edits are retained for correction, never silently trimmed. Negative-source and subframe guards remain. `static/editor_interchange.js`; new normal regression `tests/test_editor_source_bounds.cjs`.
2. **Relinked preview disagreed with exported bytes.** Real browser imported a three-second 320×180 red clip, then relinked a one-second 640×360 blue clip with the same filename. Export resolved the new file while the viewer retained the old object URL, dimensions and duration. Stop/revoke the stale preview, commit requested cache persistence before replacing the active link, reset stale duration/quality provenance and audio/video type, and reload the selected track. A second real relink from video to audio was also reproduced failing and then verified in the correct viewer with identical exported bytes. Existing timing/edit decisions are preserved; source quality must be reverified. Uncached relinks no longer retain a stale cached media reference. `static/editor_sync_station.js`; actual browser reproduction now passes.

Original source media files are never rewritten. No art, tray geometry, character writing, Base/Horizon boundary, source audio buffer policy or waveform resampling was changed.

3. **Audio-only selections mislabeled as video EDL events.** Actual interchange output assigned the video `V` event channel to selected audio/blip tracks. A new failing regression reproduced it. The simple cuts exporter now rejects those selections with an explicit message; full JSON retains audio decisions and source bytes. No silent audio-to-video relabel or dropped audio.

## Endurance failures and diagnostic limits

The first real attempt had two admitted independent guest identities, separate browser processes, actual socket PCM/worklets, pre-fader host source recordings and active Program capture. Minute four observed zero participant inputs, with video still recording. The initial harness did not save the failure media; that evidence limitation is explicit.

A five-minute diagnostic then stopped at minute two on an instantaneous FFT level threshold while both connections remained active. Decoding the retained recording showed both tones present with strong amplitudes. This was a diagnostic metric problem, not proof of another disconnect. The harness now keeps FFT values as telemetry and uses actual input continuity plus decoded recorded audio for verification. The original disconnection failure is not relaxed away: the repeated thirty-minute attempt failed with one actual input missing, and host messages reported timing-buffer protection. Partial Program media was stopped, downloaded, hashed and independently probed; evidence retains its duration and hash, not large raw files in Git.

The current worker combines underflow/overflow into one user-facing fault message, so the exact lower-level cause and physical-device behavior are not certified. The observed available-workload failure remains a real gate failure. Increasing buffering, dropping/repeating samples, stretching audio or suppressing disconnects just to make a test green was rejected. A proper clock/load/transport investigation is still needed before long-session multi-device reliability can be claimed.

The completion/export/reload tail of the thirty-minute harness was **WROTE, NOT REACHED** because the run failed early. No shortened diagnostic is counted as a thirty-minute acceptance result. Its default target is 1,800 real seconds; optional shorter diagnostic targets are recorded in the JSON.

The first virtual-network harness used Playwright WebSocket routing, which did not intercept these native worker sockets. Its zero-intercept assertion failed, preventing a false jitter pass. The succeeding check uses a real loopback TCP proxy and asserts actual forwarded bytes. It preserves protocol, authentication, cookies, consent and native worker processing; only test transport routing is changed.

## Verification and exact source

Final local implementation/check source: `a3ca6d8abc554bc5e16751110888a73fbe184a60`, tree `38112edb8a570469bcb46220abcdb6664da91dd0`; public source twin `d7a276030a2a8051396ebfca4ab28dd5b4667d76`. Earlier repair/check commit local `b44972b` has public twin `e18e9241ddada70ef07905ecf4c71509a3de9de3`, tree `359e2627938dff26d7470ea36b04cb1f6603ae69`. Exact source trees were checked before publication. Later commits contain documentation/evidence only.

**RAN:**
- Three new bounds checks failed before repair; the three plus twelve existing editorial Node checks passed afterward.
- Finishing browser selection: one passed / one failed before relink repair; two passed afterward. An additional audio-type relink reproduction failed before its fix; final strengthened finishing selection: two passed in 35.43 seconds. Final combined editorial Node selection: sixteen passed.
- Affected Python/browser/portable-archive/switcher selection: **27 passed**, one warning, 36.46 seconds.
- Real TCP proxy / signed virtual-peer timing selection: **one passed**, one warning, 24.18 seconds.
- Top-level Node selection: **30 files, 109 reported cases, all exit zero**.
- Syntax compile of all four explicit acceptance tools passed.

The previous 2,371-pass whole Python suite belongs to the previous application source. It was not rerun or relabeled for this checkpoint: changes are two editorial JavaScript files, and current evidence is the affected Node/browser/media checks above. Failed endurance checks remain failed regardless of those regression passes.

Matching Playwright Chromium 141 had to be restored after the workspace restart removed its browser cache and virtualenv Python launcher. The first unavailable-browser attempt was recorded as skipped, not passing. No optional AI models, Blender or finisher were installed. Tests used isolated temporary data roots.

Executable explicit tools are under `tools/acceptance/`; they are excluded from default `tests/` collection so ordinary regression runs do not unexpectedly start a half-hour soak. Run tools separately using the source commands listed in the evidence README. Normal source-bounds regression lives under `tests/`.

## Publication / continuity

Base published GPT branch head: `91d642130d24a295a515217b9ce23b2cb8724ed2`; local twin `4a5a819`. Publish new tested source and documentation on the same GPT branch using guarded update and exact tree verification. No main merge, deployment, Actions or release authorization. Latest evidence: `evidence/readiness-checks-2026-11-06/`. The failed/unavailable gates remain on the master list; this handoff supersedes any implication that all remaining checks passed.
