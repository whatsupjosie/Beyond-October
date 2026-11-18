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

### Ordinary Reach manuscripts at reload (checked, holds)

`test_reach_manuscript_edit_then_reload_with_host_unreachable_is_kept`: type into a normal (non-file) manuscript, then reload while the host refuses saves. The text comes back from Reach's synchronous `localStorage` recovery (`writeRecovery`), 3 of 3 runs; the status does not claim the host has it. With `writeRecovery` disabled the test fails.

**Test-harness defect found here:** without the injected refusal the test passed even with `writeRecovery` disabled. The hide-time `PUT` reached the host through the harness's Playwright request interception, which a real closing page may not achieve (`reach.js` does not use `fetch` `keepalive`). Any test that relies on a request completing during unload must fail the host on purpose.

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

## Decisions (Josie, 2026-11-18)

1. The exit journal is conditionally approved: the original record is preserved in every case, and it is not released until its recovery and failure tests pass.
2. Recovery and failure messages explain what happened, what was preserved and the next action, and never claim an unverified save.
3. GPT's coalescing probe stays as a permanent regression test.
4. This branch stays separate from PR #13 until the recovery and message work is complete, independently reviewed and tested; then it goes through the existing integration process. No premature merge.

## Update 2 (later 2026-11-18): remaining loss paths, messages, and a protected-data incident

### Rich DOCX at close (checked; protected by warning, not by a copy)

The rich engine is not committed (only its stylesheet and notices are). It was built locally for testing from the pinned recipe (`2i/editor-engine`, `npm ci`, `node build.mjs`, `@docx-editor.dev/core` 2.32.0) and **not committed**; without it "Open local rich editor" reports that rich editing is unavailable. With it:
- An edit typed just before a reload is **lost from storage** (stored working DOCX parsed with python-docx: earlier marker present, last marker absent). Rich bytes come from the engine's asynchronous `saveBytes()`, so a synchronous exit copy is not possible.
- But the reload is guarded: the browser's leave warning fires (2 of 2), and staying keeps the text. Hiding the tab stores the edit (2 of 2), which covers phone backgrounding while the page is alive.
- `tests/test_2i_adversarial_rich_saves.py` (3 tests) holds the autosave, the leave warning and the hide flush in place; removing the hide flush or the leave warning each fails its test. The tests skip, with the build command in the reason, when the engine is not built.
- **Residual risk:** a writer who chooses "Leave" on the warning, or a tab killed without being hidden first, loses the last 1.5 s of rich edits.

### Ordinary manuscripts with browser storage full and the host down (defect fixed)

Filled `localStorage` until even one character was refused (an earlier fill attempt left room; that run was discarded), refused host saves, typed. The leave warning fired and the text stayed, but the status read "Save failed · Reach unavailable": nothing told the writer that no copy existed anywhere or what to do. The status indicator is also cut at 220 px, so a long message would hide its own instruction. Fix in `2i/2i-assets/reach.js`: the status becomes "Not saved · export a copy now", and a one-time notice says what happened, what is unchanged, and to use Export (Ctrl+E) and keep the page open. The test fails on `062eb49` and passes now.

### Recovery write failing on reopen (defect in my own journal code, fixed)

If the checked write that applies a journal failed, a single `catch` reported "Close protection unavailable", which was false, and no download or discard controls appeared. The journal itself survived (it is deleted only after a confirmed write). Now a failed recovery write takes the kept-edits path. New test injects an IndexedDB `put` failure at reopen: the stored record is unchanged, the journal is kept, the alert and download work, and nothing claims recovery. It fails on `062eb49`.

### Messages rewritten to Josie's standard

- Recovered: "Recovered your last edits. This file closed before they were saved; they are now saved in its working copy. The original file is unchanged."
- Kept edits: "Some edits from a window that closed were never saved, and this file has changed since then. Nothing was overwritten: the current version is open here, and those earlier edits are kept separately. Download them to compare, then discard them when you no longer need them."
- Discard confirmation and result say it cannot be undone and that the open version is unchanged.
- Journal unavailable: says the browser cannot keep a recovery copy, that edits still save while the page is open, and to press Save before closing.
- "Recovered" is shown only after `record()` has completed its transaction.

