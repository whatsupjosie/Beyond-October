# Handoff to GPT: status of Claude's work and the integration check

Written 2026-11-12 (Pacific), by Claude, for GPT and any other collaborator on Beyond-October.
Branch this describes: claude-work, tip ad96bd1.
main: unchanged, tip c82069b (2026-11-04). Nothing in this handoff authorizes a change to main.

Read this before you touch claude-work. Everything marked VERIFIED was checked by a command or a test run during the 2026-11-12 pass. Everything marked NOT VERIFIED was read from a chat or a file and not re-run.

## 1. What changed on claude-work during this pass

Commit 3641f31, "Merge integration-2026-11-04 into claude-work". VERIFIED.
- Merged origin/integration-2026-11-04 into claude-work. The integration branch has the same content as main. The merge was clean, with no conflicts.
- Brought onto claude-work: the November 4 and 5 fixes (Notes email visibility, Place sticky note, flaky recording test fix, notes resource closing, 2i speech path tests, PubWorld Set page offline, four defect fixes).
- Also brought in, because the integration branch already contained them: three commits dated November 1 under the whatsupjosie account (offline host-data checkpoint, recovery through the real host, local speech). Their authorship is not confirmed from here. They were integrated into main on November 4.

Commit ad96bd1, "Notes for the next AI: add the owner's November 10 correction". VERIFIED.
- Appended the correction block to docs/alex_eq_2026-11-10/NOTES_FOR_THE_NEXT_AI_2026-11-10.txt. The owner's words are quoted as she wrote them.

This handoff file is the commit after ad96bd1.

## 2. Test status on claude-work at ad96bd1

VERIFIED, one clean run, 2026-11-12, Linux sandbox, Python 3.13.18, dependencies from requirements.txt and requirements-dev.txt installed into a venv:
- 2,370 passed, 8 skipped, 1 failed, 2,377 tests collected.
- The failure is tests/test_world_walk_host_integration.py::test_bella_faux_pas_studio_opens_from_the_foresight_counter_in_the_dressing_room. It fails at line 336 with StopIteration. The test calls next() over page.frames right after the iframe's src attribute appears, and the frame is not yet registered. It passes when run alone. Treat it as a timing race in the test, not a confirmed product regression. It has not been fixed.

Environment note, not a repo change: the venv's Playwright 1.56 looks for chromium_headless_shell revision 1194. The sandbox has revision 1243 under /opt/pw-browsers. A symlink under /home/claude/pw/chromium_headless_shell-1194/chrome-linux/headless_shell points to the 1243 binary. Running with PLAYWRIGHT_BROWSERS_PATH=/home/claude/pw fixed the 35 errors. Without it, every browser test errors. On a machine with a normal Playwright install this does not apply. Windows and PowerShell 5 have not been run at all.

Not run: anything through GitHub Actions. The owner has asked that CI not be used for testing.

## 3. Open defects found on claude-work

VERIFIED by ruff --select F821 and by reading the code:

a. Camera settings never save. HIGH.
   - modules/cameras_advanced.py line 715 and modules/evo/camera_manager.py line 633 call write_json. Neither file imports it.
   - Both calls sit inside a try/except, so the failure is only logged as "Failed to save camera configuration". Nothing fails loudly.
   - The integration did not fix this. It was first found on 2026-11-06.
   - Fix: import write_json from modules/persistence.py in both files. Then add a test that saves and reloads the camera configuration.

b. modules/evo/switchblade_governor.py uses VDIReport only in string annotations, with no import. LOW. It does not crash at runtime. A type checker will flag it. Fix: import VDIReport under TYPE_CHECKING, or add the import.

c. modules/wired/NUDGE_MINIMAL.py uses WebSocket without importing it. LOW. It is a snippet that nothing imports, according to docs/handoff/COMPLETION_REPORT_2026-10-25.md.

d. tools/foresight_checks/check_lab_counter.py uses os without importing it. LOW. It is a dev tool, and nothing references it.

e. modules/mocap_integration.py and run5_pubworld_camera/pubworld.py show undefined-name flags, but both have "from __future__ import annotations", so these are harmless. No action needed.

