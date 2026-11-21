# Merge report - integration/converge-2026-11-20

Written 2026-11-20 against `whatsupjosie/beyond-october`, read at forty-six
branch heads. `main` was not touched. Nothing was deleted.

Companion files: `BRANCH_PROVENANCE.md` (every branch name, tip commit, date)
and `LARGE_FILE_INVENTORY_2026-11-20.md` (what the new repo would carry).

## What this branch is

Base: `main` (`c82069b4`, 2026-11-04), fast-forwarded to
`claude/2i-coalesce-saves-2026-11-18`, then eleven explicit merges.

Forty of the forty-six branches are reachable from this branch's tip. Six are
not; they represent four distinct commits, all listed under "Needs your
decision" below.

## How the branches were judged

Not by name. Ancestry plus file-level content comparison. Two name-based
readings turned out to be wrong and are worth recording:

- `audit/standard-first-2026-11-19` sounds like it makes the standard page the
  default 2i look. It does not. It is six documentation commits auditing which
  established open engineering approaches to adopt. No code.
- `codex/2i-typewriter-visual-2026-11-17` is titled "show typewriter scene in
  every view and resolve artwork offline", which sounds additive. It replaces
  the interactive typewriter with a static image. See below.

Of the forty-six refs, fifteen were maximal heads and thirty-one were already
fully contained in one of them. Five pairs of names pointed at one commit.

## Three approaches considered before committing to one

1. **Merge all fifteen maximal heads onto main in increasing-delta order.**
   Rejected as the plan of record: it puts `codex/main-debug-20261119`, the one
   genuinely parallel line, in the middle, where its conflicts mix with the 2i
   conflicts and neither can be judged on its own.
2. **Take the most inclusive head as the tree and cherry-pick the rest.**
   Rejected: it discards merge provenance, which is the one thing the new
   repository cannot reconstruct, and cherry-picking twenty-five interdependent
   commits out of `main-debug` is worse than one merge of them.
3. **Merge the family that shares the 250-commit base first, closely-related
   branches adjacent, and the parallel line last and alone.** Chosen. Each
   conflict then sits in a single domain, and the hard case is isolated in one
   reviewable step. This also paid off concretely: merging
   `codex/2i-claude-functional-integration` before `preview/2i-live` moved the
   merge base so that `preview`'s two expected conflicts disappeared.

## One row per branch

| Branch | Tip | Disposition | Reason |
|--------|-----|-------------|--------|
| `claude/2i-coalesce-saves-2026-11-18` | `2a5abdb52` | carry forward - merged (base) | Most inclusive head, 259 commits. Matches your stated interactive-typewriter design. |
| `audit/standard-first-2026-11-19` | `6cccfd7a5` | carry forward - merged | Clean. Documentation only. |
| `fix/2i-save-freshness-2026-11-19` | `27b074109` | carry forward - merged | Clean. 2i save-freshness fix plus tests. |
| `claude/pubpartner-work-notes-2026-11-19` | `4dc10a426` | carry forward - merged | Clean. One commit. |
| `gpt/speech-playback-lifecycle` | `6707e7cde` | carry forward - merged | Clean. |
| `gpt/recording-endurance-2026-11-13` | `0857cf5f8` | carry forward - merged | Clean. |
| `gpt/clacker-timecode-verification` | `e8d779830` | carry forward - merged | Clean. Contains guest-recording-triage and participant-clock. |
| `codex/2i-beta-test-gates-2026-11-17` | `f52125a82` | carry forward - merged | Clean. Brings seven hosted-save tests and a CI file (see CI note). |
| `codex/github-browser-tests-2026-11-17` | `5965e9780` | carry forward - merged | Clean. One commit, a CI file (see CI note). |
| `codex/2i-claude-functional-integration-2026-11-17` | `e0cc000c2` | carry forward - merged | Four conflicts, resolved to the Nov-18 line. Details below. |
| `preview/2i-live-2026-11-17` | `95cfde06f` | carry forward - merged | Clean after ordering. Brings the single-file offline 2i preview. |
| 29 further branches | - | carry forward - already contained | Ancestors of this tip. `BRANCH_PROVENANCE.md` lists each. |
| `console-touch-typewriter-keys` | `3ee394a7c` | carry forward - already in, by exact port | Proven by blob: 11 of 16 changed files byte-identical here, other five strict supersets, zero dropped lines. Dropped as a merge on your instruction. |
| `backup/claude-console-touch-typewriter-2026-11-17` | `3ee394a7c` | carry forward - already in | Same commit as the above. |
| `2i-beta-polish` | `df737caae` | **needs your decision** | Three code commits on no other branch. All three conflict. See below. |
| `backup/claude-2i-beta-polish-2026-11-17` | `df737caae` | **needs your decision** | Same commit as the above. |
| `codex/2i-typewriter-visual-2026-11-17` | `69e155031` | **needs your decision** | Replaces the interactive typewriter with a static image. See below. |
| `codex/main-debug-20261119` | `d3b9db81f` | **needs your decision** | Twenty-five commits; two files are an architecture fork. See below. |

