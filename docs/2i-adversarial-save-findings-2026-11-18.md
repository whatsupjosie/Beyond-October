# 2i adversarial save findings, 2026-11-18

**Branch:** `claude/2i-coalesce-saves-2026-11-18`, based on `codex/2i-save-routing-hardening-2026-11-18` at `7e70e05` (draft PR #13). Nothing was merged into `main`, PR #13, or any GPT, Fable or backup branch.
**Scope covered:** Mission 1 (write amplification) completely, plus the failure-injection and mutation parts of Missions 3 and 5 that apply to saving. Missions 2, 4 and the rest of 5 are **not done**; see "Not done" below.
**Environment:** Linux cloud container, Python 3.13 venv, Chromium build 1243 (headless, software WebGL) driven by Playwright 1.56. No Windows, no PowerShell 5, no phone, no physical disk failure.

## Defects reproduced

### D1. Write amplification: one storage write per keystroke (confirmed, fixed)

- **Reproduced independently** in a real browser, not only in GPT's source-extracted probe: 40 real keystrokes in the served 2i file editor caused **41** `put` calls on the `files` IndexedDB store, counted by a browser-level hook on `IDBObjectStore.prototype.put` (not the code's own counters). GPT's probe gave 40 record calls for 40 edits.
- **Cause:** `2i/2i-assets/file-workspace.js` `markDirty` called `session.flush()` on every edit, bypassing Foresight's own 350 ms debounce in `static/foresight_files.js` `dirty()`. `persistRaw()` also took a separate snapshot and queued a separate record write for every call, so concurrent calls were never merged.
- **Fix:** `markDirty` no longer flushes; edits use the debounce. `persistRaw()` coalesces: a save that is queued but has not started takes its snapshot when it starts and absorbs later callers; a save already in flight is never joined. Debounced save failures are also shown in 2i's top-bar `saveIndicator` (`onSaveError`), which the removed flush used to do.
- **After:** 40 keystrokes, **1** write, stored text equal to the typed text.

### D2. Unsaved text is lost when the page reloads, closes or is killed (confirmed, fixed)

