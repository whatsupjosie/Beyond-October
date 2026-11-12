# Session-ending handoff — post-completion reliability audit

**Later readiness checks:** [executed readiness follow-up](SESSION_ENDING_2026-11-06_READINESS_CHECKS.md) records newly repaired editorial defects, failed long multi-peer continuity, missing source-master/native-4K implementation and unavailable physical/Resolve gates.

Signed: Codex / ChatGPT Work, November 6 UTC. Branch: `chatgpt-work-2026-11-05`.
**Status: audit repairs and final full confirmation completed in the available environment.** The five missed defects and one introduced cleanup regression were repaired and exercised. This is not a release-readiness or timing guarantee; open engineering and device gates remain below.

## What the audit found

The earlier full suite passed, but it missed real failure paths. Five defects were reproduced before their repairs:

| Finding | Actual failure | Repair and proof |
| --- | --- | --- |
| Attachment staging ownership | Starting a second notes router deleted another worker's staged attachment; saving failed with missing bytes | Per-request staging directories protected by OS leases. Stable parent lock serializes registration/reaping. An actual HTTP send now survives a second worker start. A spawned worker's live bytes survive cleanup, and its abandoned directory is reaped after exit. |
| Conflicting guest ban authority | Governance expired a session ban on the next run, but guest validation's second SQL check still denied the same guest | Remove the conflicting duplicate ban check; keep the existing governance authority plus lease/key/entry checks. New-run session ban expires; permanent ban still rejects. |
| Lost chat acknowledgement | A real sent message with a lost receipt could leave the editor disabled indefinitely | Fifteen-second acknowledgement deadline exposes an unconfirmed state and preserves the draft/UUID. Two own-copy guests use a real socket with exactly one server receipt dropped; retry confirms, and reopened persisted history contains one copy. |
| Group size boundary | Two hundred requested members plus automatically retained owner created two hundred one members, which could not receive a whole-production note | Count retained owner in the transaction; reject and roll back oversize group. Two hundred total members remains accepted. |
| Recipient/placement editing | Removing a recipient after choosing her note location retained an obsolete placement; actual preview returned HTTP 400 and blocked sending | Prune placements only for people no longer selected, expanding group/department selectors while retaining still-selected overrides. Real browser switches Sound to Camera after choosing a location and previews the correct remaining recipient. |

## Regression caught in the audit repair

The first completed broad audit run on `8159801` finished with 2,370 passed, six skipped and one failure: `test_the_route_still_enforces_its_own_ceilings_behind_the_guard`. The upload-limit and payload cleanup behavior passed, but the new persistent parent lock was inside `incoming/`, violating the unchanged empty-staging assertion. Move that stable bookkeeping file to `notes/.incoming.lock`, outside payload staging. The test remains unchanged. This is an introduced repair regression, not a reason to relax the test or count that run as passing. A further complete confirmation on the corrected source passed; see executed results below.

## Test weaknesses corrected

The old archive corruption test appended bytes. A same-length corruption could evade a size-only check without that test noticing. The new regression changes one byte, recomputes ZIP CRC, retains the original member length, and verifies the real importer rejects it without a partial destination. In an isolated in-memory copy, removing only the SHA-256 comparison makes that exact rejection assertion fail. Production source is never mutated by this test.

Earlier group/contact UI tests used legacy local users. The new acceptance adds two independently owned identities on separate home hosts, real signed admission to a production host, department schedule delivery, per-person locations, private BCC, attachment downloads and independent read state; then real contact consent, dropped receipt/retry, persisted history and block enforcement. This closes a cross-feature evidence gap rather than treating the older local-user tests as proof of visiting guests.

The initial new browser test's history assertion raced the old conversation while reconnecting. Its wait now observes the newly opened socket state and then persisted-history rendering. The failed run is retained and labeled as a test synchronization defect, not hidden or presented as an application repair.

## Attachment ownership decision

Three approaches considered: retain all crash files indefinitely (safe for live uploads but accumulates storage), delete by age (unsafe for slow/live requests), or use per-request OS leases and proven-dead cleanup. Selected leases, following existing repository file-lock patterns in documents/capture, without coupling notes to those services. Parent registration/cleanup lock prevents lease-file replacement races. Heavy cleanup runs through the request threadpool; cancellation-shielded finally cleanup closes its batch. Legacy loose staging files have no ownership proof and are deliberately retained, never guessed dead. Existing original-media and note-attachment stores are preserved.