Nothing is marked "leave behind". I did not decide to leave out any of your
work; the four undecided commits are recorded with their hashes and remain on
their branches in the old repository.

## Conflicts, both sides, and how each was resolved

### `codex/2i-claude-functional-integration-2026-11-17` - four conflicts

`main.py` was byte-identical to ours, so commit `32d1424`'s Fable server restore
was already present and nothing server-side was lost.

| File | Ours (Nov 18) | Theirs (Nov 17) | Resolution |
|------|---------------|-----------------|------------|
| `2i/2i-assets/reach.js` | Native-undo guard at lines 808-810 using optional chaining | The same guard without optional chaining, plus different comments | Ours. Functionally equivalent. |
| `static/typewriter_console_demo.js` | Nov-18 embed protocol: `embedded=2i`, `pubcast:key` | Nov-17 protocol: `embed=2i`, `pubcast:2i-key` / `pubcast:2i-paper` | Ours. The two protocols cannot coexist, and `studio-desk.js` on this branch speaks the Nov-18 one. |
| `2i/2i-assets/studio-desk.js` | Interactive typewriter in a same-origin iframe, Expand keys, Foresight file-tray view selector | Static image plus a decorative paper preview; no view selector | Ours. It is the design you stated: real touch and mouse key hotspots. |
| `2i/writers-room-v22.html` | Nov-18 reconciliation and bridge | Nov-17 equivalent | Ours, same reason. |

Carried in from that branch regardless: `2i/2i-assets/typewriter-key-bridge.js`
and four test files.

### `codex/main-debug-20261119` - not merged, work preserved

Four of its six conflicted files resolve as genuine unions, and each union was
verified necessary rather than assumed:

- `main.py`: their capture wiring plus our studio25d recording router.
  `application.state.session_capture` is required - `shutdown()` calls it at
  lines 917 and 1930, so taking ours alone would crash on shutdown.
- `modules/production_routes.py`: union of the import sets.
  `confirmed_stop_session_id` is used at line 404, so taking ours alone would
  have been a `NameError` at runtime.
- `modules/recording.py`: all six hunks unioned - `ingest` and `capture_errors`
  side by side, both validation checks kept, their `local_metadata` signature
  over our ingest-validation body. `datetime`, `replace` and `local_metadata`
  were each confirmed in use first.
- `2i/2i-assets/file-workspace.js`: ours, identical behaviour, keeps the 350 ms
  debounce rationale.

The two that stopped me:

- `static/production25d_storage.js`
- `static/production25d_app.js`

These hold two incompatible local-recording architectures. Ours: IndexedDB
version 3, lease-based `captures` and `captureChunks`, a `Capture` writer,
`captureOwner`, `PubCast25DSourceRecordings`, a cancellable start token.
Theirs: IndexedDB version 2, `chunks` and `journals`, a `journal` object with
sequence, bytes, committed and tail, incomplete headers, `panicActive`. They use
different state fields (`recordingStarting` against `startingRecording`,
`captureWriter` against `journal`) and different `save()` signatures
(`save(session,blob,capture)` against `save(session,blob,chunked)`).

