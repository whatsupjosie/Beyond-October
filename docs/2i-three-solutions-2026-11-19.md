# Three solutions, then a better one: the four major open problems

**Date:** 2026-11-19. **Author:** Claude, under Josie's rule "weigh at least three real approaches before an architectural commitment".
**Status:** analysis and recommendations only. Nothing here is built yet except where it says "done". Facts are from the code on `claude/2i-coalesce-saves-2026-11-18` (`5fc2dae`); unproven points are marked.

---

## 1. Alex: the canonical vessel and her live memory share one path

**Facts.**
- The app opens `DATA_DIR/pubpartner/vessels/alex.pubpartner` with `PubPartnerVesselRuntime.open_or_create` (`main.py`, `modules/pubpartner_vessel/runtime.py`): it opens the file if present, otherwise **creates a new, blank vessel**.
- `run_reach.py`, the main launcher, uses `reach_userdata/` and seeds only the bot configs. **So under the normal launcher Alex runs from a blank vessel, not the canonical one.** (Verified by reading the code; not yet observed in a running app.)
- `start_reach.py`, or running `main.py` directly, uses the repository's `data/`, so the **canonical file itself** is opened and written as live memory. That is how the preflight changed it on 2026-11-18.
- Done: a commit guard and a committed-blob test keep a changed vessel out of Git (`docs/ALEX_VESSEL_PROTECTION.md`).

