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

The local recorded clacker is implemented in the later checkpoint below.
Complete replayable source masters, deterministic selective native rendering and
physical-device/Windows/PowerShell 5/long-session/network acceptance remain open. PCM contributions
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

## Session end — workspace became unavailable (historical; resumed below)

**Signed:** Codex / ChatGPT Work, 2026-11-05T11:00:31.965Z.
**Reason for stopping:** the execution environment became unavailable while a
profile UI patch/test operation was pending. The non-returning orchestration was
canceled. This is an environment stop, not milestone completion.

Published application source is `f997d5418903522d62a2aa10e4afc9755800ee09`,
identical to local `aacf59d`, tree
`ab251b65a2b294ffb75d4975ac3ee971a93c001d`. Recording reconciliation is the
preceding `c5589bb`. Documentation-only recovery commits follow those. No main
merge, deployment or Actions occurred.

**RAN, complete recording integration baseline:** `python -m pytest -q` with
the installed Node executable selected for Playwright, on that frozen source:
**2,328 passed, six skipped, zero failed, sixteen subtests passed**, 217 warnings,
921.01 seconds, exit zero. All current recording, clacker, exact-frame reuse and
camera-pool tests passed in this run. The six skips are two disabled Alex research
modules, three real-model speech cases and one optional speech-decoder dependency.
Final Node recording/sync/audio/archive selection: **37 passed**. Earlier failed
runs remain evidence; a broad pass does not certify physical-device performance.

The full-suite raw log and XML were copied into the local evidence directory,
but access dropped before those two artifacts were published. The final summary
above was directly observed. Already published focused logs, failures, source
hashes and timing measurements remain available in the two evidence folders.

**Profiles:** an initial backend extension was implemented locally and passed
15 API/SQLite tests (old notes regressions included). Later setup/auth metadata,
editor, draft, photo and reel UI work was written but not verified. No profile
application changes were committed/published before the interruption. The last
UI patch's completion and the dependent browser test are UNKNOWN.

[Profile recovery record](PROFILE_WORK_RECOVERY_2026-11-05.md) lists every confirmed
and unconfirmed local path, the actual test result, workspace and artifact paths,
requirements, intended test command and next actions. Recover that working tree
before assuming the code is missing or rewriting it. If it is lost, these notes
are a reconstruction guide, not a claim that the source was uploaded.

**Still unfinished:** independent invited guests/one-owner-per-copy migration,
the expanded profile journey, production groups/department/individual note
addressing, schedule updates, contacts/notifications needed for those journeys,
their targeted debugging, and both required post-feature whole-codebase debug
rounds. The broad recording baseline is not counted as either round. Source
masters, cross-device sync, native Windows and hardware gates remain open.

The claim is PAUSED because the workspace is unavailable. Next session resumes
guest identity/profiles and the remaining agreed scope from these records.



## Resumed profile checkpoint

Signed: Codex / ChatGPT Work / 2026-11-05T17:47:23.494222+00:00.

Recovered the unpublished source, repaired the restored runtime, and completed
the missing draft/browser changes. RAN current combined profile API, real-browser,
auth and existing notes selection: **25 passed**, one deprecation warning,
15.04 seconds. See `evidence/profiles-2026-11-05/README.md` and its actual logs.
The earlier UNKNOWN patch did not land; the source and tests now supersede that
uncertainty. The full recording-baseline raw log/XML are now included. That old
2,328-test result applies only to the earlier recording source. It is not proof
for these profile changes, and neither baseline is a post-feature debugging round.

Profile optional fields, visibility, photos, drafts, conflict refusal, host-scoped
search, click-to-load reels, setup metadata and the existing singleton tray are
implemented. Independent guest identity/admission, groups/schedules, contacts,
full onboarding browser acceptance and the remaining milestone gates remain open.
Claim ACTIVE, continuing with guest admission. No main merge or deployment.

## Session-ending checkpoint — resumed work saved

Signed: Codex / ChatGPT Work / 2026-11-05T18:18:08.766851+00:00.
Status: session/context checkpoint; milestone unfinished. There is no outstanding
owner decision blocking the next authorized engineering step.

