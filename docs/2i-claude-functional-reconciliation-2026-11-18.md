# 2i functional reconciliation and preservation ledger

Date: 2026-11-18. Branch: `codex/2i-claude-functional-reconcile-2026-11-18`.

## Immutable preservation checkpoints

Created exact-head GitHub backup branches before editing:
- `backup/claude-console-touch-typewriter-2026-11-17` = `3ee394a7ca66edd5e152eb0eca4de1709333bd7c`
- `backup/claude-2i-beta-polish-2026-11-17` = `df737caaeff206e4128932532663776af74ec0e8`
- `backup/fable-2i-beta-polish-2026-11-17` = `cbc529583202628075c4c319482ae011da2a123f`

Original development branches and `main` were not altered.

## Functional integration completed on this branch

Based on the previously verified console-staging commit `ec1b5c5`, which carries the exact 15 Claude touch-console/typewriter source and art blobs alongside Fable's editor, without replacing the editor.

The served 2i editor, `2i/writers-room-v22.html`, and Reach adapter, `2i/2i-assets/reach.js`, now include the following reconciled behavior:

1. Native Ctrl/Cmd+Z and redo stay within **any ordinary focused text input**, not just the manuscript and chat textareas. Inline collab-line editing keeps its existing manuscript undo path; existing shortcut guards stay in place.
2. **Write-mode Unlock** uses the cursor's paragraph rather than demanding a Collab-selected line. Already-unlocked lines produce a notice, not an unnecessary undo entry.
3. **Cancel New Chapter** does not add an empty undo step.
4. **Fallback Replace All** (without NarrativeCore) counts each replacement once, leaves locked lines intact, avoids no-op dirty mutations, and keeps the textarea in sync with `committed`. Fable's NarrativeCore-aware replacement path is unchanged.
5. **Undo/redo of lock/chapter metadata in Write mode** retains all words typed after the original action, while a genuine text-edit snapshot still restores text. Metadata undo/redo carries its classification in both directions. The newer Fable full narrative-history snapshots are retained for regular text edits.
6. System errors, recovery information and lock warnings are attributed to **Writer's Room notices**, not AI partner speech.

## Verified evidence and limits

- A focused simulation reproduced **actual lost writing** on the prior Fable undo code: the text after a locked snapshot disappeared on Undo.
- After repair, the **three** new `tests/test_2i_metadata_undo_node.js` checks passed (lock undo/redo, chapter undo/redo, actual text undo); the **seven** new `tests/test_2i_claude_functional_reconcile_node.js` checks passed (unlock, no-op, chapter cancel, locked Replace All both paths, native text-field undo). All ran against GitHub-retrieved code using a temporary V8 compatibility harness rather than the full Node native runner.
- Edited undo, lock and replacement JavaScript sections parsed successfully. This is not full HTML/browser validation.
- Earlier independent source-focused results on Fable: 67 existing Node checks and 7 hosted-save checks passed in a compatibility harness, not a real end-to-end server run.
- Claude's handoffs separately claim 2283 passing Python tests on the editor polish branch and 2302 on the console/typewriter branch. **Those runs have not been independently reproduced on this combined branch.**
- GitHub Actions is still failing before runner assignment; do not claim that these tests ran in GitHub CI.

## Functionality preserved but not yet integrated

- Claude's `2i-beta-polish` **phone layout and CSS**, visual lock indicators, ResizeObserver layout polishing, and `tests/test_2i_polish_browser.py` are preserved in the backup branch, but not blindly copied over Fable's independent notebook, page sizing, wrapped paragraph numbering and manuscript recovery.
- The `/typewriter-console` bench page and original art/hotspots/audio are present, but its `pubcast:key` event is **not connected to the real 2i manuscript**. No live typed-paper integration claim.
- Real Ctrl+Z/lock/edit behavior, Save Now, manuscript close/reopen, line protection, mobile use and the rendered typewriter require native Playwright/Chromium acceptance against the integrated host.
- No 30-minute recording, audio playback, Windows packaging, or iPad/Safari acceptance in this reconciliation.

## Release gates

Do not merge into main or declare beta until the actual Node, Python, Chromium and host-persistence suites have run on the consolidated tree, failing cases are fixed, and an independent review verifies the new text-loss protections. Preserve all three backups and the original branches throughout.

The owner prioritizes functional integration and preservation of Claude's progress ahead of any large visual redesign. Work on the look can follow after functional parity.
