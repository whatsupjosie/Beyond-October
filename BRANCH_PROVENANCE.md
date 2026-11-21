# Branch provenance for integration/converge-2026-11-20

Written 2026-11-20. This branch is intended to become the starting point of a new
repository, so every branch that existed in `whatsupjosie/beyond-october` at that
moment is recorded here by name, tip commit and date. The old branch names will
not exist in the new repo; this file is how they stay traceable.

Source repository: `whatsupjosie/beyond-october`
Branch heads read: 2026-11-20, forty-six refs under `refs/heads/`
`main` at that time: `c82069b47b04eac56cca1fb4f6a4eb16c44d32ae` (2026-11-04)
Base of this branch: `main`, fast-forwarded to `claude/2i-coalesce-saves-2026-11-18`

Nothing was deleted. Branches not merged are recorded below with their tip commit,
so the work remains reachable in the old repository.

## How the forty-six branches collapse

Judged by commit contents and ancestry, not by branch name. Of the forty-six refs,
fifteen were maximal heads (contained in no other branch); the remaining thirty-one
were already fully contained in one of those fifteen. Five pairs of names pointed at
the same commit.

## Explicit merges, in the order they were made

| # | Branch | Tip commit | Date | Conflicts |
|---|--------|-----------|------|-----------|
| 1 | `claude/2i-coalesce-saves-2026-11-18` | `2a5abdb5255d78c9e14b6c937cc25002213f2a22` | 2026-11-19 | base of the branch (fast-forward from main); the newest 2i line |
| 2 | `audit/standard-first-2026-11-19` | `6cccfd7a5b2b74f3c29829ed723c0e85128ee322` | 2026-11-19 | clean |
| 3 | `fix/2i-save-freshness-2026-11-19` | `27b074109fdc9f9c32a16db636353e5083226aa4` | 2026-11-19 | clean |
| 4 | `claude/pubpartner-work-notes-2026-11-19` | `4dc10a4265111f7ea55584b9e0630c031e9c06b7` | 2026-11-19 | clean |
| 5 | `gpt/speech-playback-lifecycle` | `6707e7cdeb5f4b6f517742b97939fd70a6437365` | 2026-11-14 | clean |
| 6 | `gpt/recording-endurance-2026-11-13` | `0857cf5f807e368b105a12929740ff20c5b3d6dc` | 2026-11-14 | clean |
| 7 | `gpt/clacker-timecode-verification` | `e8d779830256d2a9a325fbecac7546c85167bcd4` | 2026-11-14 | clean |
| 8 | `codex/2i-beta-test-gates-2026-11-17` | `f52125a8229d01c923a7fb28c2caa9d50dcf25dc` | 2026-11-17 | clean |
| 9 | `codex/github-browser-tests-2026-11-17` | `5965e97801e445154168405ffc3b59ae43a9fff6` | 2026-11-17 | clean |
| 10 | `codex/2i-claude-functional-integration-2026-11-17` | `e0cc000c2adf1a9bad069fe9c650f04e4354fe10` | 2026-11-17 | four conflicts, all resolved to the Nov-18 line |
| 11 | `preview/2i-live-2026-11-17` | `95cfde06fa863ad7ffdff6495d90451647001e6e` | 2026-11-18 | clean once cx-func was merged first |

## Every branch, with its disposition

`carry forward` means its commits are reachable from this branch's tip.

