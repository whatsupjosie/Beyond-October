# Integration ledger, 2026-11-04

Branch: `integration-2026-11-04` (local; not pushed, not merged to `main`).
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
- Whole pytest suite, run 2 (after all fixes): **2,222 passed, 2 failed, 6 skipped**, 803 s.
  - `test_portable_save_as_and_reopen_uses_real_disk_without_vendor_picker`: failed once under full-suite load; passed alone. Load-sensitive, not explained.
  - `test_production25d_browser.py::test_multiple_takes_keep_original_media_bytes`: one of the recording tests already documented as flaky (a recording stopped within about two seconds produces no data). Alone on the merged tree it passed 3 of 4 times; alone on `main`, `gpt-work` and `claude-work` it passed every time I ran it (3, 2 and 2 runs). I did not fix it; the sandbox README says that needs Josie's go-ahead.
- The 6 skips: two Alex Little One research tests (off by design) and four speech tests that need the speech models installed (`PUBCAST_SPEECH_TEST_MODELS`, audio decoder dependencies). **The real-model speech acceptance did not run here.** GPT's recorded evidence for it stands as GPT's.

## Cross-feature check (RAN)

On the merged tree: real host, owner set up, a note with a 3,000,000-byte attachment, a saved speech choice (revision 1); host stopped; offline checkpoint; restore into a new directory; original data directory deleted; restored host started; sign-in. Result: same permanent user ID, the note with its subject and project, the attachment byte-identical (SHA-256 equal), and the speech choice at revision 1. This shows the checkpoint covers the new notes and speech data, which are inside the host data directory.

## Read, not run (review notes, nothing changed)

- `modules/production_notes.py`, `static/production_notes.js`, `modules/userdb.py` changes, `modules/data_checkpoint.py`, `modules/speech_*.py`, `modules/stt_engine.py`, `modules/tts_engine.py`, `static/speech_client.js`, `modules/recording.py` changes were read in full. No injection sinks found in the new JavaScript (no `innerHTML`, `eval`, or similar).
- `/api/production/people` returns every account's email to every signed-in member. Under Josie's one-user-per-copy model this goes away with the crew-accounts route, which Claude's own handoff says to rework.
- `NotesStore` opens a SQLite connection per call using `with conn:`, which commits but does not close; CPython closes them when they are dropped. Low risk here, but a handle can linger on Windows.
- `/health` now calls `status()` on both speech engines on every request; for the neural voice that opens the voice archive each time. Low cost, worth caching if `/health` is polled often.
- `production_notes.js` keeps polling every 20 seconds when signed out or when no host answers.
- The "Use server TTS" checkbox on the Control page now starts checked and is relabelled "Local speech (recordable)". That is a behaviour and wording change in GPT's work; Josie should confirm it.

## Not verified

Windows and PowerShell 5 (everything), physical microphones and speakers, real speech models in this environment, phones, a second machine, long sessions, power loss. Nothing here was run through GitHub Actions.

## Still open (not touched)

Crew-accounts route and `@production` against the one-user model; the profile "About me" section; the PubPartner connector; email replies into PubCast; PC-004 (reconcile the later participant-audio package); the flaky recording tests; the Blackbox socket-close error on reload (PC-024).
