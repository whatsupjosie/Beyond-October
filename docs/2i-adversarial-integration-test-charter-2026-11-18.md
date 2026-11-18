# 2i adversarial integration test charter: three methods, five traps
**Date:** November 18, 2026  
**Scope:** Beyond-October combined 2i editor, Claude typewriter, Fable manuscript safeguards, Foresight file trays, Reach account and storage.  
**Objective:** Find defects that normal unit tests and component-by-component wiring reviews miss. This is a **test design and one source-driven diagnostic**, not evidence the complete app has passed.

## Three complementary methods

**A. Deterministic state-machine chaos test.** Build a seeded event runner whose actions include type, select, lock, paste, undo, switch presentation, Save, switch file, hide tab, reopen, reconnect, and close. Each test records the exact seed, event ordering, file/document IDs and before/after serialized document state. Run the same seed through a model oracle and full application.

**B. Failure injection at real interfaces.** Put controllable delays and failures around `ForesightFiles.record()`, file handles, Reach PUT/GET, network and host postMessage. Hold a Save open while the user edits, closes, or switches files; reject persistence with a conflict, quota error, 503, decode error or unavailable account. A test passes only if the UI status and actual stored content agree. Do not rely on mocks as the final acceptance gate.

**C. Differential and mutation testing.** Compare identical edit scripts across the saved Claude, Fable, GPT and combined implementations. Test the combination in real Chromium at phone and laptop sizes. To establish that tests detect missing integration, deliberately disable one route/handler in disposable test worktrees; the relevant test **must fail**. No mutations touch originals or main.

## Five priority traps and their explicit falsification conditions

| Rank | Risk | Original adversarial experiment | Required result |
| --- | --- | --- | --- |
| 1 | Write storm / delayed autosave | Type 40 characters in a burst; count queued flushes and actual revision writes. Then type while a write is deliberately held. Repeat on Foresight and Reach. | No write per keystroke; a bounded number of persisted writes for a burst (initial target <=3); final revision and exact manuscript text include the last edit. |
| 2 | False Save success / close race | Start Save A, make edits B and C while A is pending, then request prepare-close. Inject quota error, 409, and a stalled write. | Never return canClose=true or show Saved for a stale/failed write. The latest content persists or a recoverable copy remains with an explicit warning. |
| 3 | Document identity crossover | Open file A and Reach manuscript B; start A save, switch view/file, receive late A completion and forged/wrong-nonce postMessage. In two tabs modify one document concurrently. | Zero writes to the wrong ID, no external frame commands accepted, conflicts never silently overwrite another writer, and no stale completion changes active status. |
| 4 | Protected text and undo across input channels | Protect two lines, exercise iframe typewriter, native keyboard, IME/composition, multiline paste, Replace All, deletion, undo/redo, mixed Unicode/emoji; also edit allowed lines. | Protected passage text and lock membership remain byte-identical, legal edits work, caret/selection/undo remain coherent, no phantom 'Saved' state. |
| 5 | Cold-start and mode parity | Open authenticated hosted app and Foresight file from cold Chromium, then reload, lose connectivity, use 390px touch viewport, switch Document/Notebook/Typewriter, close/reopen. Compare Claude/Fable/combined behavior. | Zero missing startup scripts/handlers, usable controls, all required features reachable from served v22, recovery accessible offline, exact content after reopen. |

## Immediate source-driven finding (not full-host evidence)

Our adapter `2i/2i-assets/file-workspace.js` calls `session.flush()` on every `markDirty()`. Shared `static/foresight_files.js` separately listens to editor input and debounces `dirty()`. In a source-executed V8 probe, 120 edits triggered 120 direct flush invocations. A separate source-executed persistence-queue probe with a stub `record()` found **40 record calls for 40 rapid edits**, all with the same final text snapshot and revision increments 0..39.

Executable diagnostic committed at `tools/2i_write_amplification_probe.cjs`. Run from a complete checkout:

```bash
node tools/2i_write_amplification_probe.cjs
```

This is an **explicit RED gate** and intentionally returns nonzero while >3 record calls arise from the 40-event burst. It is kept outside the default test collection, so it does not obscure unrelated test results. Source execution and mock `record` calls establish a high-confidence write-amplification lead, but not actual disk-write counts. Work should first reproduce it, then coalesce saves without weakening protection on close/pagehide, and rerun the probe plus real persistence/close tests.

## Completion criteria for Work

The full host must run natively in an isolated cloud environment with **real** Chromium, actual disposable server/auth/files, native Node and Python tests. All five trap categories must pass at least one full-path test, with fault-injected results and saved seed/reproduction instructions. New test failures are genuine blockers, not opportunities to relabel mocks as acceptance. Preserve the original branches and keep all changes in a dedicated, reviewed integration branch until accepted.