| Branch | Tip commit | Date | Author | Disposition | Note |
|--------|-----------|------|--------|-------------|------|
| `11-12-merge` | `d70952e52c81f89178f4ab557206fcde109bf970` | 2026-11-12 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `audit/standard-first-2026-11-19` | `6cccfd7a5b2b74f3c29829ed723c0e85128ee322` | 2026-11-19 | whatsupjosie | CARRY FORWARD - merged explicitly | See the merge order above. |
| `backup/2i-professional-completion-2026-11-16` | `aaa14b00121c4d0f4369ca9a26021fb18c6f68f3` | 2026-11-15 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `backup/fable-2i-beta-polish-2026-11-17` | `cbc529583202628075c4c319482ae011da2a123f` | 2026-11-16 | Claude | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `backup/main-before-integration-2026-11-11` | `bfbdcf0676c11163063ef369cd419b5667792cfe` | 2026-11-01 | Claude | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `chatgpt-work-2026-11-05` | `1cfb2d2ed96fa9ff183592a1930c9229373e0d79` | 2026-11-12 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `claude-work` | `f3b8863d819dd3f7f635cd8be0facff5b26bf912` | 2026-11-12 | Claude | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `claude-work-2026-11-12` | `5c039e532fa71ab651dbdb83384c266365832329` | 2026-11-12 | Claude | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `claude/2i-coalesce-saves-2026-11-18` | `2a5abdb5255d78c9e14b6c937cc25002213f2a22` | 2026-11-19 | Claude | CARRY FORWARD - merged explicitly | See the merge order above. |
| `claude/pubpartner-work-notes-2026-11-19` | `4dc10a4265111f7ea55584b9e0630c031e9c06b7` | 2026-11-19 | Claude | CARRY FORWARD - merged explicitly | See the merge order above. |
| `codex/2i-beta-test-gates-2026-11-17` | `f52125a8229d01c923a7fb28c2caa9d50dcf25dc` | 2026-11-17 | whatsupjosie | CARRY FORWARD - merged explicitly | See the merge order above. |
| `codex/2i-claude-console-consolidation-2026-11-17` | `32d142457d041d0f7bba54ab96c16dca908717e3` | 2026-11-17 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `codex/2i-claude-functional-integration-2026-11-17` | `e0cc000c2adf1a9bad069fe9c650f04e4354fe10` | 2026-11-17 | whatsupjosie | CARRY FORWARD - merged explicitly | See the merge order above. |
| `codex/2i-claude-functional-reconcile-2026-11-18` | `1e3b3620bdbb5b118ac74a550d8eacdf11a54930` | 2026-11-18 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `codex/2i-integration-readiness-2026-11-18` | `ef879b6d3cbb7fb5365a22ddc5ddd31d3b6adb9c` | 2026-11-18 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `codex/2i-offline-save-2026-11-16` | `45d572194f7dfd52212a5686f935c9f54ed663a9` | 2026-11-16 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `codex/2i-save-routing-hardening-2026-11-18` | `7e70e0536416490ae42a97208915c70073740973` | 2026-11-18 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `codex/2i-typewriter-manuscript-bridge-2026-11-18` | `4ca32875bcc58ecefe5b06ce718398457340c32d` | 2026-11-18 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `codex/2i-ui-readability-2026-11-16` | `f47b11b6767bb164ba3fbb4886b893d865ee53b5` | 2026-11-16 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `codex/github-browser-tests-2026-11-17` | `5965e97801e445154168405ffc3b59ae43a9fff6` | 2026-11-17 | whatsupjosie | CARRY FORWARD - merged explicitly | See the merge order above. |
| `codex/recovery-floor-2026-11-01` | `1e33789ba82d231384b04063b1b68325ca94df4c` | 2026-11-01 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `fable/2i-beta-polish-2026-11-16` | `cbc529583202628075c4c319482ae011da2a123f` | 2026-11-16 | Claude | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `fable/2i-polish-2026-11-16` | `51a34cafae0a6965e75eebe9001f392463063a0f` | 2026-11-16 | Claude | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `fable/integration-2026-11-13` | `764874a74627adf455c97a99bc56597257170282` | 2026-11-13 | Claude | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `fix/2i-save-freshness-2026-11-19` | `27b074109fdc9f9c32a16db636353e5083226aa4` | 2026-11-19 | whatsupjosie | CARRY FORWARD - merged explicitly | See the merge order above. |
| `gpt-work` | `43e71839bd243b47768256980b376bf90424cd7d` | 2026-11-01 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `gpt/2i-narrative-intelligence-2026-11-15` | `84d9e27c7e74f1345d6d07401a125b54ca2c82c2` | 2026-11-15 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `gpt/2i-professional-completion-2026-11-15` | `aaa14b00121c4d0f4369ca9a26021fb18c6f68f3` | 2026-11-15 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `gpt/clacker-timecode-verification` | `e8d779830256d2a9a325fbecac7546c85167bcd4` | 2026-11-14 | whatsupjosie | CARRY FORWARD - merged explicitly | See the merge order above. |
| `gpt/control-ui-wiring-2026-11-08` | `e86d20b970368918448e6008d45f5b690620bba1` | 2026-11-08 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `gpt/guest-recording-triage-2026-11-13` | `ffd58a84e2a0038e566998b0fe240b0046c6eb26` | 2026-11-13 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `gpt/live-studio-setup-2026-11-09` | `1cfb2d2ed96fa9ff183592a1930c9229373e0d79` | 2026-11-12 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `gpt/participant-clock-prototype-2026-11-13` | `466eee8e7c17d48d92f5907e2a0727f60f5070e0` | 2026-11-14 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `gpt/primp-canvas-preparation-2026-11-07` | `946016ed083da61f1034f94c44cd9e271be32acd` | 2026-11-09 | whatsupjosie | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `gpt/recording-endurance-2026-11-13` | `0857cf5f807e368b105a12929740ff20c5b3d6dc` | 2026-11-14 | whatsupjosie | CARRY FORWARD - merged explicitly | See the merge order above. |
| `gpt/speech-playback-lifecycle` | `6707e7cdeb5f4b6f517742b97939fd70a6437365` | 2026-11-14 | whatsupjosie | CARRY FORWARD - merged explicitly | See the merge order above. |
| `integration-2026-11-04` | `c82069b47b04eac56cca1fb4f6a4eb16c44d32ae` | 2026-11-04 | Claude | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `main` | `c82069b47b04eac56cca1fb4f6a4eb16c44d32ae` | 2026-11-04 | Claude | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `preview/2i-live-2026-11-17` | `95cfde06fa863ad7ffdff6495d90451647001e6e` | 2026-11-18 | whatsupjosie | CARRY FORWARD - merged explicitly | See the merge order above. |
| `sandbox-as-code-2026-11-01` | `8a06383b420495f9c71b20c7bef711814fc8b6f1` | 2026-11-01 | Claude | CARRY FORWARD - already contained | Ancestor of this branch's tip; no separate merge needed. |
| `2i-beta-polish` | `df737caaeff206e4128932532663776af74ec0e8` | 2026-11-17 | Claude | NEEDS JOSIE'S DECISION | Three code commits (26fca15, 3fb483f, 6c45e37) exist on no other branch. All three conflict. See MERGE_REPORT_2026-11-20.md. |
| `backup/claude-2i-beta-polish-2026-11-17` | `df737caaeff206e4128932532663776af74ec0e8` | 2026-11-17 | Claude | NEEDS JOSIE'S DECISION | Identical commit to 2i-beta-polish (df737caae). Same decision. |
| `backup/claude-console-touch-typewriter-2026-11-17` | `3ee394a7ca66edd5e152eb0eca4de1709333bd7c` | 2026-11-17 | Claude | CARRY FORWARD - already in, by exact port | Identical commit to console-touch-typewriter-keys (3ee394a7c). Same disposition. |
| `codex/2i-typewriter-visual-2026-11-17` | `69e155031c2974c63a5360d400762428524d4884` | 2026-11-17 | whatsupjosie | NEEDS JOSIE'S DECISION | Replaces the interactive typewriter iframe with a static image and a decorative paper preview, and drops the Foresight file-tray view selector. Carries the only file:// artwork fix. See MERGE_REPORT_2026-11-20.md. |
| `codex/main-debug-20261119` | `d3b9db81fc4a35d05db82de1d0de24dacf17e973` | 2026-11-19 | whatsupjosie | NEEDS JOSIE'S DECISION | 25 commits of real recording/camera/timeline work on a line parallel to main. Four of six conflicted files resolve as clean unions; static/production25d_app.js and static/production25d_storage.js are two incompatible recording architectures. Resolution work preserved on integration/main-debug-union-trial-2026-11-20 (eacde8753). |
| `console-touch-typewriter-keys` | `3ee394a7ca66edd5e152eb0eca4de1709333bd7c` | 2026-11-17 | Claude | CARRY FORWARD - already in, by exact port | Verified by blob: 11 of 16 changed files are byte-identical in this branch; the other five are strict supersets with zero dropped lines. Dropped as a merge on Josie's 2026-11-20 instruction. |