### Protected-data incident: the "read-only" preflight modified the canonical Alex vessel

While diagnosing the two failing checks I ran `tools/workbench_preflight.py` directly, as `CHECK_FORESIGHT_WINDOWS.ps1` does. Its docstring says "read-only", but it starts the app against the checkout's own `data/`: `data/pubpartner/vessels/alex.pubpartner` grew from 147,456 to 192,512 bytes (blob `b487735b…` instead of the canonical `96fa66a728d07d5ff43b0d3d7fc17a466765cec1`), and 43 runtime files appeared, including `data/byok/secure/master.key`. `tests/test_saves_survive_restart.py` caught the vessel change. Nothing was committed.
- Repair: confirmed every new file was dated 17:54 to 17:55 (that run), dry-ran then removed them, and restored the vessel to its committed blob; verified `96fa66a7…` and a clean `data/`.
- Fix: unless `PUBCAST_DATA_DIR` is set, the preflight now runs against a disposable copy of `data/` and removes it at exit (the pattern `conftest.py` already uses). Run directly afterwards: PASS, vessel blob unchanged, `data/` unchanged. pytest and the sandbox runner were already isolated.
- Not added: an automated test that runs the tool against the real `data/`, because a regression would then damage the vessel; the restart test already guards the vessel blob.
- **Risk on Josie's machine:** any earlier run of `CHECK_FORESIGHT_WINDOWS.ps1` or `run_reach.py` from a checkout changes the tracked vessel file in that checkout. Do not commit `data/pubpartner/vessels/alex.pubpartner` from a working checkout without checking its blob ID.

### The two long-standing failures were stale tests (fixed)

`test_writers_room_reach_runtime_is_actually_loaded` and the preflight's two "2i loads Reach…" checks matched the exact string `<script src="/2i-assets/reach.js">`. Commit `bae4696` deliberately made those references relative so 2i opens from disk; served at `/writers-room` they resolve to the same files. The checks now resolve each `src` and `href` against the page URL as a browser does. They pass, and still fail when the reference is broken (missing file name, wrong folder).

### Regression after Update 2

25 existing test files on the 2i path plus the 4 new ones: **143 passed, 0 failed, 1 skipped** (real speech models). Adversarial set 12 of 12, three runs in a row.

## Update 3: rich DOCX engine bundled; Node tests brought into the regression

**Decision (Josie):** ship the rich editor, DOCX, and as many formats as can actually be run.

- **Engine bundled** at `2i/2i-assets/vendor/docx/`: `engine.js`, `harfbuzz.wasm`, 12 local fonts (Liberation Serif and Mono, Carlito; OFL-1.1), built from the pinned recipe in `2i/editor-engine` (`@docx-editor.dev/core` 2.32.0). Two consecutive builds were byte-identical. `PROVENANCE.json` records versions, upstream commit, the build command and a SHA-256 per file. The committed `THIRD_PARTY_NOTICES.md` is kept: the rebuild differs from it only in line endings and trailing spaces. With the engine present the rich tests run instead of skipping.
- **Defect I introduced and missed (fixed):** my exit-journal code registered page listeners through the bare global `addEventListener`. `tests/test_twoi_rich_browser_contract_node.js` runs the file module in a Node harness without one, so mounting failed ("addEventListener is not defined"). Bisect: passes on `7e70e05` and `f39ca7a`, fails from `8501c78` (mine). I missed it because my regression runs were Python-only. Listeners now go through `root` with optional calls. From now on every regression run includes all Node tests.
- **Five Node tests fail on PR #13 without any of this work** (same result on `7e70e05`). All five are stale source-extraction harnesses, not app defects. They belong to the integration line, so they are documented here for its owner rather than edited on this branch:
  - `test_foresight_file_close_node.js` and `wiring_smoke_node.js`: their sandboxes lack `initializing`, which later Reach code reads.
  - `test_2i_offline_save_node.js`: its sandbox lacks `reachFileMode`.
  - `test_2i_typewriter_relay_node.js`: `deepStrictEqual` compares an object created inside a `vm` context; identical content fails on the cross-context prototype. Compare with `JSON` or a plain copy.
  - `test_2i_professional_ui_node.js`: slices `canPresent` up to `"\n  if(reachFileMode)"`, which a later change replaced with `const filePresentation=!!reachFileMode;`.
