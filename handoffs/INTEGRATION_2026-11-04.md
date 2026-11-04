# Integration ledger, 2026-11-04

Branch: `integration-2026-11-04` (published on GitHub; not merged to `main`; the latest head is whatever the branch shows, and this ledger records work up to the sections below).
Written by Claude at Josie's request ("integrate our features in and go over Claude's coding, or go over GPT's coding work, troubleshooting and debugging").

## What was merged

| Side | Branch | Head | Content |
| --- | --- | --- | --- |
| A | `claude-work` | `295b556` | Production notes (sticky notes), PubCast profile, Easter egg, test sandbox runner |
| B | `gpt-work` | `43e7183` | Offline host-data checkpoint and restore, mono WebM export fix, local speech (dictation and read-aloud) |

Common base: `main` at `bfbdcf0`. The only file both sides changed was `main.py`, and git merged it without a conflict. I read the merged result: the notes router mount and the speech router mount are independent and both present.

## Defects found and fixed during the integration

Each was reproduced before it was fixed, and the same reproduction was run again afterwards.

1. **Sticky-note attachments over 1 MB were refused by the real host** (`main.py`, `BodySizeLimitMiddleware`). Notes allow 10 MB per file and 25 MB per note, but the host's default body cap is 1 MB, and `/api/notes` was not in its list of larger routes. Claude's notes tests mount the router on a bare app and never met the middleware. Reproduced through `run_reach.py`: 0.9 MB accepted, 1.5 MB and 5 MB refused with "Request body too large (max 1MB)". Fix: `/api/notes` allows 26 MB at the guard; the route still enforces its own 10 MB and 25 MB limits. After the fix: 1.5 MB and 10 MB accepted, 10.5 MB refused by the route. New test `tests/test_production_notes_host_limits.py` (3 tests) puts the real middleware in front of the real router; with the fix removed, 2 of its 3 tests fail.
2. **2i broke when opened on its own** (`2i/writers-room-v22.html`, from `gpt-work`, not from the merge). GPT's change called `window.PubcastSpeech` unconditionally. Opened from disk and offline, `/static/speech_client.js` is not served, the page threw during start-up, and typing stopped being committed. The existing data-safety test `tests/test_2i_reload_restores_solo_text.py` fails on `gpt-work` alone and passes on `main` and `claude-work`. Fix: when the local speech script is absent, 2i uses its original browser-only read-aloud and voice input (the removed code, restored as the fallback). With the script present, behaviour is GPT's.
3. **Two 2i file-workspace tests became ambiguous** (from `gpt-work`). The new dictation control adds a second `role=status` region to the 2i page; two tests looked it up strictly and matched two. Fix in `tests/test_foresight_file_workspace.py`: both lookups now name the 2i file-controls region. The text asserted is unchanged.
4. **Eight walkable-world browser tests failed on console errors** (from `claude-work`). The notes script asks `/api/notes` on load; those tests serve the page from a plain file server with no host, so the request 404s, and the tests treat any console error other than the `/health` probe as a failure. Fix in `tests/test_world_walk_browser.py`: the same host-less exemption now also covers `/api/notes`. Every other console problem still fails.

## Test results (Linux, Python 3.13 venv, Chromium 153 with software WebGL, Playwright 1.63.0)

- Sandbox `fast` tier on the merged tree: PASS (372 Python files compile, 28 Node tests, packaged-route preflight, 32 backend tests, `data/` untouched).
- Sandbox `standard` tier before fixes 2 and 3: 4 browser failures (the two 2i tests above and two known-flaky recording tests).
- Whole pytest suite, run 1 (before fixes 2 to 4): 2,212 passed, 12 failed, 6 skipped.
- Whole pytest suite, run 2 (after the first four fixes): 2,222 passed, 2 failed, 6 skipped, 803 s. (Superseded by the final run in "Second review" below: 2,237 passed, 0 failed.)
  - `test_portable_save_as_and_reopen_uses_real_disk_without_vendor_picker`: failed once under full-suite load; passed alone. Load-sensitive, not explained.
  - `test_production25d_browser.py::test_multiple_takes_keep_original_media_bytes`: one of the recording tests documented as flaky. **Fixed afterwards, see "Recording tests" below.**
- The 6 skips: two Alex Little One research tests (off by design) and four speech tests that need the speech models installed (`PUBCAST_SPEECH_TEST_MODELS`, audio decoder dependencies). **The real-model speech acceptance did not run here.** GPT's recorded evidence for it stands as GPT's.

## Recording tests (fixed after the full run)

