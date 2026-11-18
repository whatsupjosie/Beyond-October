# 2i functional integration: Claude typewriter → Fable manuscript (2026-11-18)

## Branch and preservation

Development branch: `codex/2i-typewriter-manuscript-bridge-2026-11-18`  
Parent branch: `codex/2i-claude-functional-reconcile-2026-11-18`.  
Both remain unmerged. **`main` and the original Claude/Fable branches are untouched.**

Exact source checkpoints retained at:
- `backup/claude-console-touch-typewriter-2026-11-17`: `3ee394a7ca66edd5e152eb0eca4de1709333bd7c`
- `backup/claude-2i-beta-polish-2026-11-17`: `df737caaeff206e4128932532663776af74ec0e8`
- `backup/fable-2i-beta-polish-2026-11-17`: `cbc529583202628075c4c319482ae011da2a123f`

## Implemented integration (source-level, pending full hosted acceptance)

1. 2i uses **Claude's actual typewriter console** at `/typewriter-console?embedded=2i` via a same-origin iframe; the original mapping, touch gestures, hardware keyboard mirroring, artwork and audio remain in their original files.
2. Embedded `pubcast:key` messages are forwarded to 2i. Only events originating in **that iframe and with matching origin** may edit the current document. No third-party frame can send editor commands.
3. New `2i/2i-assets/typewriter-input.js` inserts into the existing Write textarea or Collab draft textarea, retaining selection and caret. It uses the browser's native `insertText` command when available to retain real undo; fallback dispatches input events. Backspace handles Unicode grapheme clusters, and editor read-only/disabled states block edits.
4. Claude's bench page remains independently functional; only `?embedded=2i` disables its own competing text buffer and mirrors the editor's text from 2i.
5. `Expand keys` enlarges the console for touch without disconnecting the document. Escape or changing views collapses it.
6. The embedded sound switch is optional and **off by default** unless an existing preference opts in. Older Fable `twoi.typewriter.audio.v1` click/bell preferences are read during migration; the separate standalone bench keeps its original default.
7. Repair to the preceding reconciliation: metadata-only undo now remaps locked-line indices and chapter boundaries through later textual changes. If mapping is ambiguous, it **refuses the undo and preserves the history**, rather than silently locking the wrong paragraph.

## Evidence actually executed

- **7 native Node unit tests passed** on the authored typewriter-input adapter in a temporary ChatGPT container using Node 22. The identical test file is committed at `tests/test_2i_typewriter_input_node.js`; the full repository native test run is not yet done.
- **7 real system Chromium checks passed** against the typewriter-input adapter in ChatGPT's container: cursor insertion, native Ctrl+Z, selection replacement, Return, Space, Backspace, read-only protection. These were isolated document-input checks, **not** a complete hosted app test.
- **4 source-focused V8 checks passed** against the current GitHub `studio-desk.js`: frame source/origin checks, Write vs Collab routing, blocking during generation, expanding/collapsing.
- The actual GitHub `static/typewriter_console_demo.js` was source-exercised in an isolated DOM harness. Its standalone typing still updated bench paper; its embedded mode forwarded a key and accepted paper synchronization only from the correct origin.
- The actual GitHub `soloTextarea` input-handler section was source-exercised against the input adapter. New text updated `committed` and marked dirty; an attempted edit to a protected line was rolled back without marking the manuscript dirty.
- **5 metadata undo checks passed** in an isolated V8 harness from the GitHub editor source: later writing preserved, real text undo preserved, moved lock indices remapped, and ambiguous chapter movement blocked.

These are separately scoped proofs. **Do not add them to Claude's independently reported 2,283 or 2,302 Python-test counts.** They do not establish total application readiness.

## Tests committed for complete checkout

- `tests/test_2i_typewriter_input_node.js`
- `tests/test_2i_typewriter_relay_node.js`
- `tests/test_2i_typewriter_studio_bridge_node.js`
- `tests/test_2i_typewriter_editor_handler_node.js`
- `tests/test_2i_typewriter_embedded_browser.py` (real disposable authenticated Reach host)
- Expanded `tests/test_2i_metadata_undo_node.js`

Run:

```sh
node --test tests/test_2i_typewriter_*_node.js tests/test_2i_metadata_undo_node.js
python -m pytest -v tests/test_2i_typewriter_embedded_browser.py tests/test_2i_single_page.py tests/test_2i_hosted_layout.py
```

For beta sign-off, also run all Node, Python, Playwright, real manuscript persistence, recording, and packaging gates. No full-host acceptance run has been completed in ChatGPT's limited checkout environment; GitHub Actions still fails before runners are assigned.

## Known remaining work, not silently declared complete

- The hosted integration needs actual end-to-end Chromium execution against a **complete checkout of the combined branch**, including Save Now/reload, undo history, locked-line protection, enlarged touch controls, sound and data retention in Write/Collab modes.
- `file://` offline standalone 2i still has its preexisting presentation limitations. Interactive typewriter is currently wired to the **hosted route**, not to a standalone file copy.
- Claude's separate `2i-beta-polish` phone layout/CSS and additional `tests/test_2i_polish_browser.py` remain safeguarded on the original and backup branches, **not merged wholesale** over Fable's distinct notebook and page-layout work. Functionality-first reconciliation remains necessary.
- iPad Safari, real speaker listening, studio camera/recording acceptance and Windows packaging remain unverified.
- The new code does not merge or overwrite the original Claude, Fable, or `main` refs.

**Release decision: draft-only.** Preserve the source, run acceptance, and only then consider merging.