f. The flaky test in section 2. LOW, but it will keep failing intermittently until it waits for the frame properly.

## 4. Not on claude-work

These are GPT's branches, not counted in this integration check. Each count is commits on the branch that are not on claude-work, VERIFIED with git rev-list:
- gpt/live-studio-setup-2026-11-09: 52
- chatgpt-work-2026-11-05: 52
- gpt/control-ui-wiring-2026-11-08: 51
- gpt/primp-canvas-preparation-2026-11-07: 7
- gpt-work: 0 (already contained)

Blackbox replay doc: docs/testing/BLACKBOX_CHAT_REPLAY_2026-11-09.md exists on gpt/live-studio-setup-2026-11-09, not on claude-work. VERIFIED. Its header says it describes that branch's work. It was left where it is.

Missing from the repo entirely, NOT VERIFIED from here:
- EFFORTS_AND_WHAT_TO_KEEP_2026-11-10.txt. Claude produced it on 2026-11-10 and sent it as an attachment. Not in any branch. The owner has to supply the file.
- A podcast pitch written 2026-11-02. Chat only.
- A separate failure record from 2026-11-06. Not found. The shortened evidence section is in QUALITY_STANDARDS.md, section 4.

## 5. What is on claude-work from Claude's side

Each item below was checked by file presence only (VERIFIED for the files named), not by reading each feature's tests. Behavior is covered only where the test run in section 2 covers it. Items marked "design only" have no code.
- Production notes (sticky notes), profiles and the Sir Purfluous office Easter egg, November 1–3. Code files present.
- Filler Cream engine, November 6–8, with revisions, a hookup to VoxelStudio, and 1/128 resolution for Primp and close-ups. Code files present. The Feic Mo Chroí heart script is at tools/feic_mo_chroi_heart.py.
- Filler Cream applicator UI design, sanding tool design, Primp live-makeup design. Design only. Under docs/blackbox/.
- QUALITY_STANDARDS.md with the evidence section, November 6.
- Iteration Wallet human-presence and AI-custody note, November 9. Design only. docs/iteration_wallet/.
- Fable EQ study, prompt, reading-model build, memory evaluation, and harvest documents, November 10–11. Under docs/alex_eq_2026-11-10/ and docs/pubcast_fable_2026-11-11/. Document content only, no code change, except the notes correction in section 1.

## 6. Protocol checks, from CLAUDE.md

VERIFIED on ad96bd1:
- data/pubpartner/vessels/alex.pubpartner has Git blob ID 96fa66a728d07d5ff43b0d3d7fc17a466765cec1, as the protocol requires.
- STATUS.md, static/foresight_counter.html, static/foresight_counter.js, static/foresight_programs.js, main.py, run_reach.py, and 2i/writers-room-v22.html are present.

NOT VERIFIED:
- The Foresight Counter commissioning goal in CLAUDE.md. Claude did not run it. Nothing in this handoff shows real launch, menus, the five tray sizes, 2i hosting, file open, save and reopen, rollback on a failed write, quit and restart, or graphics compatibility mode.
- Windows and PowerShell 5 commands. Not run.

## 7. Decisions waiting on the owner

These are not for GPT to decide alone.
- docs/alex_eq_2026-11-10/FABLE_PROMPT.txt, lines 47 to 49, contains a personal quotation from the owner. The owner's own rule says Alex-facing files must not carry her personal material. On 2026-11-10 she was told that quotation had been left out, but it is in the file. Ask her whether to remove it. Do not edit her words without her permission.
- Whether to upload EFFORTS_AND_WHAT_TO_KEEP_2026-11-10.txt so it can be committed.
- Whether to copy the Blackbox replay doc from gpt/live-studio-setup-2026-11-09 onto claude-work.
- Whether to restore the November 2 pitch, which exists only in chat.
- Whether GPT's branches should be merged into claude-work. Merging into main needs her explicit authorization.

## 8. Suggested next steps, in order

1. Fix defect 3a. Add the camera save test. Run the camera tests and the full suite.
2. Fix the flaky frame wait in section 3f and rerun that file several times.
3. Fix or annotate the VDIReport import, section 3b.
4. Decide with the owner on the GPT branches in section 4.
5. Run the Foresight Counter commissioning checks listed in CLAUDE.md, on Linux first, then on Windows with PowerShell 5. Record each as tested or untested in a ledger.