## Names that pointed at the same commit

Merging either of a pair adds nothing beyond the other.

| Commit | Branch names |
|--------|--------------|
| `1cfb2d2ed96fa9ff183592a1930c9229373e0d79` | `chatgpt-work-2026-11-05`, `gpt/live-studio-setup-2026-11-09` |
| `3ee394a7ca66edd5e152eb0eca4de1709333bd7c` | `backup/claude-console-touch-typewriter-2026-11-17`, `console-touch-typewriter-keys` |
| `aaa14b00121c4d0f4369ca9a26021fb18c6f68f3` | `backup/2i-professional-completion-2026-11-16`, `gpt/2i-professional-completion-2026-11-15` |
| `c82069b47b04eac56cca1fb4f6a4eb16c44d32ae` | `integration-2026-11-04`, `main` |
| `cbc529583202628075c4c319482ae011da2a123f` | `backup/fable-2i-beta-polish-2026-11-17`, `fable/2i-beta-polish-2026-11-16` |
| `df737caaeff206e4128932532663776af74ec0e8` | `2i-beta-polish`, `backup/claude-2i-beta-polish-2026-11-17` |

## Branches that are ancestors of main

These had nothing ahead of `main` and so contributed nothing to merge:
`backup/main-before-integration-2026-11-11`, `codex/recovery-floor-2026-11-01`,
`gpt-work`, `sandbox-as-code-2026-11-01`. `integration-2026-11-04` pointed at
exactly `main`'s commit.

## Branch kept for a pending decision

`integration/main-debug-union-trial-2026-11-20` (`eacde8753`) holds the completed
union resolutions for `codex/main-debug-20261119` with the two production25d files
left at this branch's version. It is deliberately not part of this branch.