### Source and actual results

Published application commit: `e4686221531b58cead4545a3020475f61a80d14b` on
`chatgpt-work-2026-11-05`. Exact tested local twin: `0848ee7`; tree:
`609741847ad38fa651a2619139a7eb3dd154daf7`. The connector publication has the
same tree; shell push still lacks credentials. Do not reset or discard local
history merely because local/published commit IDs differ. Published predecessor
`01d9a49` contains durable governance admission; `b2ecb20` contains the earlier
profile checkpoint. Local `2b288da` contains the first-run browser follow-up,
which is included in the latest published application tree.

**RAN on this current frozen application:** 109 passed, one Starlette/AnyIO
deprecation warning, 99.14 seconds, exit zero. This includes actual two-copy HTTP
and popup browser journeys; private note delivery; auth/role/privacy boundaries;
profile/onboarding/drafts; incoming and unsolicited outgoing socket revocation;
legacy note browser regressions; credential/checkpoint recovery; and the original
full two-peer media acceptance using two independently admitted guest leases.
Physical microphones are replaced by browser tones. Actual decoding, source
separation, live controls, reconnect, original save and exact ZIP bytes are real.

Exact selection, architecture, failures/corrections and open gates:
`evidence/guest-admission-2026-11-05/VISITING_IDENTITIES.md`.
Final raw output/JUnit: `guest-checkpoint-final.log` / `.xml` in that directory.
Earlier failing observers and the initial missed session-ban check remain as
raw evidence. Raw pytest logs contain their own trailing whitespace; they were
preserved verbatim. Source-only whitespace check passed.

The old **2,328-test** result remains a recording integration baseline on the
older `f997d541` tree, not a full-suite result for the new profile/guest source.
**Neither of the two post-feature whole-codebase debugging rounds has begun.**

### What now exists

- Private human profile editing, opt-in host-scoped discovery, explicit optional
  fields, bounded metadata-free photo copies, per-field sharing, click-to-load
  reels, revision-fenced updates and drafts, basic first-run setup and skippable
  optional profile entry. Permanent existing IDs survive migration. Actual first-
  install browser journeys pass for private and discoverable choices.
- Me menu opens the existing singleton profile and guest/invitation trays;
  no tray geometry or note art was redesigned.
- Independent copies keep their own sole local owner and permanent human ID.
  Human identity keys extend the existing encrypted CredentialStore. Atomic
  create-once publication prevents racing workers from silently rotating keys;
  damaged keys fail rather than being replaced.
- Host invitations, five-minute one-use challenges, signed minimal visiting cards,
  explicit consents, owner approval/key comparison, remembered returning keys,
  an explicitly unlockable door, eight-hour bounded visiting leases and explicit
  durable lease revocation. Owner role is never granted by the visiting card.
- Existing GovernanceEngine owns durable approvals; compare-and-set prevents
  competing workers from both deciding a request. Visiting cards cache shared
  profile data without adding local password/user rows. New local crew-account
  HTTP creation is retired (410), while old accounts/IDs/notes are retained.
- Browser popup exchange validates exact origin and source window. Manual card
  exchange is offered as a fallback; its browser acceptance is still open.
  After approval the guest can view her read-only visiting card and is offered
  the green-room studio entry link. Actual entry through that link remains open.
- Central token decoding verifies visiting leases. A socket transport fence checks
  each live incoming/outgoing frame, so an idle revoked visitor cannot keep
  receiving frames. Tests include an already-open socket.
- Two independently admitted guest identities have passed the complete existing
  decoded recording/media-export acceptance. That closes the former same-owner-
  token limitation for this tested local workflow; native/network gates remain.

### Source map

`modules/human_profiles.py`, `modules/userdb.py`, `modules/auth_routes.py` and
`modules/production_notes.py` own profile validation/persistence and legacy notes
integration. `modules/credentials.py` owns encrypted immutable identity secrets.
`modules/governance.py` owns durable waiting entries; `modules/guest_identity.py`
owns invite/proof/pin/lease state in the same governance database.
`modules/guest_identity_routes.py` owns the visitor HTTP surface.
`modules/auth.py` and `modules/guest_session_guard.py` fence tokens/live frames.
`main.py` wires them at the existing governance startup and middleware boundary.