Root cause: the tests stopped recording after a fixed 1.1 s delay, before the browser's recorder had produced its first chunk, so the studio had nothing to save. The tests now wait for a real non-empty chunk (a read-only counter in the test fixture; the studio is unchanged). Applied to the multiple-takes, failed-storage, panic, recorder-error and reload-and-play tests. Evidence: 30 of 30 idle passes; with both CPUs kept busy for the whole run (load average about 4.5 on 2 CPUs) the old tests failed 3 of 5 and the new ones passed 15 of 15 (three runs of five). An earlier version of this note claimed 10 of 10 under load; that run's load generator had stopped partway, so it was corrected. `tools/sandbox/README.md` "Flaky tests" is updated.

## Second review, three rounds (2026-11-04, after Josie asked for a check for cut corners)

Round 1, audit of my own claims. Found: (1) the load evidence for the recording fix was overstated (corrected above); (2) the 2i speech code had no test of its own, since the only coverage needs the real speech models; (3) the full suite and the fast tier had not been re-run on the final tree. Checked and held up: no HTML-injection sinks (`innerHTML`, `eval` and the like) in the new scripts; `/health` answers with the speech models absent; the larger notes body limit applies only to the single upload route.

Round 2, troubleshooting. Each item was reproduced, fixed, and shown to fail without its fix:
1. **2i speech wiring now has tests** (`tests/test_2i_speech_wiring.py`, 11 tests): standalone read-aloud, superseded and cancelled utterances, no browser speech at all, browser voice input, and the hosted path through the local client (clamped speed, cancel, failure message, cancelled result). With GPT's original 2i page the five standalone tests fail; two deliberate breakages of my own fallback code were each caught.
2. **Standalone 2i had silently lost its original read-speed range.** GPT narrowed the slider to 0.7 to 1.5 in steps of 0.1 for the local voice. With no local voice, 2i now restores 0.5 to 2.5 in steps of 0.25, as before. Hosted behaviour is unchanged.
3. **The notes store left database connections unclosed** (`with connection:` in sqlite3 commits but does not close). It now closes every connection it opens. Before: 51 "unclosed database" warnings in the notes tests; after: 0. New test fails without the fix.
4. **The notes upload route never closed the multipart form it parses itself.** Uploads over 1 MB spool to temporary files on disk, and a refused note (too large, no recipient) left them open until garbage collection. The route now always closes the form. New test fails without the fix.
5. The other backend areas (checkpoint, speech, recording, userdb) were scanned with resource warnings on: none found.
6. **Not explained:** `test_portable_save_as_and_reopen_uses_real_disk_without_vendor_picker`, which failed once in the first full run. It passed 16 of 16 repeats under sustained load and in the final full run. I could not reproduce it, so I cannot say what caused the one failure.

Round 3, regression on the final tree (Python 3.13 venv for pytest, Chromium 153 software WebGL): whole suite **2,237 passed, 0 failed, 6 skipped** (820 s). Sandbox `fast` tier (clean room, Python 3.12): PASS in 36 s (372 Python files compile, 28 Node tests, packaged-route preflight, 32 backend tests, `data/` untouched). The 6 skips are unchanged: two research tests that are off by design and four that need the real speech models.

Still not verified, unchanged: Windows and PowerShell 5, physical microphone and speakers, real speech models, phones, a second machine, long sessions, power loss.

## After the second review: email visibility (PC-038 / PC-015, first step)

`GET /api/production/people` used to return every account's email address to every signed-in member. It now returns an address only to its owner and to the owner and moderators, who add the crew and need it to address an email copy. Other members see names, IDs and roles. The "Also send as email" link still works for those who can see addresses; for others it says "No email address available to you for ...". New test (fails without the change); notes tests and the notes browser test pass. **This is a decision Josie should confirm:** it keeps the email-copy feature for the people who run the production and closes the leak, but the fuller one-user-per-copy and invited-guest model (PC-038) is not built. Usernames and roles are still visible to all members.

## Place sticky note (PC-037, first part)

The notes menu now has a **Place sticky note** button: pick a room (the room you are standing in first, marked), then a place in it, then the writer opens with that place already chosen (the makeup mirror always stays on). Rooms and places come from the existing `static/world/note_spots.json`, so a place appears in the picker as soon as it is added there. Escape steps back (writer to menu, places to rooms, rooms to menu). New real-browser test (fails without the change); the other walker and notes browser tests still pass (26). **Not built, still PC-037:** the personal user menu itself (user ID, subscriptions, history and so on) with a sticky-note section that lights up on unread; right-click "Place sticky note" on an object; most of the places Josie listed (only five have positions today, and those positions are marked "proposed, for Josie to correct" in the spot file, so painting new ones needs her picture coordinates or her eye).

## Fixes that needed nothing from Josie (PC-024, PC-023, PC-006, PC-021)

