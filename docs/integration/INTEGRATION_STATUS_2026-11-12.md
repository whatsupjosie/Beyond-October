# PubCast integration candidate — 2026-11-12

**Branch:** `11-12-merge`  
**Scope:** Claude + GPT integration candidate only. **Not merged into `main`.**  
**Status:** Source histories combined; acceptance testing and owner decisions outstanding. No market-readiness claim.

## Source preservation and merge provenance

GitHub branch comparisons were executed on 2026-11-12 before documenting this state.

- `main` baseline: `c82069b47b04eac56cca1fb4f6a4eb16c44d32ae` (unchanged during this integration).
- Claude recovery / handoff source: `claude-work-2026-11-12` at `5c039e532fa71ab651dbdb83384c266365832329`. This is one commit after `claude-work` and includes the recovered chat files.
- GPT live studio source: `gpt/live-studio-setup-2026-11-09` at `1cfb2d2ed96fa9ff183592a1930c9229373e0d79`. It already contains `gpt/control-ui-wiring-2026-11-08`, and is identical to `chatgpt-work-2026-11-05`.
- GPT Primp source: `gpt/primp-canvas-preparation-2026-11-07` at `946016ed083da61f1034f94c44cd9e271be32acd`.
- PR #5 merged GPT live studio into this branch (merge commit `fcab09cb4438c23c6d33bb9c7b797a7ab902256c`).
- PR #6 merged GPT Primp into this branch (merge commit `922d74ddd277a5966aacc0e8de1efe083d215564`).
- Separate follow-up commits add missing camera-persistence imports and a regression test.

**History check:** GitHub comparisons found zero commits on any other current development branch absent from `11-12-merge` (including `gpt-work`, `codex/recovery-floor-2026-11-01`, and `sandbox-as-code-2026-11-01`). Branches remain intact; no force push and no `main` update.

**Source tree check:** Against `main`, Claude's recovery tip, GPT live studio, and GPT Primp, zero files present on those source trees are absent from the candidate tree. **This checks path preservation, not equivalence of contents or behavior.** The candidate intentionally contains modifications to existing paths; those require regression testing.

## Work accounted for in the branch

- Claude: production notes, Filler Cream and its documentation, EQ/Fable studies, Iteration Wallet design notes, recovered 27-effort harvest, November 2 pitch, partial wallet communication design.
- GPT: UI/control wiring, clacker/actor-frame evidence, studio/camera work, live studio and Blackbox source, replay/retention/date-binding research and testing documents, related tests.
- GPT Primp: avatar mirror/canvas UI and assets, authoring acceptance documentation, tests, known paint visibility limitations.
- Existing `main`: prior integration and foundation code, preserved as ancestor.

The three recovered chat files are on `docs/chat_recovered/`. The wallet design copy is explicitly partial and is not represented as the complete original.

## Verification performed during this integration

- VERIFIED: Branch source ancestry, PR merge completion, main SHA, tree-file presence, and source differences by GitHub compare and Git tree API.
- VERIFIED BY CODE INSPECTION: Both camera manager modules called `write_json` without importing it; the candidate now imports `write_json` from `modules.persistence`.
- TEST CREATED BUT NOT EXECUTED HERE: `tests/test_camera_configuration_persistence.py` checks both managers write and update actual JSON files.
- **NOT VERIFIED:** Full pytest suite, real application boot, Playwright browser runs, audio hardware, phone/Chromium, Windows/PowerShell 5, integration in physical production, and complete Foresight Counter commissioning. No GitHub Actions were used.

Do not treat GitHub's successful merge, presence of tests, or an earlier source-branch test result as a passing integration test.

## Known high-priority unfinished checks

1. **Recording:** On the GPT control UI branch, the full suite previously reported 2,367 passed, 6 failed, 6 skipped; the six failures concern browser recording, Stop-button enablement, PANIC delay and timeouts. Four failures reportedly reproduced on an older version. Rerun on the candidate and verify real behavior.
2. **Guest audio:** GPT reported two-guest audio failing within 1–4 minutes during a 30-minute test. Unresolved.
3. **Replay access / privacy:** GPT's replay uploads were flagged as accessible to anyone with the host address. Treat as a security blocker for any deployed multi-user service until checked and fixed with owner-approved access policy.
4. **Consent and limits:** Guest acceptance wording, 5 MB upload limit, 8-hour guest passes, 5-minute invitations, and 200-person cap were introduced without the owner's approval. Preserve as open decisions; do not normalize them as accepted requirements.
5. **Primp:** The earlier branch reported paint changes barely visible due to cyan glow over starter avatars, and placeholder avatar models; passing unit tests did not establish visual usability.
6. **Camera persistence:** Missing import corrected in both managers. New regression test and save/reload workflow need an executed run.
7. **Intermittent browser race:** `tests/test_world_walk_host_integration.py` may raise `StopIteration` before a child frame registers. Not fixed in this pass.
8. **Other static flags:** `VDIReport` typing annotation import, `WebSocket` in an unused snippet, and `os` in a development tool require targeted review.
9. **Foresight Counter:** Full acceptance sequence (real start, tray sizing, open/save/reopen, rollback, quit/restart, graphics compatibility) has not been newly commissioned.
10. **Offline/client/production:** STT/TTS/lip sync, studio cameras, clacker, export, EQ/persona continuity, Blackbox retention, VoxelStudio and Filler Cream require cross-system workflow tests, not only isolated unit tests.

## Decisions reserved to owner

- Whether and when to promote this integration candidate to `main`.
- Replay access, guest recording/AI participation consent, invited users, upload limits, retention and account semantics.
- EQ study prompt contains a personal quotation flagged by Claude as contrary to the owner's privacy preference. Do not make alterations to the owner's words without authorization; review access before any broader distribution.
- Iteration Wallet boundaries and what it may accept/send; no automatic authority transfer.
- three.js r128 vs r160 compatibility and other visual decisions.
- Feature adoption where tests reveal divergent behaviors; no silent overwrites.

## Work not established as recoverable from remote branches

Claude's handoff reports a separate uncommitted PEQ integration/lineage snapshot (75 files and a manifest) and a full Wallet communication-design attachment not present in remote branches. The recovered Wallet file is explicitly partial. Some chat-only failure and duplicate-file-audit details were not found as complete standalone files. **Do not claim these originals are integrated until independently recovered.** Record without inventing missing content; this does not block unrelated source integration.

## Acceptance gate before any promotion to main

1. Run candidate full tests and critical targeted suites; record environment, command, result, skipped tests and evidence.
2. Test end-to-end workflows, recording/PANIC, multi-guest audio, and Foresight Counter commissioning.
3. Resolve or safely isolate any open security and high-severity regression.
4. Report source-vs-candidate behavioral differences and owner-reserved decisions.
5. Obtain explicit owner approval for the **exact candidate commit** proposed for `main`.
6. Recheck `main` head and preserve rollback refs before promotion.

Until those gates are met, this branch is **integrated in Git history, not certified as production-ready**.