- **Regression after Update 3:** Python, 2i path plus rich tests: **160 passed, 0 failed, 1 skipped**. Node: **50 passed, 5 failed** (the five above, unchanged from PR #13).

## Update 4: formats ("as many formats as we can run")

**Method.** 32 fixtures made by real producers (LibreOffice 24, pandoc, ffmpeg, Pillow; `tools/make_format_fixtures.py`, `tests/fixtures/formats/MANIFEST.json`, 293 KB) were opened through the real app path in Chromium before any change, and the result recorded per format. `tests/test_2i_format_matrix.py` (32 browser tests) now holds every result. Oracles: original bytes read raw from IndexedDB, exported DOCX parsed with python-docx, downloads compared byte for byte.

**Worked already (now tested):**
- Text, edited directly with exact round trip (edit, save, reopen, export, original unchanged): TXT, MD, CSV, JSON, HTML, Fountain.
- Converted to an editable text copy, with Export DOCX: DOCX, ODT, PDF, PPTX, XLSX.
- Images, displayed with rotate and crop, the edit kept as a PNG working copy and the original unchanged: PNG, JPEG, GIF, WebP, BMP, SVG.
- Audio and video, decoded with the right length: WAV, MP3, OGG, Opus, FLAC, M4A, MP4, WebM, MOV (in the test Chromium; see "Not verified").

**Defects found and fixed:**
1. **RTF opened as raw markup** (`{\rtf1\ansi…`) under "2i text editor ready", inviting edits that could corrupt the file. Now converted to text by a standard-library parser (groups; skipped destinations including font and colour tables, pictures, headers, footers and footnotes; `\'hh` in the document's code page; `\uN` with surrogate pairs; escapes). Checked on LibreOffice and pandoc RTF, an emoji surrogate pair, escapes and an unknown `\*` destination; non-RTF input is refused.
2. **EPUB, ODS and ODP could not be opened** ("Failed to execute 'decode' on 'TextDecoder'"). New converters: EPUB follows the book's own reading order (container, package, spine; paths outside the book refused); ODS gives tab-separated rows like XLSX, without expanding LibreOffice's runs of thousands of repeated empty cells; ODP gives slide text like PPTX, without speaker notes. All use the existing archive and XML limits.
3. **Unknown binaries showed a raw browser error.** Now: "This file is not text that 2i can edit, and there is no converter for its format here. Use Download original to get it back." followed by "The original has not been altered."
4. **Legacy Word `.doc` showed the same raw error.** It is a closed binary format that cannot be read reliably without Word or LibreOffice, so it is not converted; the message says to open it in Word or LibreOffice, save it as `.docx`, and open that copy, and to use Download original meanwhile.

On `d993d26` the six tests for these four defects fail and the other 26 pass; all 32 pass now.

**Harness gap found:** the shared browser fixture routes only `/api/foresight/files/convert` to the real code, so Export DOCX could never complete in tests. The format matrix serves the real export and rich routes itself.

**Not verified / not supported:**
- Media decoding was checked in Playwright's Chromium, which includes proprietary codecs. Firefox does not play MOV/H.264 everywhere, and some Chromium builds lack AAC/H.264; not tested.
- HEIC and AVIF photos (common from phones): no encoder here to make fixtures; not tested.
- Rich (formatted) editing is offered for `.2i` rich archives. Opening a `.docx` gives a text copy, with a button to make a rich `.2i` from the original. Opening a DOCX straight into the formatted editor is the natural next step and is not built.
- Legacy `.doc`, `.pages`, `.key`, `.numbers`, `.wpd` and other closed formats: not converted.

**Corrections after a final self-review:**
- My chat summaries said "27 formats"; the correct count is **30** (6 text, 9 documents, 6 images, 9 audio/video), plus 2 unsupported-file tests, 32 tests in all. The plan document is corrected.
- RTF limitation not stated before: `\'hh` bytes are decoded one at a time in the document's code page. Correct for Western code pages; RTF using double-byte code pages (Japanese, Chinese, Korean) without `\uN` escapes would come out garbled. Modern producers (Word, LibreOffice, pandoc) write `\uN` for such text; not tested.