Windows uses the documented `msvcrt.locking` byte range even beyond EOF, avoiding a pre-lock read of a potentially locked byte. Primary reference: https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/locking . Native Windows behavior remains UNKNOWN here; Linux spawned-process execution is the observed proof.

## Reviewed paths and claim boundaries

- Recording: actual encoded capture/journal/source jobs, actual-start timestamps refreshed in durable appends, ownership fencing, Stop/PANIC, recovery and portable import/export. Existing original-byte tests remain; added same-length hash mutation proof.
- Synchronization: shared AudioContext, audio-thread cadence, immediate video mark callback, per-take offsets and recorded measurements. A 250 ms regression bound is not a frame-accurate or millisecond-accurate production guarantee. Three-probe automatic calibration/compensation remains design only. Physical devices and cross-device clock drift remain unverified.
- Profiles/guests: validation, explicit disclosure, normalized images, signed host-bound challenges, one-use invite transaction, pinned identity keys, guest lease guards, one local owner and existing vault key publication. First-contact key approval identifies the approved key, not independently certified human identity. Guest picture transfer, cartridge backup UX and global directory remain unimplemented extensions.
- Groups/notes: membership revisions and transaction guard, per-recipient BCC/read/save/trash, scope resolution, placements, schedules and file staging. Added a membership-change-after-preview/before-save regression: HTTP 409, no sent note and no orphan attachment or staging directory.
- Contacts/moderation: existing consent authority, block/revoke and outgoing socket fences; new real lost-receipt acceptance. Scope does not claim global messaging federation.
- Cross-system preservation: full collected suite and Node modules on frozen final source; source diff inspection. No owner data, original art, tray geometry, Base/Horizon contracts or unrelated recovery temporaries changed. No main merge, deployment or Actions.

## Executed results and source

**RAN:** 2,371 passed, six skipped, zero failures/errors, 217 warnings and sixteen subtests passed in 990.44 seconds (exit zero). Twenty-nine Node files reported 105 cases, all exit zero; canonical npm selection also exited zero with nine overlapping cases.

Final tested local application `bf20f7f520f0422b9c560f22e83d05a9035764a3`, exact tree `8bd568419b03703b4d113a20b966975c972b4c78`; published application twin `885707b079f71b17b3f84e0a801e129eb61538d1`. Earlier repair commits: local `6666261` / public `e2dd36461d104a087b4b04b8b266d7858a580e2e`; local `8159801` / public `bfbdfcd98319b2d65aa6510a750129fd9a97a331`. Each public application tree was verified identical to its local counterpart. Later documentation/evidence edits do not change the tested application.

Focused cleanup rerun: 24 passed in 40.95 seconds. Final decoded clacker offsets: 94 ms and 38 ms; unchanged 250 ms regression guard. Exact commands, failed and passing logs, JUnit, Node per-file results, source hashes and skip entries are under `evidence/reliability-audit-2026-11-06/`. All new code/tests were executed; no source-only implementation is being called verified.

The first broad audit run was intentionally interrupted (exit 130, partial progress only) after the continued review reproduced the recipient/placement defect. It is not counted as a pass or another completed round. The final full run is restarted on all repaired source. Logs preserve failed reproductions and successful focused reruns. Targeted and full counts overlap and must not be added.

The first completed broad audit run's decoded clacker observation is 15 ms and 16 ms video-minus-audio-reference. The original 250 ms assertion remains unchanged. Preserve the measured artifact; do not generalize this setup into a device guarantee.

## Remaining limits

Linux/headless Chromium/software WebGL evidence; native Windows, physical microphones/GPUs/phones, WAN, prolonged load and independent clock drift remain UNKNOWN. Six existing optional/research skips remain explicit in the test artifacts. Complete replayable scene-source master, selective native 4K rendering and actual DaVinci import/relink remain open engineering acceptance gates, not hardware-certified by a passing browser suite. This audit does not close those gates or declare PubCast release-ready.

The previous blanket completion wording is superseded by this specific evidence and its limits. Fixes are additive and reviewable; do not delete runtime databases or identity files to roll back. Preserve the original owner handoff/design text.

## Publication

Base publication: `3e7e460cbb207d85f83fc3e72783dbdd2204649b`; local tree twin `edd3fad`. Connector publication uses a compare-and-set branch update, followed by exact local/published tree verification. The branch update is atomic after the three application commits and the documentation commit are prepared. Issue #1 receives the result and latest handoff link after successful final verification and publication. No main merge, deployment or Actions. Local source/public commit twins differ in commit IDs; the exact Git tree and per-file hashes are the content authority.
