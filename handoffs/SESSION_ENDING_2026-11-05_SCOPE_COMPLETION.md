# Session-ending handoff — scoped recording, profiles and production notes

**Later audit:** [post-completion reliability audit](SESSION_ENDING_2026-11-06_RELIABILITY_AUDIT.md). Its reproduced defects and later verification supersede this checkpoint for current reliability status.

Signed: Codex / ChatGPT Work, November 5 Los Angeles session (completed November 6 UTC).
Branch: `chatgpt-work-2026-11-05`. Master coordination: [issue #1](https://github.com/whatsupjosie/Beyond-October/issues/1).

**Status: scoped software work complete within the available environment.** This supersedes the earlier paused checkpoint. Both distinct broad debugging rounds were run, their findings repaired, and the final full confirmation passed. Hardware and optional-model exclusions are explicit below.

## Work delivered

Recording retains recovered independent participant audio, original encoded media, Program and independent stems, local journals, replay/export and crash recovery. Two separately owned identities admitted on a different host exercise actual guest recording and export. Real browser/decoded-media tests cover short Stop, PANIC, canceled permission, disconnected sources, failed storage, reload and browser-process crashes. Physical microphones are represented by browser test tones. Original-media preservation and portable archive integrity are tested; advanced native selective rendering is outside the completed browser recording claim.

Profiles preserve permanent IDs and provide own-copy setup, private-by-default optional details, opt-in per-field discovery on this host, normalized photos, revision-safe drafts, deliberate reel loading and the existing Me menu/trays. Visiting guests use signed host-bound cards, owner-approved key admission and revocable leases. The guest entry link now opens the real `green_room/main` destination. A visiting profile is read-only. The legacy local-crew creation endpoint remains retired without removing old IDs or historical notes.

Production groups now have explicit members, departments, producer permissions and revisions. Notes target a chosen production, department or individual with previewed recipients and per-person placements, including each own mirror and audio-console spots. Whole-production delivery includes the sender when she is a member. Structured schedules carry timezone-aware start/end/location. Membership and preview revisions are fenced again during delivery. Existing artwork, attachments, To/CC/BCC privacy and independent read/save/trash remain intact.

Contacts reuse existing request/accept/decline/private-message authority. Blocking persists across workers and revokes prior grants. Switching conversations fences late frames; drafts belong to the correct actor/conversation, unconfirmed messages survive reconnect and retry the same idempotency ID. The existing shell exposes groups, contacts and notes with compact notifications.

## Source changes and repairs

Local application commits (not the connector publication commit IDs):

- `3326b06`, tree `4c60a98b12a3d843f8076c7a9929fd8fbc32c3c3`: groups, schedule notes, contacts, shared moderation.
- `5e3331f`, tree `3d70db0b70183d339cc0f3874cddbe96117bb367`: round-one repairs, migration serialization, private-chat draft/receipt recovery and photo limits.
- `878ef65`, tree `e33526b9b2cba7da5f5df0030e6af6166a9cc761`: audio-clock notification paints clacker marks immediately before queued scene rendering. This is the final tested application tree; later edits are documentation/evidence only.

Key implementation files: `modules/production_groups.py`, `modules/production_notes.py`, `modules/governance.py`, `modules/userdb.py`, `modules/chat_rooms.py`, `main.py`; `static/production_groups.{html,js}`, `static/human_contacts.{html,js}`, `static/production_notes.js`, `static/human_profile.js`, `static/human_visits.{html,js}`, `static/foresight_programs.js`, `static/foresight_counter.html`, `static/world_walk.html`, `static/production25d_clacker.js` and `static/production25d_app.js`.

New acceptance covers groups/contacts UI and authorization, 12-way concurrent startup across eight data roots, spawned-process moderation, conversation switching/retry, actual host photo upload and guest entry. Existing recording/profile/notes regressions remain in the full suite.

## Two distinct whole-codebase debugging rounds

Round 1 ran on `3326b06`: **2,357 passed, six skipped, one failure, four teardown errors**, sixteen subtests, 967.25 seconds. The failure was a static API-reference contract around the guest API stem. Four teardown errors exposed notification code assuming a complete auth adapter in offline shell tests. Both were repaired without weakening tests. Additional adversarial reproductions exposed migration races, stale conversation frames, omitted sender delivery and a real full-host photo size mismatch. Focused repairs: 27 passed; actual-host photo checks: three passed; conversation Node cases: three passed. Earlier targeted scope selection finished 35 passed.

Round 2 ran on repaired `5e3331f`: **2,362 passed, six skipped, one failure**, sixteen subtests, 962.94 seconds. Decoded clacker video lag measured 285/132 ms, exceeding the unchanged 250 ms assertion on one mark. The audio-clock callback now paints the mark immediately, preserving image quality and the original assertion. Focused real-media rerun: two passed, 49.10 seconds, measured 100/26 ms.

Final full confirmation on `878ef65`: **2,363 passed, six skipped, zero failures/errors, 217 warnings, sixteen subtests passed; 963.46 seconds. All 29 Node files exited 0, with 104 reported cases.** Decoded clacker offsets in that run were 8 ms and 90 ms; the assertion remained 250 ms. Application source was frozen during the run.

Evidence: `evidence/scope-completion-2026-11-05/README.md`, raw logs/JUnit, per-file Node logs, `tested-source.json` and measured clacker JSON. Earlier recording/profile/guest evidence is retained in its original directories. Counts from targeted and broad runs overlap and must not be added as unique tests.

## Synchronization decision

Proceed with the tested shared-audio-clock marker path and preserve observed timestamps. The owner's proposed automatic three-probe preflight, measured delay compensation, zero-offset simultaneous dispatch and director override are documented in `docs/synchronization/THREE_PROBE_CALIBRATION_REVIEW_2026-11-05.md`. Their automatic selection and operator UI are **not implemented or claimed as tested features**. Three samples give a provisional estimate, not a timing guarantee. Permission preparation, actual-output measurements, jitter, configuration invalidation and no silent mid-take switching are explicit design requirements.

## Environment and exclusions

Linux; Python 3.12.14; Node 24.22.1; Playwright 1.56 / Chromium 141; software WebGL; FFmpeg/FFprobe. Isolated temporary data roots protect owner data. Browser commands use `PLAYWRIGHT_NODEJS_PATH=$(command -v node)` because the bundled Node executable is unavailable here.

Six existing skips: two disabled Alex research modules; three speech-model tests requiring `PUBCAST_SPEECH_TEST_MODELS`; one decoder requiring optional speech dependencies. They are not certified by this run. Native Windows/PowerShell 5, physical GPUs/microphones/phones, WAN, cross-device clock drift, long sessions and native filesystem behavior remain unverified. Global profile federation, guest photo transfer, identity-cartridge backup UX and advanced native source-master/selective rendering remain separate extensions/acceptance work. The claim is the scoped software work within this available environment, not a universal release or hardware guarantee.

No main merge, deployment or GitHub Actions. Original owner text/art, note appearance, tray geometry and Base/Horizon independence are preserved. Unrelated recovery download temporaries remain untouched and untracked. Source migrations are additive; do not delete user/identity data to roll back. Reverting guest identity code requires compatibility review for existing signed leases.

## Publication and stopping point

Publication uses the connected GitHub API because the shell has no push credential. Local and publication commit IDs may differ; identical Git tree SHA is the verification authority. The publication parent is `df7c400cbcf37c62e8efd38451298cedb71a0fb3`; the branch update is guarded against concurrent changes. Issue #1 receives the completion record and links after successful publication. No further feature expansion is part of this work order.
