# 2i: plan to a safe public beta

**Date:** 2026-11-18. **Owner of this plan:** Claude, for Josie and GPT to review.
**Starting point:** `claude/2i-coalesce-saves-2026-11-18` (on top of PR #13, `7e70e05`). Evidence so far: `docs/2i-adversarial-save-findings-2026-11-18.md`.

## What "safe enough for public beta" means here

A count of passing tests is not the gate. 2i is beta-ready when every item below has **executed evidence on the real served app**, with stored data read back by a different mechanism from the code under test, and each test shown to fail when the thing it protects is removed.

1. **No silent manuscript loss.** Type, then reload, close, hide, kill, lose the network, or switch documents at the worst moment: the last edit is stored, or a recovery copy exists and the writer is told so.
2. **No false "Saved".** A save that failed, stalled or was refused never shows as saved and never lets a tray close.
3. **No wrong-document writes.** A late completion, a second tab, or a forged message never writes to or reports on the wrong document.
4. **Protected text holds.** Locked passages and lock membership survive every input channel; legal edits still work.
5. **It starts and works where writers are.** Cold start on the full host, desktop and 390 px phone, all three presentations, offline recovery, Windows with PowerShell 5.

## Status against those gates today

| Gate | Status | Evidence |
| --- | --- | --- |
| 1, file mode, reload and hide | **Fixed on this branch** (exit journal) | 5 browser tests, red on PR #13 and on `f39ca7a`, green now; mutation-checked |
| 1, ordinary Reach manuscript, reload with the host unreachable | **Holds** (existing `writeRecovery` to `localStorage`) | New test, 3 of 3; fails with `writeRecovery` disabled |
| 1, rich DOCX at exit | **Guarded, residual risk** | Leave warning and hide flush hold (tests); a writer who chooses Leave, or a tab killed unhidden, loses the last 1.5 s. Engine not committed. |
| 1, image and media at exit | **Open, low risk** | Media is view-only; image edits save immediately per action; not yet tested at exit |
| 1, Reach recovery when `localStorage` is full | **Fixed** | Writer is now told no copy exists and to export; leave warning holds; test red before, green after |
| 1, real tab close, phone background kill | **Open, needs real hardware** | Only reload and a simulated hide were run |
| 2, false "Saved" and close races | **Open** | Charter trap 2 not yet built |
| 3, document identity | **Open** | Charter trap 3 not yet built |
| 4, protected text | **Open** | Charter trap 4 not yet built |
| 5, cold start, phone, presentations, Windows | **Open** | Partial old evidence only; Windows never run |
| Write amplification | **Fixed on this branch** | 40 keystrokes: 41 writes before, 1 after |
| Formats | **30 formats tested end to end (6 text, 9 documents, 6 images, 9 audio/video); RTF, EPUB, ODS, ODP added; clear messages for the rest** | `tests/test_2i_format_matrix.py`, 32 real-producer fixtures; open DOCX directly in the formatted editor is not built |

## The work, in order

Each step follows the same rule: write a test that fails first, fix the smallest thing that makes it pass, prove it with a mutation, record the evidence, commit to the Claude branch.

### Step 1. Close the remaining loss paths (gate 1)

1. **Rich DOCX, image and media at exit.** Reproduce: edit, reload inside the save delay, reopen, compare with a raw read. For rich DOCX the bytes come from an async `saveBytes()`, so a synchronous exit copy may not be possible; if so, keep the reproduction, warn on leave instead, and document it rather than shipping a workaround.
2. **2i's own browser autosave** (`pubcast2i-autosave-v2-*`, 3 s). Check whether anything relies on it at exit. If it is only a secondary copy, document its limits; if something relies on it, fix it the same way.
3. **Recovery storage full.** Fill `localStorage` to its limit, type, reload. Required: the explicit "Browser recovery unavailable" message, a leave warning, and the server copy intact. Then check growth: per-writer dirty copies are kept on purpose; measure how fast they accumulate and whether old ones can fill the quota.
4. **Hide-time host save.** `reach.js` sends a plain `fetch` on hide. Do not add `keepalive` blindly: it caps bodies at 64 KB, smaller than many manuscripts. Measure, then decide. The local recovery copy stays the primary safeguard.

### Step 2. No false "Saved", no unsafe close (gate 2, charter trap 2)

Inject at the real boundaries: hold a file-mode IndexedDB write open, reject it with a quota error, return 409, 503 and a stalled response for the Reach `PUT`. During each, edit, press Save, and request prepare-close. Required: the status never says Saved, `canClose` is false, and the latest text is stored or kept as a recovery copy with a warning. Status text is checked against a raw read of storage, every time.

### Step 3. Protected text (gate 4, Mission 4)

Real browser, served v22. Lock two passages, then use: ordinary typing, the typewriter iframe, IME composition (CDP `Input.imeSetComposition`), emoji and combining-character deletion, multiline paste across a lock, Replace All, cursor-based unlocking, undo and redo. Oracle: the locked passages and the lock list, read from stored state, byte-identical before and after; legal edits elsewhere applied. Mutation: remove the lock guard and the tests must fail.

### Step 4. Document identity (gate 3, charter trap 3)

Open file A and manuscript B. Start A's save, switch, deliver A's completion late. Send `postMessage` with a wrong nonce and from a wrong origin. Two tabs on one document. Oracle: every storage write's document ID, recorded by the put hook and a host log; no write to the wrong ID, no accepted forged command, conflicts never silently overwrite.

### Step 5. Seeded chaos runner (Mission 2)

A runner that draws a sequence from a fixed action set (type, paste, lock, undo, save, switch document, switch presentation, hide, reload, drop network, close) using a recorded seed. A small independent model computes the expected text and locks; the real app runs the same sequence; stored data is compared with the model after each step. Any failing seed is saved as a permanent regression test. Start with the action set already covered by Steps 1 to 4, so the runner extends proven tests rather than replacing them.

### Step 6. Full host, phone and presentations (gate 5)

Run `run_reach.py` itself, not the test router: cold start, sign-in, a Reach manuscript and a Foresight file, Document, Notebook and Typewriter presentations, at 390 px touch and desktop, offline and back. Compare Claude's, Fable's and the combined branch on the same scripts (charter method C).

### Step 7. Josie's hardware (cannot be done in the cloud container)

- `CHECK_FORESIGHT_WINDOWS.ps1` on Windows with PowerShell 5.
- Real tab close and browser quit with unsaved text, in Chrome and Firefox.
- A phone: type, switch apps until the browser is killed, reopen.
Claude will write each as a short, copy-paste checklist with the exact expected result, so Josie spends minutes, not hours.

### Housekeeping that blocks a clean signal

- Done: the two long-standing failures were stale string checks; fixed so they resolve real references and still fail when a reference breaks. The 2i path suite is fully green (143 passed, 1 skipped).
- The test harness answers host requests through Playwright interception, which can complete requests a real closing page would lose. Tests that depend on a request finishing during unload must fail the host on purpose, as the Reach reload test now does.

## Who does what

- **Claude:** Steps 1 to 6 on `claude/2i-coalesce-saves-2026-11-18` (or a successor branch), each with failing-first tests, mutations and a findings entry. No edits to GPT's, Fable's or backup branches, or `main`.
- **GPT and Josie:** review each step's findings, reconcile into the integration branch, and challenge the tests.
- **Josie:** the decisions below and Step 7.

## Decisions (Josie, 2026-11-18)

1. File-mode exit journal: conditionally approved. The original record is preserved in every case; not released until its recovery and failure tests pass.
2. Messages explain what happened, what was preserved and the next action, and never claim an unverified save.
3. GPT's coalescing probe is a permanent regression test.
4. This branch stays separate from PR #13 until complete, independently reviewed and tested; then the existing integration process. No premature merge.
5. Claude makes routine implementation decisions, documents the reasoning, and escalates only consequential tradeoffs or irreversible actions.

## Open engineering decisions taken under that authority (reasoning in the findings document)

- Rich DOCX close protection stays "warn and flush on hide", not a new copy mechanism: a synchronous copy of rich bytes is not possible, and inventing an engine-specific snapshot would add risk without evidence it is needed.
- The DOCX engine build output is not committed (4.4 MB). Whether rich editing ships in the beta, and therefore whether the engine is bundled, is a product decision for Josie and is the one item escalated from this round.
- No `fetch` `keepalive` on the hide-time Reach save: its 64 KB body cap is below many manuscripts; the local recovery copy is the tested safeguard.
