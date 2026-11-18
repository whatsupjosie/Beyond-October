# 2i Save Routing and File Recovery Hardening

**Date:** 2026-11-18  
**Source repository:** `whatsupjosie/Beyond-October`  
**Branch:** `codex/2i-save-routing-hardening-2026-11-18`  
**Parent:** `codex/2i-integration-readiness-2026-11-18`, starting SHA `ef879b6d3cbb7fb5365a22ddc5ddd31d3b6adb9c`.

## Goal

Finish wiring the real Save commands and file-open readiness without replacing Fable's document engine or Claude's 2i/typewriter work. An actual Foresight file and a normal Reach manuscript are **different storage owners**. Tests should catch wrongly routed writes, lost recovery options and false readiness, rather than merely checking whether script files exist.

## Confirmed defects repaired

### 1. File-tray Save could write through the wrong storage engine

`2i/2i-assets/reach.js` previously selected `networked ? saveDocument() : saveToFile()` unconditionally. Before `ForesightFiles.mount()` finishes, `saveDocument` still points to Reach's **ordinary manuscript saver**, even though the page belongs to a Foresight file. The Save button, File menu and Ctrl+S can dispatch during that interval. Once mounted, an offline file-tray case could also be routed through the unrelated standalone export.

Now `saveNow()` checks `reachFileMode` first. Before mounting it returns `false`, without invoking any unrelated saver; after mounting it uses the `saveDocument` function rebound to the exact Foresight file session. Normal Reach hosted saving and normal standalone/offline export retain their original behavior.

### 2. Failed Save from File menu/Ctrl+S was not reliably reported

The menu and keyboard shortcuts called `saveNow()` without catching rejected promises. A rejected `session.save()` could produce an unhandled rejection rather than a visible Save error.

File-tray `saveNow()` now catches the error, writes `Foresight file not saved` to the Save status and returns `false`. If an earlier mount failure disabled Save with a recovery instruction, Ctrl+S **does not overwrite that instruction** with a misleading `Opening...` notice.

### 3. Missing Foresight record could masquerade as an opened file

The actual `static/foresight_files.js` returns a session even when a requested file ID has no saved bytes; its `session.activity().recovery` is false. The earlier `file-workspace.js` nonetheless rebound the saver, enabled Save and announced `foresight:file-ready`.

Now the file adapter refuses readiness when no recoverable session exists. Save is disabled, and the host does not receive a ready message.

### 4. Failed working-copy decode could also masquerade as readiness

`ForesightFiles.mount()` catches some decode/load errors internally, calls `options.onError` and returns a session for the preserved original source. It may still report `recovery:true` because the original file is retained. A storage-only readiness check would not detect the failure.

The file adapter records whether `onError` occurred and refuses to announce an editable file as ready when the working copy failed to open.

### 5. Error UI could remove the last recovery control

The earlier file-adapter error handler replaced the entire file-toolbar `textContent`. When `ForesightFiles` had added a `Download original` button for a failed working copy, replacing the toolbar erased it. This became especially dangerous once explicit decode failures were classified as not ready.

Now the adapter **prepends** an accessible error message to the toolbar instead of replacing its children. Original-file and recovery/download controls remain visible.

### 6. Reach navigation could still mutate Foresight file documents

Save was only one entry point. While a Foresight file was mounting, the served editor still exposed ordinary Reach handlers for New, Open, Save As and My manuscripts. Those functions can save or switch a Reach manuscript rather than the Foresight file being edited. Even after file mounting, the Reach-specific manuscript shelf could open a different Reach document inside the Foresight file session.

The original Reach commands now refuse those operations in `reachFileMode`, with a clear Writer's Room notice. Foresight's own `newDocument`, `openDocument` and `saveDocumentAs` handlers replace those originals after its session mounts. The Reach manuscript shelf is hidden on the file route and guarded if called programmatically. The legacy HTML drop handler now blocks an early file import instead of changing manuscript state before Foresight's capturing drop handler is installed.

This does **not** remove normal Reach manuscript navigation. Its original functions still operate when `reachFileMode` is false.

### 7. Background/autosave could bypass the corrected Save dispatcher

Reach's ordinary `markDirty()` still scheduled `saveDocument()` after one second, and its `visibilitychange` handler called `saveDocument()` whenever the tab became hidden. Neither went through `saveNow()`. When `startReach()` completed but the Foresight session was still mounting, these paths could write a different Reach manuscript despite the explicit Save guard.

Added layered defenses: Reach's **default** `saveDocument()` refuses `reachFileMode`; Reach's scheduled autosave and visibility-save handlers skip file routes (Foresight's own session handles these); the file-tray textareas and Save button remain locked from page startup until `file-workspace.js` has installed a recoverable Foresight session. Failed or missing files remain read-only.

The existing Foresight adapter still dispatches its own change notification, uses `session.flush()` for file persistence and flushes at pagehide/visibilitychange. Normal Reach auto-save and normal Reach editor input remain unchanged.

## Verification actually executed

- `tests/test_2i_file_save_dispatch_node.js`: **9 focused checks passed** using actual GitHub `reach.js` saveNow source in an isolated V8 compatibility harness.
- `tests/test_2i_file_host_ready_node.js`: **7 focused checks passed** using actual GitHub `file-workspace.js` in an isolated mock host. Covers normal immediate Save after readiness, account failure, pending login, missing file record, failed mount and decode failure with preserved original download.
- `tests/test_2i_file_navigation_isolation_node.js`: **5 focused checks passed** against actual Reach functions and the HTML drop listener in a V8 compatibility harness. Before and after mounting, file-tray Reach commands are blocked; the normal Reach route is not blocked.
- `tests/test_2i_file_autosave_isolation_node.js`: **7 focused checks passed** from the current Reach source. It covers read-only startup, timer suppression, fail-closed default Save and visibilitychange while preserving normal Reach behavior.
- Red/green check of background saving: the prior file-route visibility handler invoked the wrong Reach saver; the corrected handler does not.
- Red/green check of Save: on parent code, a pre-mount file-tray Save called the wrong Reach saver; on the repaired source, it returned false and did not call Reach.
- Red/green check of file readiness: **3 of 6** new tests failed against the parent file adapter and **all 6** passed on the repair. The failures concerned missing file, mount error/Save availability and working-copy decode failure.
- Production JavaScript parsed after editing.
- These are precise **source-driven V8 checks**, **not native full-repository Node, real FastAPI startup, real browser UI, real storage failure injection or complete integration acceptance**. No GitHub Actions jobs were dispatched for this pass.

## Remaining critical gates

1. Run native Node and Python suites from the **full combined checkout**, including new test files.
2. Start the real authenticated PubCast host in Chromium; open a normal Reach manuscript and a Foresight file, Save through button, menu, Ctrl+S and host `prepare-close`, close/reopen, compare the exact text, protect locked lines and verify offline recovery.
3. With disposable Foresight records, inject missing ID, corrupt working file, storage exception, and late edit during Save. Verify the original download survives and no incorrect `ready` or `Saved` status is emitted.
4. Test phone/tablet and Claude typewriter inside both editor routes. Preserve Fable's notebook and Claude's distinct phone/layout branch; their full designs have **not** been combined or accepted here.
5. Test studio recording, clacker, speech lifecycle, packaging and independent acceptance separately.

**Release state:** protected branch only, not beta-ready. Do not merge into `main` until the full runtime tests pass. Original GPT, Claude and Fable branches and backups remain unchanged.