`static/human_profile.html` / `.js` are the profile UI;
`static/human_visits.html` / `.js` are join/sign/host screens.
`static/login.html`, `static/reach_auth.js`, `static/foresight_counter.html` and
`static/foresight_programs.js` integrate setup, stable IDs and existing trays.
`requirements.txt` includes Pillow for bounded photo normalization.

New tests: `test_human_profiles.py`, `test_human_profiles_browser.py`,
`test_human_profile_onboarding_browser.py`, `test_governance_admission_persistence.py`,
`test_identity_credentials.py`, `test_guest_identity.py`,
`test_guest_identity_routes.py`, `test_independent_guest_hosts.py`,
`test_independent_guest_browser.py`, `test_admitted_guest_recording_browser.py`,
all under `tests/`. Existing `test_production_notes.py` and its browser fixture now
explicitly create pre-existing legacy records rather than using the retired API;
new separate acceptance proves the independent visitor path.

### Next work, in priority order

1. Targeted guest-boundary audit: cross-worker session-ban propagation and stale
   ban/unban caches remain open. Session bans are process memory in the existing
   governance engine; checking the current engine fixed the reproduced immediate
   gap, but does not certify multiple workers. Explicit guest-lease revocation is
   durable and tested. Do not describe broader moderation as certified.
2. Verify guest actual studio entry and own/private dressing-room behavior,
   waiting-room avatar controls, no host private-room exposure, manual fallback,
   reconnect/restart, expiry and identity-cartridge backup/restore UX. Guest photo
   transfer and a public Human badge everywhere remain open. First-contact key
   trust is owner approval/comparison, not a claim of globally certified humans.
3. Build production groups/roles/departments on the existing NotesStore. Replace
   implicit everyone-on-host `@production` with actual selected group membership;
   snapshot/preview authorized recipients, preserve To/CC/BCC privacy and separate
   per-person read/save/trash. Add schedule updates and permitted physical note
   spots, including each person's own mirror and the sound engineer's console.
   Existing approved paper/gold-star look and attachments must remain intact.
4. Reuse the existing durable DM request/accept/decline/revoke implementation for
   contact/message requests and blocking; finish usable UI/notification indicators.
   Do not create a competing private-message authority.
5. Targeted debugging of completed recording/profile/group journeys, then two
   separate post-feature whole-codebase debugging rounds on their respective
   source trees. Do not count this 109-test focused run or the old baseline as
   either round. Complete source-master/selective native-render gates remain open.
6. Update issue #1 and the scoped milestone after each verified checkpoint; always
   write a session-ending handoff. The requested milestone stopping point remains
   after features, targeted debugging and both broad rounds.

### Environment, preservation and rollback

Workspace `/workspace/scratch/d6f0985b33b2/pubcast`; Python 3.12.14 virtualenv,
Node 24, Playwright 1.56 / Chromium 141, system FFmpeg, software WebGL. Restored
Python launcher points at the installed runtime; Chromium cache was reinstalled.
Use the installed Node executable via `PLAYWRIGHT_NODEJS_PATH` for Playwright.
Use isolated temporary PUBCAST_DATA_DIR roots, not actual seeded user data.
`run_reach.py` supplies the persistent JWT secret for real launcher operation.
No native Windows/PowerShell 5, physical GPU/microphone/phone, WAN or long-session
certification is implied. Atomic key publication needs native filesystem checks.

No main merge, deployment, GitHub Actions, art replacement or PubPartner/2i
restructuring occurred. Base and Horizon were not coupled. No private owner
material was copied. An unrelated recovery download temporary file remains
untracked and untouched; do not add or delete it as part of this work.

Changes are additive/reversible source commits; do not delete migrated user or
identity data to roll back. Reverting source without accounting for signed guest
leases and cached cards requires a compatibility review, not a destructive reset.