| Option | What it does | For | Against |
| --- | --- | --- | --- |
| A. Guard Git only (done) | Refuse commits that change the vessel | No runtime change, zero data risk | Canonical file is still mutated in place by some launchers; the main launcher still runs a blank Alex |
| B. Open the canonical file read-only | Runtime cannot write it | Canonical can never change | Alex can no longer remember anything; breaks her |
| C. Separate template and live copy | Ship the canonical file as a read-only template; each data folder holds its own live vessel, copied from the template when absent | Canonical never opened in place; every launcher gets the real Alex | Existing live memory (in a checkout's `data/`, or a blank vessel already in `reach_userdata/`) needs migrating |

**Best single option:** C.

**Better answer: C, made safe to adopt.**
1. **Template, never opened in place.** On start, if the live vessel is absent, copy the template, but only after checking the template's Git blob is `96fa66a7…`; refuse and say so if it is not. If a live vessel exists, use it and never touch the template.
2. **Refuse in-place use.** If `DATA_DIR` resolves to the repository's own tracked `data/`, open a live copy instead of the tracked file (or refuse to start with a clear message). This closes the hole for every launcher at once, including ones nobody remembers.
3. **One-time migration tool, dry run first,** using the existing checkpoint (`modules/data_checkpoint.py`) and Alex backup (`modules/alex_memory_backup.py`) for a verified backup before anything moves. It reports which of three situations each machine is in:
   - grown live memory inside a checkout's `data/` (blob is not canonical): back it up, move it to the live data folder, then restore the tracked file from Git;
   - a blank vessel already created in `reach_userdata/`: it may hold memories made since, so **keep it beside the seeded canonical copy** and report it; nothing is discarded or merged automatically;
   - fresh install: seed from the template.
4. Keep the guard and the committed-blob test.

**Tests that must fail first:** start each launcher against a fresh folder and assert the live vessel's identity is canonical Alex (fails today for `run_reach.py`); start against the repository's `data/` and assert the tracked file is unchanged afterwards (fails today); migration dry run on the three situations, then a real run with byte-for-byte verification of the backup.

**Josie's answer (2026-11-19):** "Alex doesn't really exist today. Just some files with traces of her. And we piece together what we can."

What that changes:
- There is no grown live memory to migrate, so the migration risk in step 3 is gone. Step 3 shrinks to: before anything changes, take a verified, read-only backup of every Alex trace that exists (the canonical vessel, `data/alex/`, any vessel already created under `reach_userdata/`), and never delete one.
- The priority becomes **preserving every trace**, not moving memory. Every fragment is part of what Alex will be assembled from, so the rules are: never overwrite, never delete, never merge automatically, and keep any copy whose origin is unclear beside the canonical one, labelled, for Josie to judge.
- With no migration needed, the template approach (steps 1, 2 and 4) carries little risk and can be built as soon as Josie wants it.

---

## 2. Rich DOCX: the last edits at close, and opening a DOCX straight into formatting

**Facts.** Rich bytes come only from the engine's asynchronous `saveBytes()`. Protection today: 1.5 s autosave, a save when the tab is hidden, and the browser's leave warning (all tested). Residual loss: the writer chooses "Leave" on the warning, or the tab is killed without being hidden first. A `.docx` opens as a text copy; formatted editing needs a separate rich `.2i` step. Whether the engine exposes a synchronous, serialisable document state is **unproven**.

| Option | What it does | For | Against |
| --- | --- | --- | --- |
| A. Keep warn + hide-save + autosave | Status quo | Tested, no new risk | Last ~1.5 s lost if the writer chooses Leave |
| B. Save much more often | e.g. 300 ms | Smaller window | Whole-DOCX serialisation on every pause: the write-amplification problem again; still not exit-safe |
| C. Synchronous engine-state journal | Snapshot the engine's model at exit and replay it | Could be exact | Depends on an engine API not shown to exist; replay fidelity risk; ties us to engine internals |

**Best single option:** A.

**Better answer: A, plus an honest rescue copy, plus direct open.**
1. **Plain-text rescue copy at exit.** On page hide or unload with unsaved rich edits, write the editor's visible text synchronously to the exit journal. It is **never applied into the DOCX** (formatting would be lost); on reopen the writer is told: "Your last formatted edits may not have been saved. A plain-text copy of the document as it was at close is kept. Download it to compare." No corruption risk, uses the tested journal path.
2. **Idle-or-interval rich autosave.** Save when typing pauses (1.5 s) and at most every 10 s during continuous typing, so a long uninterrupted burst cannot stay unsaved. Measure `saveBytes()` time on a large document before choosing the interval.
3. **Open DOCX straight into the formatted editor.** Build the rich working copy from the DOCX on open with the existing verified path (`packVerifiedRich`), original kept separately; fall back to today's text copy, with a clear message, only if the engine cannot open the file.

**Tests that must fail first:** reload after choosing Leave, then assert the rescue copy exists and is offered (fails today); continuous typing for 20 s with saves counted (shows today's single trailing save); open a `.docx` and assert the formatted editor mounts with the original unchanged (fails today).

---

## 3. "Saved" when a save failed or stalled, and closing during it

**Facts.** File mode says saved only after the IndexedDB transaction completes; Reach only after the host returns a revision. Both are real confirmations of a write. Not yet tested: a write that never settles. `prepareClose` awaits the save with no time limit, so a stalled write most likely makes close hang rather than lie (hypothesis to prove). Also unproven: whether "Saved" can stay on screen while newer edits are unsaved.

| Option | What it does | For | Against |
| --- | --- | --- | --- |
| A. Time limits on saves | Treat a save that takes too long as failed | No hang | A slow save that later succeeds was reported failed; needs reconciliation |
| B. Read back after every save | Read the stored record and compare before saying Saved | Strongest truth | One extra read per save; does not by itself solve a stall |
| C. One save-state machine | idle, dirty, saving, saved, failed, stalled, owned by one module, UI drawn from it | Clean, consistent | Refactor across `reach.js`, `file-workspace.js`, `foresight_files.js`: large regression risk |

**Best single option:** B.

**Better answer: a content fingerprint plus a "still saving" state, without the refactor.**
1. **Fingerprint what was written.** Hash the snapshot when a save starts; when it confirms, show "Saved" only if the text on screen still has that hash; otherwise "Saving latest changes…". This proves Saved is never shown over newer, unsaved text, at the cost of one hash, not one read.
2. **Stalled is its own state, never failure and never success.** If a save has not settled after a set time, say "Still saving. Your text is safe on screen; don't close yet," keep `canClose` false, and do not abort the write. If it later succeeds, the fingerprint check decides what to show.
3. **One small shared helper** used by both the file and Reach paths, instead of a new state machine.

**Tests that must fail first (fault injection at the real boundaries):** hold a file-mode write open and a Reach `PUT` open, then type, press Save, request close: assert no "Saved", `canClose` false, latest text kept; reject with quota, 409 and 503; let a held write succeed after more typing and assert the status does not claim the newer text is saved.

---

## 4. Tests that slice source code break when the code moves

**Facts.** Five Node tests fail on PR #13 because their copied slices of `reach.js` and the page no longer match the code. One of my own changes broke another, and I missed it because my runs did not include the Node tests.

| Option | What it does | For | Against |
| --- | --- | --- | --- |
| A. Fix each harness | Add the missing globals and markers | Quick | Breaks again on the next change |
| B. Replace with real-browser tests | Test the same behaviour in Chromium | Robust, tests what users run | Slower; takes time to write |
| C. Make the code importable | Split functions into modules tests can import | Clean | Restructures Josie's code; needs her explicit approval |

**Best single option:** B.

**Better answer: B for what protects manuscripts, A as a stopgap, and make silent rot impossible.**
1. Real-browser tests for the behaviours that guard writing (save routing, close, typewriter relay); fix the remaining slicers (A) only until those exist.
2. Every slicing harness fails with "source moved: update this harness" when its marker is missing, as the write-amplification probe already does, instead of a misleading ReferenceError.
3. One Python test runs every `tests/*.js` file, so a normal `pytest` run can never skip the Node tests again.

**Ownership:** the five harnesses belong to the integration line (GPT); item 3 is a small change Claude can make now.

---

## Recommended order

1. Section 3 (false Saved, close during a stall): biggest risk to trust, no data migration, fully testable here.
2. Section 4, item 3 (Node tests inside pytest): small, removes a blind spot that already hid a defect.
3. Section 2 (rescue copy, interval autosave, direct DOCX open).
4. Section 1 (Alex template and migration): highest stakes, so it starts only after Josie says where her real Alex lives, and runs as a dry run first.
