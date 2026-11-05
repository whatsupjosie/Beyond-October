# Session-ending handoff — ChatGPT Work, November 5, 2026

Signed: Codex / ChatGPT Work. This file is updated as work proceeds; session end
does not imply milestone completion. Branch: `chatgpt-work-2026-11-05`.
Starting head: `afa8971f11d09f63defc7553859002934d6df586`; integrated base `c82069b`.

## Recording reconciliation checkpoint

Compared both original November 1 ZIPs, path by path and SHA-256, with this
branch. The later participant-audio package supplies missing encoded ingest,
active capture journals, independent voices and the camera-pool dependencies
used by those recovered pages. Package digest, changed paths, donor and merged
hashes are in `evidence/recording-integration-2026-11-05/source-reconciliation.json`.
Earlier donor ledgers are retained there with RECOVERED prefixes as historical
evidence, not tests of this branch.

Used `origin/main` as the common source baseline for three-way integration.
Retained current speech, mono Opus export, Blackbox closure, note polling,
profile privacy, world art and standalone 2i fixes. Did not restore active
GitHub workflows, the omitted private file, old world data or old auth code.

The app merge needed manual resolution around Stop: journal-based recording now
keeps the existing three-second first-data wait, pending-start cancellation and
immediate PANIC. An immediate stop also interrupts an already-waiting ordinary
Stop. Real browser regression tests cover both paths without replacing encoded
media with fixtures. Recorder errors now stop automatically (recovered behavior);
the existing error test retains its media-preservation assertions.

## RAN on the combined tree

Environment: Linux, Python 3.12.14, Node 24.22.1, Playwright 1.56.0,
Chromium 141.0.7390.37/SwiftShader, system FFmpeg/FFprobe. Installed repository
runtime and development requirements in `.venv`; `pip check` reports no broken
requirements. Browser installation needed `PLAYWRIGHT_NODEJS_PATH` set to the
installed Node executable because the bundled executable was denied here.

- Backend: 68 passed. Participant audio, encoded ingest, pool authorization,
  original portable recording, program-audio routes and contracts.
- Browser recording: 31 passed in 228.98 s. Participant voices/decoded stems,
  levels/mute/solo/EQ, journal recovery, actual renderer/browser crashes,
  canceled permission, archive resume/restart, eight stage genres, PANIC,
  original-byte preservation and failed-storage retry.
- Neighbor regressions: 47 passed. Standalone/hosted 2i speech wiring, notes,
  shared switchers, router parity, communications and filesystem boundaries.
- Merge/pool browser checks: 14 passed, one failed in 99.33 s. Both new short
  Stop/PANIC tests pass. The failure is the recovered three-contributor camera
  pool test expecting `running` while its real resource guard reported `reduced`.
  Its FPS/traffic assertions had passed. No assertion or guard was weakened.
- Node focused recording/journal/archive/guard/confidence/audio: 32 passed.
- Existing `npm run test:node`: nine entries passed after `npm ci`.

Exact pytest logs and JUnit XML are alongside the source manifest; any tokens
in failing test diagnostics are redacted before committing evidence. Counts
overlap; they are not a unique test total. An initial baseline command named a
nonexistent test file, then the corrected baseline hit the bundled Playwright
Node permission error (22 passed, eleven setup errors). Those were environment
setup attempts, not application defects or claimed successful browser baselines.

## Open / unverified

This is not the milestone's full recording acceptance. Recovered participant
browser fixtures use contexts sharing the owner's auth token: transport and
isolated stems are proven, independent admitted guest identities are not yet.
The recovered socket tests do check distinct authenticated subjects and capability
binding, but do not substitute for the real guest journey.

Recorded fifteen-second clacker/reference track, complete replayable source
master, deterministic selective native rendering and physical-device/Windows/
PowerShell 5/long-session/network acceptance remain open. PCM contributions
have an explicit 500 ms playout reserve and are receiver-encoded pre-fader stems;
they are not lossless sender originals or sample-accurate cross-device sync.

Profiles/one-owner-per-copy guest admission, production-group notes and their
targeted debugging remain. Neither of the two required whole-codebase debug
rounds has been counted or completed. Current work is focused reconciliation.
No main merge, deployment or GitHub Actions run occurred.

The isolated pool recheck also failed (42.70 s), this time at the sustained
1.4 FPS gate. It is an open resource/performance failure in this environment,
not a diagnosed product fix. The bounded investigation has moved on; no
performance assertion was weakened.

Next: recording identity/
clacker gates and the remaining agreed scope. Preserve every unfinished gate in
the living milestone record; continue updating this handoff before session end.

## Local clacker and rendering checkpoint

Recording reconciliation is published at `c5589bbefa56f1de4ac4e7d85daccfb5c00a8963`,
tree `fab7fd60274adc69fc5936caa68a1f7edee797a7`, exactly matching local `0a4f89e`.
Shell git push lacked credentials; publication used the GitHub connector and
verified matching source trees. Local and published commit IDs differ; their
source content does not. Continue publication against the actual remote parent,
without overwriting another session's updates.

Added `static/production25d_clacker{,_worklet}.js`, wired through the existing
source journals and Program canvas. The fifty-millisecond blip is an independent
recording and does not enter Program audio. A half-second video dash makes the
mark recordable on the slow software renderer. Per-take reference generation IDs
preserve earlier timing metadata across clock failure/restart. Clock failure
stops capture, retains incomplete media and allows a fresh recording generation.
Local reference timing is now implemented; cross-device timing is still open.

Measured the actual encoded media. A short mark initially disappeared; after
lengthening it, video delay still measured 244/318 ms, failing the unchanged
250 ms local acceptance bound. `world_walk_glb.js` now reuses exact current-frame
pose pixels for the duplicate Preview draw. It checks frame stamp, resolution
and hologram state; a new frame renders normally and dispose releases the copy.
Walker callers do not opt into this optimization. The follow-up media run passed
at measured delays of 79/152 ms. Reference spacing is exactly fifteen seconds
and Program has no blip. Do not call that sample-accurate video or cross-host sync.

Executed final targeted application run: thirty-five passed; the added GPU
observation test initially failed because its prototype spy did not observe the
renderer instance method. Correcting the observer to count native WebGL draw
calls gives a separately passing proof: same-frame Preview needs no extra draw,
the pixels are byte-identical, and a new frame does issue draw calls. Existing
eight-genre and actual-animation checks also pass. Full failures, corrections,
exact commands, source hashes and actual measurements are preserved under
`evidence/clacker-integration-2026-11-05/`.

A whole-repository integration baseline is running on this source. It is not
either of the two required post-feature debugging rounds. No profiles/groups
implementation or independent guest identity acceptance is claimed yet.