## 9. Working rules from the owner

These are restated from the owner's saved preferences and the project files. Check them against the owner's own wording before relying on them.
- Work on a branch. main changes only with her authorization.
- Never alter her words without her explicit permission.
- Verify as you go. Run the real thing, not only a mock.
- Do not put words like "best" or "final" in file or folder names.
- Do not use GitHub Actions to test her work.
- If she declines an idea, say plainly what is actually required, and leave the decision to her.
- If the first approach fails, look for another way to reach the goal before giving up.

## 10. Complete open-items list (added 2026-11-12 after an audit of every chat from 2026-11-01 to 2026-11-12)

This section supersedes sections 4, 5 and 7 where they differ. Each item says what it is, where it stands, and who has to act.

### 10.1 Work that is not in any branch

- The peq-integration-2026-11-06 work and its peq_lineage copy. This was 75 files with a SHA-256 manifest, plus a folder renamed from "best" to aug15_0554_pubpartner_zip. It was made on 2026-11-06 in a sandbox clone, was never committed, and the branch is not on the remote. The folder is not in this sandbox. Treat it as lost from here. Recovery depends on the original zip Josie uploaded on or around 2026-11-06. The Nov 6 chat reported 324 passed for the regression set on that copy.
- PUBCAST_WALLET_COMMUNICATION_DESIGN_2026-11-09.md, the Wallet stage 1 design. It was sent as an attachment on 2026-11-09 from /home/claude/note, which no longer exists. It is not in the repo. Its five decisions are listed in 10.2.
- EFFORTS_AND_WHAT_TO_KEEP_2026-11-10.txt, the November 10 harvest of 27 efforts. Not in the repo. Needs the owner's upload.
- The 2026-11-02 podcast pitch. Chat only.
- The 2026-11-06 failure record. Not found. The evidence section lives in QUALITY_STANDARDS.md, section 4.
- The 2026-11-06 duplicate-file audit across 23 repos. Chat only. The corrected figures from that chat are about 339 Python filenames with competing versions (an earlier 475 was wrong), about 200 copy-named files (an earlier figure of about 1,100 was wrong), and 3 mostly empty Python files (an earlier figure of 144 was wrong).

### 10.2 Decisions waiting on the owner (Josie). GPT should not decide these.

1. Merge into main. Not authorized. Claude asked on 2026-11-05. main stays at c82069b until she says so.
2. PubWorld Set page and three.js. The page needs the older three.js r128. A second copy is at static/vendor/three-0.128.0, next to the shared 0.160.0. Moving the page to 0.160.0 changes its lighting and colour handling. She should confirm the second copy or ask for one copy after a visual check. Other demo pages still load three.js from the internet. They were left alone on purpose, and she has not said whether to change them.
3. Email visibility. The change is recorded in handoffs/INTEGRATION_2026-11-04.md. It needs her confirmation.
4. One-user-per-copy versus the crew-accounts route. Undecided. This is PC-038. The crew-accounts route still exists in the code.
5. The About-me profile spec, section 14.4 of handoffs/HANDOFF_PUBCAST_NOTES_PROFILES_CONNECTORS_2026-11-02.md, which is on claude-work. Five open questions: default visibility of each field; what goes on a guest's visiting card; whether two cartridges share memory; a name for the in-studio Claude; whether "identity constant, mode switchable" is the rule.
6. Wallet stage 1 design. Five decisions: what PubCast may hand in; when (by hand, at key moments, on a schedule, or a mix); whether unknown senders are held or refused; whether PubCast may ask for things back; whether PubCast shows the Wallet's size with a warning limit. Claude recommended auto-filing paired hand-ins into an unreviewed holding area that she promotes with her key. GPT's per-hand-in approval is the alternative. Claude said it would not build until she answers.
7. The CLAUDE.md read-first line. The QUALITY_STANDARDS.md evidence section exists. Whether to list it in CLAUDE.md's read-first line is hers to decide, and CLAUDE.md has not been changed.
8. Recording files for PC-004. She was to attach recording.py and recording_pipeline_routes.py, both from November 1. Not received as far as the repo shows.
9. The user menu design, right-click placement, and the remaining spot positions. Not decided.
10. Lip-sync measurement, the external Nudge, UI polish, connectors. Not decided.
11. Windows and PowerShell 5, and physical-device checks. Not run. Her laptop was down on 2026-11-12, so these are blocked on the owner.
12. Issue #1. Whether Claude posts a progress comment under her account. Not posted.
13. Scheduled tasks. Task trig_01MnfpZqC9z7GJoCei4Q32xk is left over from 2026-11-05. Delete it only if she says so. A poke-test task was switched off on 2026-11-03 and not deleted.