Choosing between them is an architecture decision, not a conflict resolution,
and a wrong guess breaks studio recording in a way reading the code would not
reveal. So I stopped. The completed union work is on
`integration/main-debug-union-trial-2026-11-20` (`eacde8753`), which is
deliberately not part of this branch.

## Needs your decision

**1. `codex/main-debug-20261119`** - which local-recording architecture survives,
ours or theirs. Everything else in those twenty-five commits (camera filename
reservation, forbidding FFmpeg overwrites, timeline transport repair, PANIC
encoder handling, per-source failure persistence) merges cleanly and is waiting
on that one answer.

**2. `2i-beta-polish`'s three commits** - you asked me to merge them on top of the
codex result. I did not, because two of the three now collide with your own newer
design, and I would be changing your design to land them:

- `3fb483f` (Ctrl+Z in a text box) is **already in**. `2i/2i-assets/reach.js`
  lines 808-810 carry your exact guard. Nothing to merge.
- `26fca15` (Reach desk layer, phone and tablet) builds the three-column desk.
  Your own Nov-16 commit `cbc529583` deliberately replaced that with the
  single-page notebook: centred page, sidebar put away, small arrow drawer tabs.
  Applying `26fca15` on top would fight the newer look.
- `6c45e37` (locks hold in Write mode, Replace All counts right) - the behaviour
  is present on this branch; only the result wording differs ("left unchanged"
  here, "left as they are" there).

All three conflict in `2i/writers-room-v22.html` and the Reach CSS and JS. Say
which look wins and I will land what is actually missing.

**3. `codex/2i-typewriter-visual-2026-11-17`** - it swaps the interactive typewriter
for a static image and drops the file-tray view selector, which contradicts two
things you have stated: that the typewriter keys should be real touch and mouse
hotspots, and that the mode menu should work in any 2i window. But it carries the
only `file:` protocol artwork fix in the repo. `preview/2i-live`'s
`2i/preview-standalone.html` looks like a better answer to the same offline
problem and is already merged. My recommendation is not to merge this branch and
to keep the offline work from `preview` instead - your call.

## A name-based reading that was wrong, and what the tests actually say

I first read the `file://` test failures as a regression: on `main` the 2i lock
controls are visible when the page is opened straight from disk, and on the
Nov-19 head they are not. A bisect over 259 commits named `cbc529583` as the
first "bad" commit - which is your single-page notebook design.

It is not a regression. `#lockAllBtn` sits inside `#sidebar`, which is
`display: none` in the single-page look, and `#twoiDrawerTabTools` and
`#twoiDrawerTabPartner` are both visible. Clicking the Tools drawer tab sets the
sidebar to `display: flex` and every lock control becomes visible and clickable.
Verified in Chromium. 2i is not broken offline; your design is working as you
specified, and the older tests click sidebar buttons without opening the drawer
first.

## Test results

Run locally in this sandbox. No GitHub Actions and no CI were used.

### Node

| Tree | Tests | Passed | Failed | Skipped |
|------|-------|--------|--------|---------|
| Base head `claude/2i-coalesce-saves-2026-11-18`, unmerged | 249 | 235 | 14 | 0 |
| This branch | 278 | 261 | 17 | 0 |

Fourteen of the seventeen failures are inherited - they fail identically on the
unmerged base head, so the convergence did not cause them. Zero skipped, so no
skipped test is being counted as a pass.

The convergence added twenty-nine tests and, before the harness fix, ten
failures. Seven of those ten were one missing sandbox variable:
`tests/test_2i_hosted_save_races_node.js` slices `saveDocument` out of `reach.js`
and runs it in a `vm` context, and the Nov-18 save routing added
`if (reachFileMode || initializing) return false;` to that function. The fixture
defined `initializing` but not `reachFileMode`, so all seven threw
`ReferenceError` before any assertion ran. Measured: 7 passed on
`codex/2i-beta-test-gates-2026-11-17` before the merge, 0 passed here, 7 passed
after adding `reachFileMode: false` to the fixture. Test fixture only; no product
code touched.

