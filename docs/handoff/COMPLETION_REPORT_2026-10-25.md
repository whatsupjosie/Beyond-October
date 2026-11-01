# PubCast Completion Report, October 25, 2026

Base: whatsupjosie/October, main branch, commit 1f2b130 (pushed Sunday October 25, 9:28 PM, "Recover Friday companion gains and wire Base/Horizon runtime paths"). Correction: the first part of this session was built on commit b44db35 (October 14), which was two commits behind main. The work was moved onto 1f2b130 and every test re-run. The October 24 ChatGPT work was dropped at Josie's direction.
Working copy: a private local copy (branch on-latest-main) with local commits on top of 1f2b130. The earlier version of this work, built on the older base, is kept on the branch master of the same local copy. Nothing has been pushed to GitHub. Josie's originals were never modified. A pristine copy of the base is kept beside the working copy for comparison.

Plain statement of status: the backbone works and is tested. It is not finished, and this report says exactly what is left.


## 1. Source-of-truth manifest

Authoritative tree: whatsupjosie/October main at 1f2b130. It adds, over b44db35, the EVO semantic runtime, the companion_support advisers (acceptance, pacing, anti-parroting, known-versus-novel, safeguards) and the Base/Horizon DockingNode, and its own verification handoff (COMPANION_RECOVERY_VERIFIED_2026-10-25.md) reports 379 passing cases.

My changes sit on top of it as local commits: the first integration pass, the keyword-layer and memory-path fixes, and the dependency declarations with this report.

Other branches in the October repo that are ahead of the old base and were NOT examined or merged: foresight/hdr-pipeline (31 commits ahead, the hyper-real Foresight work), October-Foresight-Doc-Integration (33), evo/semantic-runtime-october-2026-10-23 (37), Backup-Consolidation (36), pete-director (5), october-24-prime-rust-recovery (9), care-routines (1), pubcast/integration-ci-2026-10-24 (2) and two status-test branches. Whether main already contains their work was not checked.

Other repos were cloned for reference and were not merged: October-24 (an empty shell, its own README says the real tree was never transferred), The Prime, Saturday, PubCast Reach, PubPartner Base/Horizon, Now Curtsey, Breaking Dawn, The Counter and 2i.