### 10.3 Claude-side items still open

- The sandbox fast tier has not been run. Claude said on 2026-11-05 that it would run it, and it has not.
- PC-025 is not done. It is about reporting what the app can do based on real initialization.
- The flaky test test_portable_save_as_and_reopen_uses_real_disk_without_vendor_picker failed once under load on 2026-11-05 and then passed 16 of 16. It did not fail in the 2026-11-12 clean run. The cause is unknown.
- The regression count is unresolved. Claude's 2026-11-03 chat said 230 after a recheck. The 2026-11-06 chat reported 324 for the bridge and orchestrator set. Nobody has reconciled the two.
- The camera save bug, the VDIReport annotation and the test race are listed in section 3.
- The 2026-11-12 clean run was 2,370 passed, 8 skipped, 1 failed, from 2,377 collected. It is not the 2,476-test figure from the 2026-11-06 chat, which was on the unpushed peq copy.

### 10.4 GPT's branches, GPT's open issues

- gpt/control-ui-wiring-2026-11-08. A full-suite run on 2026-11-09 gave 2,367 passed, 6 failed, 6 skipped. All six failures are browser recording tests. The Stop button never enables on four of them, PANIC takes over a second to cut on one, and a wait times out on another. Four fail consistently, and they also fail on the November 6 version. GPT tested on an older Chromium. Claude's run was on current Chrome on a slower machine. A deliberate browser-crash test freezes the tools and was not run. Check PANIC on the owner's laptop.
- chatgpt-work-2026-11-05. GPT claimed 2,371 passing tests and then marked its own readiness checks NOT CLEARED. The largest bug it found: in a 30-minute test with two guests, guest audio dropped within one to four minutes. This is GPT's own finding and is unresolved.
- gpt/primp-canvas-preparation-2026-11-07. Paint does not show. Full-strength black ink changed the screen by 3 out of 255. The cause is that the starter avatars keep the cyan hologram glow, which adds light over whatever is painted. The avatars are also block placeholders with a domed head and no face. GPT's 36 Primp unit tests pass. The paint problem is not covered by them.
- Decisions GPT made without the owner's approval. Each needs her decision.
  - The guest acceptance wording is "I accept the production terms, recording, AI participation and data processing for this visit." The owner's own terms are not in it: avatar thoughts recorded; English or translatable; the owner signs; the AI signs too.
  - A 5 MB cap on every upload. Uploads used to be unlimited. That is roughly 10 to 20 seconds of replay video.
  - An 8-hour guest pass, 5-minute invite codes, and a 200-person group cap.
  - Replay uploads are public to anyone with the host's address. GPT flagged this itself.
- The Blackbox replay doc is on gpt/live-studio-setup-2026-11-09 at docs/testing/BLACKBOX_CHAT_REPLAY_2026-11-09.md. Commit 1cfb2d2 on that branch backs up the November 9 live studio and Blackbox source. It is on GPT's branch, not claude-work.
- Claude said on 2026-11-09 that the Iteration Wallet code is not in any of the repos it checked, and that GPT should push its branch first. Whether GPT has pushed it is unknown here.
- The October-24 repo was read-only for Claude on 2026-11-02, at the owner's direction. Nothing was changed there.

### 10.5 Other work from the same chats, not for this repo

Several chats from 2026-11-01 to 2026-11-12 are not Beyond-October work. Examples: a fashion portfolio bundle sent as files on 2026-11-02, and several personal support conversations. They are not listed here on purpose. This repo is public.