The three that remain are tests written against the Nov-17 interface, and each
was checked rather than assumed:

- *Reach capture guard stops Ctrl+Z in Find and Rename* - asserts a literal
  comment string, `// Preserve native undo in EVERY text entry`, which the Nov-18
  file words differently.
- *manuscript shortcut owner preserves every native text-field undo* - calls
  `manuscriptShortcut` with a `nativeTextField` context key that the Nov-18
  function does not read. The protection is there, one level out:
  `2i/writers-room-v22.html` line 2881 computes `otherTextField` for any
  `input, textarea, select, [contenteditable]`, and line 2867 returns null. So
  Ctrl+Z in a Find or Rename box does not touch the manuscript.
- *standalone Replace All counts once* - expects the message "left as they are";
  this branch says "left unchanged". Counting is the same.

None of the three is a defect. Updating or retiring them is a change to test
assertions, which I left alone.

### Python

Full suite, `python -m pytest -q -p no:randomly`, run on commit `daa9b779` of
this branch. Later commits on the branch are two Markdown files and one Node
test fixture, none of which pytest collects (`pytest.ini` sets
`python_files = test_*.py`), so these counts hold for the branch tip.

| | Count |
|---|---|
| Collected | 2814 |
| Passed | 2805 |
| Failed | 9 |
| Errors | 17 |
| Skipped | 9 |
| xfailed | 1 |
| Subtests passed | 16 |
| Duration | 36 min 29 s |

Skipped and xfailed are reported separately and are not counted as passes.

Attribution. Every failing and erroring test was re-run against the unmerged
base head `claude/2i-coalesce-saves-2026-11-18`:

| Group | Count | Inherited or new | Evidence |
|-------|-------|------------------|----------|
| `tests/primp_chromium/test_mirror.py` errors | 14 | inherited | Same fixture setup error on the base head. |
| `test_admitted_guest_recording_browser`, `test_clacker_recording_browser`, `test_participant_audio_browser` | 3 | inherited | Fail identically on the base head. |
| `test_alex_routes_bridge::test_alex_routes_message_and_recent_memory` | 1 | inherited | Passes alone (9 passed). Fails in a group run, `count` 0 rather than 1, from cross-test state. Reproduced on the base head once the collection blocker was removed: 1 failed / 251 passed there, identical to here. |
| `tests/test_2i_claude_functionality_browser.py` failures | 5 | new test file, added by the `cx-func` merge | Playwright timeout clicking `#lockAllBtn`; the button is inside the put-away sidebar in the single-page look. |
| `tests/test_2i_typewriter_event_browser.py` errors | 3 | new test file, added by the `cx-func` merge | Exercises the Nov-17 `pubcast:2i-key` protocol and `typewriter-key-bridge.js`, which this branch does not wire. |

**The convergence introduced no regressions.** All eight new red tests arrive
with the two test files that `codex/2i-claude-functional-integration-2026-11-17`
added, and both exercise the superseded Nov-17 interface. The other eighteen
fail the same way on the unmerged base head.

### A defect found and fixed: the suite could not run at all

`tests/test_2i_typewriter_embedded_browser.py` line 12 read
`from test_2i_hosted_layout import reach, _open`. `tests/` is a package
(`tests/__init__.py` exists), so pytest imports its modules as `tests.test_*`
and a bare sibling import can never resolve. A collection error aborts the whole
pytest run, so that one line made the entire Python suite uncollectable on every
head that carried it: `claude/2i-coalesce-saves-2026-11-18`,
`audit/standard-first-2026-11-19`, `fix/2i-save-freshness-2026-11-19`,
`codex/2i-integration-readiness-2026-11-18` and
`codex/2i-typewriter-manuscript-bridge-2026-11-18`.

