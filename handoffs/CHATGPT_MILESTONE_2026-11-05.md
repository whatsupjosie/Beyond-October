# PubCast ChatGPT milestone — recording, people, production notes, two debugging rounds

**Opened:** 2026-11-05  
**Branch:** `chatgpt-work-2026-11-05`  
**Based on:** `integration-2026-11-04` @ `c82069b47b04eac56cca1fb4f6a4eb16c44d32ae`  
**Owner:** Josie Curtsey Cobbley / Rearview Foresight  
**Implementer:** GPT-6 / ChatGPT (this branch only)  
**Master coordination:** [Beyond-October issue #1](https://github.com/whatsupjosie/Beyond-October/issues/1)  
**Status:** SCOPE AGREED, NOT COMPLETE. This is a living work record. A separate **session-ending handoff** is required at the end of every work session, whether or not the milestone is complete.

## Exact stopping point chosen by the owner

1. Finish the recording stack, including recovered November 1 participant-audio work, independent sources, capture, save/playback/export, and recovery.
2. Complete basic first-run user experience, identity and human profiles: one owner per independent PubCast copy, guests bring their own IDs, private or discoverable *within PubCast*, profile editor, personal menu. Expanded optional profile with screen name, real name if desired, photo/avatar, pronouns, city, résumé/skills, bios, professional/hobbyist/learner, linked portfolio and click-only video reel, projects and desired collaborations, favorite media and internet recommendations.
3. Expand the already-built *production notes* to project/production groups, members, role/department targets and whole-production recipients. Sender chooses room/object/sticky-note spot. Whole-group mirror delivery means each authorized member's **own** dressing room; audio-only note can be placed on an audio-board hotspot. Structured schedule changes remain distinguishable from messages. Personal connections/message requests and a compact personal menu/notifications are within scope only insofar as required to make this user journey function.
4. Troubleshoot/debug **each of these three systems specifically**, with targeted acceptance and regressions.
5. Troubleshoot/debug **the entire combined codebase in two separately documented rounds**, repairing reproducible problems and rerunning affected tests after each.
6. At **every session end**, write a **thorough session-ending handoff** stating only what was actually accomplished in that session, the source base/head, commits, changed files, verified tests, failures/skips, unfinished items, blockers, risks, and next steps for someone to check and resume. The milestone itself ends after these agreed tasks and two debug rounds are complete. **STOP at that scope.**

Do **not** start experimental 3D/voxel builder, gamified onboarding, unrelated moonshots, or broader product changes during this milestone. Do not merge `main` or run GitHub Actions on this milestone without authorization.

## Source of truth and implementation guardrails

- Baseline branch has Claude's notes and basic profiles, GPT's speech/checkpoint work and integrated repairs. **Do not replace integrated modules wholesale with the November 1 ZIPs.** Merge missing participant/capture components semantically, keeping short-take, Blackbox close-on-reload, WebM mono, and speech-program mixer fixes.
- Owner's original packages: `PubCast-2026-11-01-participant-audio.zip` (later source than `PubCast-2026-11-01-capture-recovery.zip`). These are owned Library sources, not GitHub commit `fba3c47` (that abbreviated commit is not found in this repository). Earlier isolated extraction: **43 focused tests passed; not an integrated-tree test**. See issue #1 comment `6647762952`.
- Existing key code: `modules/production_notes.py`, `static/production_notes.js`, `modules/userdb.py`, `modules/auth_routes.py`, `modules/governance_waiting_room.py`, `static/login.html`, `static/foresight_counter.html`, `static/foresight_counter.js`, `static/foresight_programs.js`. Relevant handoff: `handoffs/HANDOFF_PUBCAST_NOTES_PROFILES_CONNECTORS_2026-11-02.md` section 14.4.
- Notes UI art (torn paper, gold star, perspective) already approved. Preserve it. The Foresight shell already has a menu/status and tray fan/Window menu; extend, do not rewrite.
- The legacy `POST /api/production/people` local crew creation and `@production` local-account targeting conflict with one-owner-per-copy guest model. Reconcile without deleting existing IDs or historical notes.
- Profile visibility: discoverability within PubCast is explicitly opt-in; real name, links, résumé, city and email are optional and private by default. Loading external video requires deliberate click; never auto-fetch third-party assets on a profile visit. Search across different hosts requires a real directory/federation service; don't fabricate network availability or weaken host authorization.
- One logical note, explicit target list, authorized delivery per member and spot; preserve To/CC/BCC, attachments and per-recipient read/trash and privacy. Never leak BCC or recipient private emails/notes through list APIs, common hotspots or fetch-by-ID.
- No changes to `main`. No GitHub Actions as a substitute for local tests. Respect Windows PowerShell 5 compatibility, offline-first operation, small bandwidth, account security, and the user's approved look and text.

## Execution gates and definition of done

### A. Recording
- [x] Compare later recovered package against published integration tree path by path. November 5: both ZIPs compared by path and SHA-256; later source integrated, with exclusions and merged-file hashes recorded.
- [x] Restore missing modules, browser workers/worklets and production-route mounts using semantic integration. See recording integration evidence and the session-ending handoff; this does not close the remaining acceptance gates.
- [ ] Validate authenticated distinct guest identities and role boundaries for participant audio; do not confuse same-host simulated contributor tokens with independent guests.
- [ ] Verify multi-source takes, untouched original media, program and independent stems, cancel/short stop/PANIC, timed capture, replay/export, crash/restart recovery and overlapping speech.
- [ ] Run focused tests on **current changed tree**, plus relevant existing suites; record hardware/environment exclusions separately.

### B. Human accounts and profiles
- [ ] Preserve permanent IDs through migration/restarts.
- [ ] One local owner per installation, guest admission/waiting-room behavior, separate identity and privacy.
- [ ] First-time profile flow: create basic profile, choose public-within-PubCast/private, enter app; optional fields skippable.
- [ ] Personal menu, profiles and editing; validate uploads and external links; click-to-load reels.
- [ ] Search/message/contact requests, accept/decline/block and authorized private communication as needed for first usable member journey.
- [ ] Test privacy across guest/host, anonymous requests, searches, edits, migration and reload.

### C. Production groups and notes
- [ ] Group membership + roles and owner/host permissions.
- [ ] Select whole production, department, individual or subset. Preview actual authorized recipients before send.
- [ ] Let sender pick allowed spot; map to recipient's personal surface for per-person dressing rooms.
- [ ] Preserve independent read, notes inbox/sent/saved, attachments, schedule updates and existing artwork.
- [ ] Integrate minimal global message/notes indicators into Foresight's existing top bar and personal menu without breaking open trays or typing.
- [ ] Test note delivery to sound engineer at audio console and entire production at each own mirror, including unauthorized access attempts.

### D. Targeted debugging
- [ ] Repeat functional API and actual UI/browser tests for recording.
- [ ] Repeat account/profile privacy/first-run and guest tests.
- [ ] Repeat group notes composition, placement, delivery and privacy tests.
- [ ] Write defect → reproduction → changed files → proof of fix entries.

### E. Whole-codebase debug round 1
- [ ] Independently exercise all meaningful startup/integration, runtime/API, disk/recovery, auth, browser, audio, 2i and studio workflows supported by the environment.
- [ ] Fix reproducible regressions; run focused suite and widest feasible whole-suite; record every skip and exception.

### F. Whole-codebase debug round 2
- [ ] Re-audit and retest on the **post-round-1** tree, focus on cross-feature boundaries (owner/guest, recording/notes, save/restore, offline, concurrent input).
- [ ] Repair reproducible findings and rerun wide suite; do not reuse round-1 test evidence as the second round.

### G. Session-ending handoff (every session); milestone scope stop after both rounds
- [ ] At the end of **this and every subsequent session**, state what was done, what was actually tested, what failed, and what remains unverified or untouched. Include branch/commit, exact files and commands, known risks and blockers, with Linux/headless evidence distinguished from native Windows/real microphone/device checks. **Do not describe the work as complete merely because the session ends.**
- [ ] Sign each session-ending handoff and link it from issue #1 for review and continuity. A subsequent session resumes the unfinished work rather than assuming completion.

## Evidence log

- 2026-11-05: Branch created at the integrated head `c82069b`. Scope was confirmed by owner. No new application tests or source fixes have yet been verified on this branch; none are claimed by this entry.
- 2026-11-05, Codex / ChatGPT Work: recording reconciliation published at `c5589bb` (same tested tree as local `0a4f89e`). Restored missing participant audio, raw voice segments, local capture journals, recovery and original server ingest. Added local recorded clacker and measured video timing; exact-frame GLB reuse reduces duplicate Program/Preview rendering without changing poses or resolution. Full current evidence is under `evidence/recording-integration-2026-11-05/` and `evidence/clacker-integration-2026-11-05/`. Camera-pool performance gate remains failed in this environment. Independent admitted guests, full source master, hardware acceptance, profiles, groups and both required whole-codebase debugging rounds remain open. See `handoffs/SESSION_ENDING_2026-11-05_CHATGPT_WORK.md`; the first scope-only entry above is historical.

- 2026-11-05T11:01:13.772Z, Codex / ChatGPT Work: session PAUSED because the workspace became unavailable. Published recording/clacker application `f997d541` passed the full integration baseline: 2,328 passed, six skipped, zero failed, sixteen subtests passed, 921.01 s; final Node selection 37 passed. This is not either post-feature debug round. Initial profile backend work passed 15 tests locally, but its application changes remain uncommitted/unpublished; later auth/UI changes are unverified. See the session-ending handoff and `handoffs/PROFILE_WORK_RECOVERY_2026-11-05.md`. Groups, independent guests and both required post-feature rounds remain unfinished.