- **Reproduced:** type, then reload before the debounce fires, then reopen. On the parent `7e70e05` the stored text was `start\nLAST-EDIT-B` for typed `LAST-EDIT-BEFORE-RELOAD` (tail lost) in one run; the loss is timing-dependent there. On my first fix `f39ca7a` **the whole edit was lost every time**: removing the per-keystroke flush moved all recent typing into the window that the exit flush must cover. **D2 was made worse by my own earlier commit `f39ca7a`.**
- **Cause, traced:** a `localStorage` trace across the reload showed `pagehide`, then a `files readwrite` transaction opening, then nothing: no `put`, no `complete`. `record()` checks the revision with a `get` and issues the `put` only inside the `get`'s `onsuccess`, which needs another event-loop turn that a page being torn down never gets.
- **Which writes survive a reload** (standalone page, 5 reloads each, normal Chromium / `--single-process`): blind `put` + `commit()` 5/5 and 5/5; `get` and `put` queued together + `commit()` 5/5 and 4/5; the current pattern (put inside the get's callback) **0/5 and 0/5**. A control write during normal operation 5/5.
- **Fix: exit journal.** On `pagehide`, and when the tab becomes hidden, with unsaved text or a save in flight, the session writes `{draft, title, twoiState, baseRevision}` synchronously to a separate database `pubcast-foresight-exit-v1:<owner>`. On the next open:
  - journal text equal to the stored text: the journal is deleted;
  - journal base revision equal to the stored revision: it is written through the normal checked `record()` **before** the file is declared ready, then deleted; the status says "Recovered unsaved edits from when this file was last closed · saved";
  - otherwise (the file was saved elsewhere since): the real record is **not** touched, the journal is kept, and the pane shows an alert with "Download unsaved edits" and "Discard unsaved edits".
  After every fully successful save the session deletes any journal it wrote.
- **Why not a blind write of the real record at exit:** it would skip the stale-writer check, so a closing stale window could overwrite a newer save from another window. The journal never overwrites the real record.
- **Why a separate database:** `static/foresight_file_shelf.html` lists the whole `files` store; a journal there would appear as a phantom file.

### D3. A stale window's unsaved text was discarded with no way back (confirmed, fixed by D2's design)

- On `7e70e05` and `f39ca7a`: another window saves a newer revision; this window's debounced save is refused ("changed in another window", shown correctly); on reload this window's typing is gone. The newer save was **not** overwritten on either commit.
- Now the newer save is still untouched and the stale window's text is kept and downloadable.

## Tests (all real browser unless marked)

`tests/test_2i_adversarial_saves.py` (oracles: browser-level `put` counters, raw IndexedDB reads of `files` and the exit journal), and `tests/test_2i_write_amplification_probe.py` (runs GPT's probe, source-driven, mock store).

| Test | `7e70e05` parent | `f39ca7a` first fix | this commit |
| --- | --- | --- | --- |
| 40 keystrokes, at most 3 writes, exact text stored | FAIL (41 writes) | pass | pass |
| reload inside the debounce window, whole edit stored | intermittent (failed once, passed once) | FAIL | pass |
| clean save then reload: no journal, no false recovery | pass | pass | pass |
| hide with unsaved text writes the journal; next save removes it; no false warning | FAIL | FAIL | pass |
| stale window never overwrites a newer save; its text is kept and downloadable | FAIL | FAIL | pass |
| probe: 40-edit burst, at most 3 record writes (source-driven) | FAIL | pass | pass |

Repeated 5 times on this commit: 6 passed each time. Regression: the 25 existing test files that touch the 2i file path, plus the 2 new files: **135 passed, 2 failed, 1 skipped** (before this work the same 25 files gave 129 passed, 2 failed, 1 skipped). The 2 failures (`test_writers_room_reach_runtime_is_actually_loaded`, `test_preflight_checks_real_reach_routes_and_assets`) fail identically on `7e70e05` without any of this work. The skip needs real speech models.

## Mutation check (each mutation applied alone, then reverted; file contents verified restored)

| Mutation | Caught by |
| --- | --- |
| exit-journal write removed | reload, hide and stale-window tests |
| coalescing guard removed | probe test only (the browser burst test passes on the debounce alone) |
| per-keystroke flush restored | browser burst test |
| journal applied regardless of revision | stale-window test |
| top-bar save error removed | stale-window test |
| journal never deleted after a save | hide test |

## Defects found in tests, including my own

1. **My first in-browser exit experiment was invalid.** Its hook checked `location.pathname` at install time, when the iframe is still `about:blank`, so it never ran. Discarded; redone in a standalone page.
2. **My reload test first waited for my own "Recovered" wording**, so it would fail even if the text had been saved normally. Mutation M3 exposed it. It now waits for either message and asserts the stored text.
3. **My hide test first asserted the journal still existed right after hiding.** Hiding also runs the normal flush, which completes and correctly removes it. It now proves the journal write with the put counter.
4. **GPT's probe is outside the suite** and was the only check that catches a removed coalescing guard. It is now run by `tests/test_2i_write_amplification_probe.py`. Its sandbox lists the closure's variables by hand, so new state (`queuedPlain`, `exitWritten`) had to be added there; it otherwise throws `ReferenceError` before measuring anything.
5. The probe and the earlier GPT tests are **source-extracted**; they do not prove browser or storage behaviour. The browser tests above do not prove disk durability below IndexedDB either.

## Not verified

- Real tab close, browser crash, OS kill of a background tab on a phone, power loss. Reload and a simulated hide were tested; `pagehide` on a real close and on mobile background kill is expected to behave like reload but was **not** run.
- Firefox and Safari. `IDBTransaction.commit()` is used when present; older browsers fall back to auto-commit, which was not tested.
- The rich DOCX editor path, image and media files: the exit journal covers plain-text and 2i text sessions only. Rich DOCX save at exit is unchanged and still subject to D2.
- 2i's own manuscript autosave (`pubcast2i-autosave-v2-*`, 3 s debounce) uses the same read-then-write pattern risk at exit; not changed.
- Windows and PowerShell 5, the full `run_reach.py` host, two real windows on two machines.

## Not done (remaining missions)

- **Mission 2**, seeded chaos runner across type, save, undo, switch, lock, hide, reopen: not built. The tests above are hand-ordered sequences, not seeded random ones.
- **Mission 3** beyond storage: Reach API, file-session mounting, host/iframe message delay and reordering are not injected yet.
- **Mission 4**, protected text (IME, emoji, multiline paste, Replace All, typewriter, undo/redo against locked lines): not started.
- **Mission 5** beyond saving: Claude, Fable, GPT branch comparison, phone, the three writing presentations: not started.

## Decisions for Josie

1. **The exit journal is new state** (a separate database, owned by `foresight_files.js`, deleted once applied). The project rule is one owner per piece of state; the real record stays the only source of truth, and the journal is a recovery buffer. Confirm or reject the design.
2. **Wording** of the recovery status, the conflict alert and its two buttons is mine and can be changed.
3. **The probe now runs in the suite.** Its header still says it is outside the ordinary suite; I left GPT's text unchanged.