Not yet compared, so no claim is made about them: the contents of the Prime archives, the Saturday "Big zip" visual patch kit, the PubCast 5.6 build, and the second Drive copy of affect_context_engine.py (one hundred and twenty thousand four hundred bytes, versus the repo's one hundred and twenty-three thousand six hundred and twenty-four). October's own import manifests suggest it already absorbed much of this, but that was not verified by diffing.

Rule followed: choose by content, never by newest timestamp.


## 2. Subsystem completion matrix

Words used: TESTED means actually run and observed. WIRED means connected in code but not exercised end to end. PRESENT means the code exists and nothing more is claimed.

Application host and startup: TESTED. The real app boots through its real lifespan as separate processes. Health answers. Windows first-run, fresh install and clean shutdown on your laptop were not tested.

PubPartner Base live turn path: TESTED with the deterministic mock provider. No real language model has run. The path is input, vault, context, memory, Alex and Jeremy bridge, affect engine, response, persisted log and receipts.

Memory and persistence: TESTED. A fact written in one process was recalled by a second process after restart. A control run with no prior write did not find it. The verbatim original is byte-exact. A torn log file and a corrupt bridge state file are tolerated.

Alex, Jeremy and the keyword (stranger) layer: TESTED and repaired, see the change log. The nuanced engine reports "observing" with no battery reading for a stranger, by design. Items two through seven of the EQ Revamp Plan are NOT started.

System Alex adjudicator and Affect Dynamics: PRESENT and WIRED. Their existing tests pass. They do not yet steer conversation tone beyond a five-value setting.

Foresight (live page): TESTED in real Chromium against the real backend. Zero console errors, all three status lights green, a picker with twenty-eight programs, and a World Chat message sent and displayed. It uses the old matter engine. The newer shapes and GL engines are not loaded on the live page. Missing from the live page: lock, pocket, stacking and named layouts. Wiring the new look is Josie's decision.

2i Writer's Room: PARTLY TESTED. The page loads in real Chromium. The 2i backend's Node tests pass (six passed, one skipped by design because it needs a live Reach server). October contains test_reach_writers_room.py only. The real-HTTP document and rich-document tests described in the ChatGPT reports are not in October. NOT verified: a real edit, save and reopen in the browser, autosave, formatting preservation, and rich DOCX editing (the EigenPal engine was never present).

PubPartner Base and Horizon docking: PRESENT in main (DockingNode, with its own tests, reported by that commit as in-process only). I built a parallel travel-memory bridge earlier in this session and then removed it, because DockingNode already does the job more rigorously (owner scoped, provenance required, atomic sync, idempotent). Not implemented anywhere yet, per main's own handoff: phone discovery, pairing, and a remote transport for these owner-scoped nodes. Not tested across two real devices.

World and PubWorld: PRESENT. The page loads. It asks for an image, assets/rooms/dressing_polish.png, that exists nowhere in October or in the other repos. Rendering was not verified.

Camera, Twin Engine and avatars: Josie's probe passes all five checks on October (scene, avatar files, camera manager, twin engine, Rust toolchain). It reports no frame rendered, and that is correct. The avatar manifest holds two avatars, Manny and Sheila. Lena is not in it. The Rust crate was not built and no GPU work was tested.

Blackbox: PRESENT. Its tests pass in the suite. The automatic capture boundary, and any ChatGPT conversation capture, were not simulated or proven.

Security and storage: see the audit section.

Real-browser widget test: passes in real Chromium. Network calls inside it go to an in-process test server, so this is not a full desktop or WebSocket acceptance test.


## 3. End-to-end runtime trace

A message posted to the live turn route goes through the pubpartner routes into the runtime spine, which builds a turn packet. That stores the original in the verbatim vault, compiles and records the vessel runtime, and writes to Jeremy's memory. The Alex bridge then masks care-facing text, runs AlexCore, runs the affect engine, publishes to the emotional orchestrator, adjudicates, and updates Affect Dynamics. Memories relevant to the speaker are recalled, the packet is assembled, a provider is called, and the turn log and receipts are persisted.

Restart proof: the app was started twice as separate processes on one data folder. The remembered fact came back after the second start. A run without the first process did not find it.

Human-pace EQ proof: Josie's nine-turn escalation was replayed through the real AlexCore with a simulated twenty-second gap between messages. Before the repair, Alex locked in WITNESS and never left. After the repair it no longer locks, and the battery no longer rises while the person is escalating. At human pace Alex reads the whole escalation, including "Get the fuck out of my house", as companion. It does not yet treat "get out" or "stop" as a request to step back. That is plan item four and has not been built.


## 4. Test results

Baseline October, per-file runs: one hundred and eight test files, nine hundred and sixty passed, five failed (all in test_doctor_paths, a missing data folder), one skipped.

Final single full run on the working copy, on top of main at 1f2b130: 1,371 passed, zero failed, three skipped, in about two minutes and ten seconds. (A run before I removed my travel bridge gave 1,383; the difference is exactly the twelve tests that went with it.)

The three skips: two are the optional Alex Little One protocol, which only runs when ENABLE_ALEX_LITTLE_ONE is true. One is the real-browser widget test, which skips in the default environment because Playwright is absent; it was run separately with Chromium and passed.

Other runs: 2i backend Node tests, six passed and one skipped by design. The SmolLM browser DOM script, eight checks passed. Josie's camera probe, five of five.

Known pre-existing fragility: test_main_route_authorization_parity boots the app repeatedly and corrupts shared module state. If it runs before test_pubcast_smoke in the same process, two smoke tests fail. This reproduces on the untouched baseline. The default order passes. It is listed as duplicate state ownership.


## 5. Change log

modules/alex_core.py, small targeted edits, not a rewrite (the file went from 1,258 to 1,388 lines: 141 lines added and eleven removed, all in the three groups below; the state machine, memory logic and personality are untouched):
- Recovery: after two consecutive settled turns, energy and stress move back toward baseline, so WITNESS and ANCHOR can be left. A mature nuanced reading that still shows depletion blocks the release.
- Matching: whole words only, negation-aware ("not tired at all", "retired", "not urgent, no panic" no longer count). "Tired of this bug" counts as frustration and never drains the battery. Ordinary "help me fix X" is not distress. Hostile or profane turns do not count toward "settled".
- Memory path containment: a user ID can no longer decide where memory is written outside the memory root. Ordinary IDs keep their exact folder, so existing data is still found.
modules/doctor.py and main.py: the runtime data folders (including secure) are created at startup, which fixed the five baseline failures.
main.py: the four /api/internal routes now require moderator rights when auth enforcement is on. They said "internal only" but had no guard and returned server file paths.
Removed again: my travel-memory bridge, my federation memory-sync change and my two travel routes, replaced by main's DockingNode.
package.json and lock: jsdom pinned to 26.1.0 (22.1.0 failed a font-size test). tests/smollm_browser_dom.cjs now finds its folder relative to itself.
requirements.txt: scikit-learn declared. The code imported it unguarded and a clean install would have failed. requirements-dev.txt: test-only packages added.
New tests: witness recovery, keyword matching, user ID paths, restart persistence, internal route guard, and runtime folder bootstrap.


## 6. Regression and audit report

Anonymous access: with auth enforcement on, one hundred and forty-nine GET routes still answer anonymous callers and sixty-three are gated. Many are HTML pages and status pages. Checked on an empty data folder: a planted API key did not leak anywhere. Two routes returned server file paths anonymously: /api/internal/pete/diagnostics (now guarded) and /api/doctor (NOT changed, see decisions). Enforcement is off by default, so a default run is open.

Fabricated status: /api/recording/storage returns hard-coded numbers (cloud used, backup "syncing") that are not measured. It should be marked as a placeholder or measured for real.

Silent error handling: forty-one places catch an exception and do nothing, plus one bare except. Not changed. Each should log or surface.

Duplicate state ownership: the test-order problem above.

Offline-first: sixteen files in static and 2i load Google Fonts from the internet (the pages I loaded in the browser that do so were 2i, world and login). Offline they fall back to default fonts. Nothing breaks, but it breaks the offline-first rule. Bundling the fonts needs a download that was not possible here.

Dependencies: scikit-learn was undeclared (fixed). beautifulsoup4 and playwright were undeclared for tests (fixed in the dev file).

Observation, not a defect I introduced: after a long escalation, the nuanced engine can still suggest a "low" battery on a warm message such as "thank you, that actually helped". That is the engine's own reading.

Alex wiring note: an old memory note says alex_core must never be wired into PubCast. The repository already wires AlexCore in main.py. That wiring was left as it is.


## 7. Remaining limitations (honest list)

- No real language model has run. Everything used the mock provider.
- ChatGPT capture was not simulated.
- The Oct 24 ChatGPT tree is dropped, and anything only in it is not here.
- The other October branches listed in section one were not examined.
- The old MemoryGate promote path (promoted memories only get a timestamp and have no exit) was not rechecked against main's DockingNode.
- Foresight's new look is not wired in.
- Rust, GPU, hardware devices and Windows were not tested.
- Google Drive OAuth and real backups to Drive were not tested.
- Real-browser tests covered page loads and the World Chat widget only.
- The nuanced engine gives no battery reading for strangers.
- Travel imports in scoped-memory mode are visible only in the default project and room scope.
- EQ Revamp Plan items two through seven are not built.
- Prime, Saturday and 5.6 archive contents were not diffed.


## 8. Decisions waiting on Josie

1. Foresight: wire in the new shapes look, delete the old C++ renderer, and restore Sir Purfluous scene director? The handoff says to wait for your visual judgment.
2. CARE port: Option one, two or three? Option one is recommended but was never confirmed.
3. EQ Revamp Plan items two through seven: go, no-go, or only some. Items two to four touch Alex Core more deeply, and the instruction stands that Alex Core is not to be rewritten.
4. /api/doctor shows server paths to anyone. Gate it, or leave it?
5. Which image should /world use in place of dressing_polish.png? The Prime has a few dressing-room images, and none is named that.
6. Bundle the fonts for offline use?
7. Is the old note "alex_core must never be wired into PubCast" retired, since it is already wired?
8. Where is the canonical repository going to live?
9. Which of the other October branches (foresight/hdr-pipeline, evo/semantic-runtime, October-Foresight-Doc-Integration, Backup-Consolidation) should be compared against main next?


## 9. Final verdict

Not finished, and not beta-ready. The conversation backbone is real and proven in-process: input, memory, Alex and Jeremy, response, persistence, and recall after restart. The Foresight shell loads and works against the real backend. Three real defects were found and fixed (Alex locking in WITNESS, matching errors, and memory paths that could escape their folder), along with a clean-install dependency failure and unguarded internal routes. What stands between here and finished: a real model turn, the unbuilt EQ items you choose, the Foresight wiring you choose, rendering and hardware tests on your own machine, a real browser pass through 2i, and the audit items above.

---

## Addendum: merge of the newest October material (branch `merged-all`)

Result: full suite on the merged tree: 1505 passed, 3 skipped, 0 failed (5 min 42 s).
Skips are the two Alex Little One research-protocol tests (opt-in by environment variable) and one live-Reach test (needs a live service).

What was merged: `evo/semantic-runtime-october-2026-10-23` on top of main + my fixes. That branch already contained three other branches and 292 files main lacked (Foresight counter and document workspace, 2i rich-document work, requested-partner-turn path, communications capture, BlackBox witness). Ten merge conflicts were resolved by keeping both sides' work; nothing of Alex Core was rewritten.

Defects found in the evo branch itself while verifying (all fixed in tests only, no app behavior changed):
1. REG-003 nudge test was stale against evo's own `bots.py` (nudges now go through `request_turn`). Test updated; its intent is unchanged.
2. Three startup tests (identical on main and evo) fail on evo itself when any earlier test leaves a lifespan open, because evo lets nested clients borrow a running lifespan. Added a releasable shared client and an `isolated_lifespan` fixture.
3. Bot-speak authorization test's stub manager lacked `shutdown`, which evo's lifespan now calls.
4. Foresight counter autosave test used fixed waits; it now waits for the saved value.
5. Test-environment only: pypdf and Pillow were missing from my test environment; they are test dependencies of evo's new tests.

988 / crisis wording: lives in `companion_support/conversation_pacing.py` and `modules/wired/`. `main.py` imports the wired stack inside try/except but never constructs it, and nothing outside `modules/wired/` calls it, so it is not on the live conversation path. Not changed; connecting it touches Alex Core and needs Josie's go-ahead.

Not yet evaluated: branches pete-director, care-routines (baby-mode routines), october-24-prime-rust-recovery, pubcast/integration-ci. Nothing has been pushed to GitHub.

---

## Addendum 2: remaining October branches merged (still `merged-all`)

Full suite after merging everything below: 1632 passed, 3 skipped, 0 failed (5 min 39 s).

Merged cleanly (no conflicts), each additive:
- `pete-director`: Pete Director page, 8-direction sprites and player. Verified served: /static/pete_director.html, manifest.json, pete_player.js and a sprite all return 200.
- `care-routines`: baby-mode care routines and staged diaper-change sequence (alex_little_one/care_routines.py, care_eq.py, bridge/route hooks). Its tests pass with ENABLE_ALEX_LITTLE_ONE=true except one: test_jeremy_never_appears_as_visible_cast_or_avatar expects a cast member named "Sir. Purfluous"; it fails identically without care-routines, so it is a stale test, not a merge effect. Left as is.
- `october-24-prime-rust-recovery`: isolated Rust/camera recovery and audit under experiments/. Not on the live path; preserved.
- `pubcast/integration-ci-2026-10-24`: GitHub Actions workflow. All five test files it names exist. It only triggers on its own branch name or manually, so it will not run on main unless edited.
- `status-test-pubcast-2026-10-22`: documentation only.
- `status-test-pubcast-2026-10-22-take-2`: skipped; an empty branch (deletes 1,072 files, adds none).

Offline findings (no change made):
- Foresight counter makes no external requests.
- static/index.html, static/world.html and 2i/index.html still request Google Fonts (Cinzel, Cormorant Garamond, Kalam, IBM Plex Mono, Courier Prime, Share Tech Mono). Only Quicksand and Nunito are bundled. Offline these fall back to system fonts.
- 2i editor engine (EigenPal 2.32.0): built and qualified locally, but not yet wired into the production 2i editor, per its own README.

---

## Addendum 3: three meticulous audit rounds (2026-10-26)

Final full suite: 1723 passed, 3 skipped, 0 failed (6 min 01 s). Earlier stability: three consecutive clean full runs before these rounds.

### Round 1 - live conversation path
- 8 SIGKILLs at random moments during a live stream of turns: every store opened cleanly; turn log, receipts and verbatim captures stayed in step (103/103/103); receipt chain and audit hash chain had 0 broken links; every captured byte matched its recorded SHA-256; the next start accepted a new turn.
- Hostile input against /api/pubpartner/turns/live: empty, whitespace, wrong types, NUL, 1 MB, 10 MB (413), path-traversal session/friend ids (all stayed inside the data dir), unknown provider, provider down (503, user text still captured), prompt-injection text (handled as ordinary text).
- FOUND/FIXED: a JSON string containing an unpaired surrogate ("\ud800") caused a 500. Now 400.
- Noted, not changed: session ids that differ only by special characters share files (e.g. "a/b" and "a_b"); changing the naming would orphan existing session files. Turn records keep the original session id, so no text is lost.

### Round 2 - static and route audit (479 routes, 207 state-changing)
- FOUND/FIXED: the same Unicode crash affected ~55 routes. A single front-door guard (modules/unicode_guard.py) now returns 400 on every JSON route. Re-probe: no hostile-Unicode 500s remain.
- FOUND/FIXED: 24 live-control routes had no authorisation at all (broadcast start/stop, switcher cut/transition, stage actors/screens, audio device select, mic profiles, camera boxer override, performance profile, choreo). With PUBCAST_ENFORCE_AUTH on they now require the mod role, via modules/control_plane_guard.py (one auditable table). Default (auth off) behaviour is unchanged.
- FOUND/FIXED: /thinking-context/status returned 500 and its startup log claimed ThinkingContext was "mounted". It is registered but its wrapper lifespan only runs on the next app start, so it is inactive in a normal single boot; RoomConductor drives rooms. Status now answers 503 and the log says so.
- Import scan: 345 modules, 4 do not import (cv2 and openai are optional dependencies; NUDGE_MINIMAL and pubcast_voxel_hollow_patch are snippet/patch scripts living in modules/wired, never imported; the patch script exits on import if imported).
- Unwired (never imported by anything): 16 modules, including response_execution_layer (1,222-line conduct system), littlemode_protocol, security_authority, secure_secrets, prompt_context_builder, unified_bridge, linux_enforcer. Preserved, not deleted. Connecting them changes behaviour and is a decision for Josie.
- Still unauthenticated even when auth is enforced, left as is for Josie to decide: /api/governance/consent, /api/stt/transcribe, /api/tts/synthesize, /api/pubworld/recognize, /api/voxel/block-kit/preview, /api/media/intake, /api/mic/cough.

### Round 3 - Foresight, 2i, shell, offline
- FOUND/FIXED (data safety): in 2i, after a reload the manuscript was restored in memory but the editor looked blank; the first keystroke then replaced the whole manuscript and its recovery copy with that keystroke. Fix: loadDocState writes the restored text into the solo textarea. Verified in real Chromium before and after; regression test added.
- FOUND/FIXED: the global 1 MB request cap rejected any Foresight workspace/file-format save above ~780 KB (advertised limit 32 MB) and 2i documents between 1 and 2 MB (advertised 2 MB). Per-route limits added (Foresight 44 MB, 2i documents 3 MB, media intake 256 MB); everything else stays at 1 MB. Over-limit saves are refused by the route with a clear error and nothing is stored.
- Verified OK: workspace writes are atomic (temp file, fsync, replace) with revision checks; 2i server documents reject stale revisions with 409 and never overwrite; SIGTERM shutdown in 1.2 s with all 10 SQLite databases passing integrity_check; Foresight, Foresight Counter, 2i and Pete Director make zero external requests with all network blocked and zero JavaScript errors.
- Still depends on the network (cosmetic fallback fonts when offline): static/index.html, static/world.html, 2i/index.html request Google Fonts. The served 2i page is writers-room-v22.html.
- Known 404: /assets/rooms/dressing_polish.png (pending Josie's choice).
- 988 / crisis wording remains unreachable on the live path; not changed.

Nothing has been pushed to GitHub.