Each was reproduced before it was fixed, and each new test fails without its fix.
1. **Blackbox capture socket (PC-024).** A page reload mid-capture dropped the socket without a close frame, and the handler's final `ws.close()` raised `WebSocketDisconnect` into the server ("Exception in ASGI application") at `modules/blackbox_routes.py:146`. Both close calls now tolerate a socket that is already gone. The audio already committed was kept before and after. Test: `tests/test_blackbox_capture_disconnect.py` (real loopback server and sockets; a dropped socket and a polite close without `stop`).
2. **Notes polling (PC-024).** The notes client asked for new notes every 20 s forever, signed out or with no host. It now waits 20, 40, 80, 160, then 300 s between failed asks and returns to 20 s on the first answer. Test: `tests/test_production_notes_polling.py` (real script, controlled clock).
3. **Integrity checker (PC-023).** `modules/integrity_checker.py` recorded `restored=True` and logged "corrupted and restored" for every failed check, but nothing in it or in the vault restores anything. A failed check is now "corruption_detected" with `restored=False`; a check that could not run is "check_failed"; the statistics report both and never report restored files. Docstring corrected. The checker is not mounted anywhere in the app and the vault engine has no `verify_file_integrity`, so this makes the record truthful; it does not make the checker work against the vault (PC-023 stays open for real repair). Test: `tests/test_integrity_checker_truthfulness.py`.
4. **Very short takes (PC-006).** Measured on the real studio page: on an idle machine a Stop 150 ms after Record saved a take (about 10 KB); with both CPUs saturated the same Stop lost the take 3 of 3 times with "Recorder generated no video data" (600 ms was saved). An ordinary Stop now waits up to 3 s for the recorder's first data before stopping; PANIC still stops immediately. With the change, under the same load, 4 of 4 short takes were saved. Test: a deterministic slow-recorder stand-in in `tests/test_production25d_browser.py` (fails without the change). This changes product behaviour: a Stop within the first second or so can take up to a second longer to finish.
5. **PubWorld Set page offline (PC-021).** `static/pubworld_stage.html` (a selectable program in the Foresight list) loaded three.js r128 from cdnjs, so with no internet it showed nothing. It now loads `static/vendor/three-0.128.0/build/three.min.js`, the same r128 build from npm `three@0.128.0` (SHA-256 recorded in that folder's `PROVENANCE.json`, with its MIT licence). Tests: `tests/test_pubworld_stage_offline.py` (no external script or stylesheet; the file matches its recorded hashes; the page starts in a real browser with every non-local request refused and no page errors). Reverting the page to cdnjs makes two of the three tests fail. **Decision for Josie:** this is a second three.js copy beside `three-0.160.0`, on purpose. The Set page is a classic script written for r128; moving it to 0.160.0 changes lighting units and colour handling and needs a visual check by her. The handoff note's "do not restore an older path" refers to the shared 0.160.0 tree and is not violated, but she should confirm she wants two copies. Other pages still load three.js from a CDN (index, map, world, stage_3d and others); I did not touch them because they are demo pages, not program entrances.

## Cross-feature check (RAN)

On the merged tree: real host, owner set up, a note with a 3,000,000-byte attachment, a saved speech choice (revision 1); host stopped; offline checkpoint; restore into a new directory; original data directory deleted; restored host started; sign-in. Result: same permanent user ID, the note with its subject and project, the attachment byte-identical (SHA-256 equal), and the speech choice at revision 1. This shows the checkpoint covers the new notes and speech data, which are inside the host data directory.

## Read, not run (review notes, nothing changed)

- `modules/production_notes.py`, `static/production_notes.js`, `modules/userdb.py` changes, `modules/data_checkpoint.py`, `modules/speech_*.py`, `modules/stt_engine.py`, `modules/tts_engine.py`, `static/speech_client.js`, `modules/recording.py` changes were read in full. No injection sinks found in the new JavaScript (no `innerHTML`, `eval`, or similar).
- `/api/production/people` returns every account's email to every signed-in member. Under Josie's one-user-per-copy model this goes away with the crew-accounts route, which Claude's own handoff says to rework.
- `NotesStore` opened a SQLite connection per call using `with conn:`, which does not close it. Fixed in the second review (see above).
- `/health` now calls `status()` on both speech engines on every request; for the neural voice that opens the voice archive each time. Low cost, worth caching if `/health` is polled often.
- `production_notes.js` keeps polling every 20 seconds when signed out or when no host answers.
- The "Use server TTS" checkbox on the Control page now starts checked and is relabelled "Local speech (recordable)". That is a behaviour and wording change in GPT's work; Josie should confirm it.

## Not verified

Windows and PowerShell 5 (everything), physical microphones and speakers, real speech models in this environment, phones, a second machine, long sessions, power loss. Nothing here was run through GitHub Actions.

## Still open (not touched)

Crew-accounts route and `@production` against the one-user model (email visibility is the first step, done); the profile "About me" section; the PubPartner connector; email replies into PubCast; PC-004 (reconcile the later participant-audio package; needs the Nov 1 files); the user menu and right-click placement; real vault repair (PC-023).
