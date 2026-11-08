# Primp troubleshooting round one

Date: 2026-11-07 (Los Angeles). Scope: the existing Primp surface-painting foundation. Status: **UNRELEASED; the 3D acceptance gate remains open.**

Starting local source: `c6dcccb`. Matching previously saved remote source: `9c3c14c0460378b0277fdefb92576b667d9d0e71`; shared tree `77e59f8f93bf2421c7c2bea0625565c6723d547d`. Local and remote commit identities differ because the source was saved through the connected repository service; tree identities match.

## Defects found and corrected

| Finding | Evidence and correction |
| --- | --- |
| Large embedded avatars could not reopen | Before editing, an executed Node probe passed at 1 MiB and threw `RangeError: Maximum call stack size exceeded` at 5 MiB and 20 MiB. The repeated-group base64 regex exhausted V8's stack. Replaced it with bounded length/padding checks and a non-repeating invalid-character scan. A 5 MiB exact-byte round trip, malformed encodings, and the encoded size boundary now pass. |
| Download requests falsely cleared the unsaved flag | Source inspection: the previous save handler set `dirty = false` immediately after clicking a download link, without a completion signal. Supported browsers now use a file picker and wait for write AND close; cancel/write/close failures retain protection. The download fallback deliberately does not claim a confirmed save. Serialization happens after opening the picker to preserve user activation. Node writer doubles exercise success, delayed close, cancellation, failed write/close, fallback, and serialization failure. No physical native picker interaction is claimed. |
| Recovery could silently overwrite another tab | Source inspection: unconditional `put(snapshot, 'recovery')`, with no revision check. Added a compare-and-replace in one IndexedDB read/write transaction. Real browser tests with two independent connections verify stale writer refusal, exactly one concurrent winner, legacy record migration, and preservation after DataCloneError. A cancelled or failed recovery replacement does not adopt the newer revision. Previously queued local writes settle before recovery is read. Protection applies between updated writers; an older running build that still writes unconditionally is not covered. |
| Undo/redo could lose entries when a callback failed | The previous implementation popped before invoking the command. Entries now move only after successful application. If a callback fails after changing state, the inverse is attempted before rethrowing; the entry stays available. Executed fault-injection tests cover failed undo and redo, state rollback, stack retention, and memory accounting. If both a command and its inverse fail, recovery cannot be guaranteed and the error is surfaced. |
| Empty strokes consumed real undo history | Tile finalization previously retained every touched tile, even if no pixels changed. It now removes unchanged tiles and returns no command for an empty edit. Actual browser Canvas checks confirm no-op edits consume no entry and a one-pixel change retains only its changed tile. Clear-layer handling was updated for the no-op return. |
| Stroke errors could leave input stuck or untracked | Inspection showed final pixel capture outside the error guard, and cancellation/lost-capture handlers that did not check the pointer ID. Completion now rolls back on failure, releases pointer capture in finally, and ignores unrelated pointer cancellations. If rollback also fails, the look stays marked unsaved. These UI paths were reviewed and syntax checked; rendered pointer/failure acceptance remains blocked. |
| Graphics failure unnecessarily blocked saving CPU-side work | Save no longer requires a working renderer after an avatar has loaded; undo and visual controls remain disabled during graphics loss. A graphics failure is kept visible after another asynchronous operation finishes. No actual active-model context-loss/save UI test was possible here. |
| Invalid surface records produced an incidental TypeError | Null paint targets now fail at the schema boundary with the explicit paint-surface validation error. Executed regression added. |

Also corrected an overbroad test/comment claiming a distance heuristic prevents all UV-island crossings. It only breaks large atlas jumps; nearby islands and edge bleed remain a real open release issue.

## RAN

- Linux / Node v24.22.1 / Python 3.12.14.
- `node --test tests/primp/*.test.mjs tests/test_voxel_block_preview_client_node.js tests/test_foresight_file_close_node.js`: **17 passing entries, zero failing**, including the two existing focused regressions.
- Actual cloud-browser harness at `/qa/browser.html`: **14 passing checks, zero failing**. Includes the previous GLB/paint/morph/animation round trips, plus no-op tile handling and production recovery functions on two real IndexedDB connections. These are browser data/Canvas checks, not 3D rendering acceptance.
- The new recovery test initially failed before reaching IndexedDB because this insecure preview origin does not expose `crypto.randomUUID`. Replaced its test-only temporary database name generator; did not weaken assertions. The rerun passed.
- Syntax checks passed for the changed application/core modules, both new modules, and the browser harness. `git diff --check` passed before saving.
- Retried the actual mirror page. It still reports `Error creating WebGL context` and disables unavailable controls. No successful viewport is claimed.

## Remaining verification gaps

The complete rendered avatar-paint/save/reopen workflow, actual native save picker, active-model graphics loss, touch/pen cancellation, and authenticated Counter/Foundry integration still need acceptance. Account-scoped recovery, mixed-version writers, UV-island isolation, finer paint resolution, full glTF extension fidelity, and physical-device performance remain open. This round does not complete the broader three-solution program or Primp itself.

## Architectural choices for these repairs

For file saving, compared unconditional download, confirmed file-handle writing, and a user self-confirmation control. Chosen: confirmed file writing where supported, honest download fallback elsewhere; no extra self-certification UI. Writer tests use doubles and do not establish OS/browser compatibility.

For recovery, compared unconditional replacement, transactional revision checking, and separate recovery records for every tab. Chosen: transactional checking, preserving the existing single recovery slot and old files. Separate per-document/per-account histories remain future work. The transactional choice has real IndexedDB execution evidence.

For no-op history, compared retaining all touched tiles, storing stroke replays, and discarding unchanged exact-pixel tiles. Chosen: discard unchanged tiles while keeping the already-tested exact-pixel transaction model.

No changes to original avatars, geometry, cream behavior, identity metadata, or source design conversations. No deployment or merge to main.