Collection before: 2787 tests and one fatal error. After: 2814 tests, no errors.
Only the import line changed. The practical consequence is that no full Python
run had been possible on any of the newest heads, which is worth knowing when
reading their handoffs.

## Fresh-clone check

Cloned `integration/converge-2026-11-20` from GitHub into an empty directory and
verified it stands on its own:

- clone succeeds, 2520 tracked files
- `pip install -r requirements.txt -r requirements-dev.txt` from the clone's own
  files is sufficient
- `npm ci` succeeds from the clone's own `package-lock.json`
- `pytest --collect-only` reports **2838 tests collected, no errors**
- the Node suite reproduces the same numbers as the working copy:
  **278 tests, 261 passed, 17 failed, 0 skipped**

Two test dependencies are imported but not declared, so their tests skip with a
reason rather than running: `zstandard` and `msgpack`, both used by
`tests/test_blackbox_*_experiment.py`. Neither appears in any `requirements*.txt`.
Adding them would turn skips into real runs.

### Paths outside the repository

No tracked symlinks. No `../../..` escapes in runtime code. Nine hardcoded
external paths, in eight files, none of them in the application runtime
(`main.py`, `modules/`, `static/`, `2i/` are all clean):

| File | What is hardcoded |
|------|-------------------|
| `launcher/start_pubcast.ps1` | `$ProjectRoot` and a Python 3.11 path under `C:\Users\hardc\...` |
| `tools/pubcast_agent.py` | `WORKSPACE` pointed at a Desktop folder |
| `codex_add_pubblocks.py` | a one-off path under `C:\Users\hardc\Downloads` |
| `tools/Build-PubCastCleanupReport.ps1`, `tools/Finalize-ZipDuplicateGroups.ps1`, `tools/Inventory-ZipsAndDuplicates.ps1`, `tools/Prove-ZipDuplicates.ps1`, `tools/Stream-ProveZipDuplicates.ps1`, `tools/Stream-ZipInventory.ps1` | default parameters under `C:\Users\hardc\OneDrive\Documents\Playground\codex_reports` |

Not dependencies, checked and cleared: `tools/sandbox/run_sandbox.py` (Windows
Program Files globs for optional Blender and Firefox discovery),
`tests/test_pubcast_smoke.py` and `tests/test_recording_portable_bundle.py`
(deliberate `C:\outside\...` fixtures proving absolute paths are rejected),
`modules/ai_runtime.py` (a comment), and
`docs/iteration_wallet/ceremony_surface_reference.html` (placeholder text in an
input field).

## About the CI files, and why they are safe to carry

Two merged branches add GitHub Actions workflows, and `preview/2i-live` adds a
`.devcontainer`. None of them runs when this branch is pushed:

- `.github/workflows/2i-beta-acceptance.yml` triggers on push only to
  `codex/2i-beta-test-gates-2026-11-17`, plus manual dispatch.
- `.github/workflows/2i-chromium-smoke.yml` triggers on push only to
  `codex/github-browser-tests-2026-11-17`, plus manual dispatch.
- `.devcontainer/` only acts if someone opens a Codespace.

Because both workflows are pinned by branch name, pushing
`integration/converge-2026-11-20` fires neither, so your inbox stays quiet and
nothing is billed. If you ever rename a branch to one of those two names, they
would fire. Every test count in this report was produced locally in a sandbox;
no CI was used.

## Still open

- The four decisions above.
- The three `cx-func` Nov-17 interface tests: update them to the Nov-18
  interface, or retire them. They assert on comment text, a context key and a
  message string, not on behaviour.
- `tests/test_2i_claude_functionality_browser.py` and
  `test_2i_polish_browser.py` both click sidebar buttons without opening the
  Tools drawer first. They need a drawer click to be valid against the
  single-page look.
- `zstandard` and `msgpack` are undeclared test dependencies.
- The fourteen `primp_chromium` fixture errors and the three recording and audio
  browser failures are inherited and untouched by this work.
