# 2i beta verification ledger | 2026-11-17

## Scope and source of truth

- Repository: `whatsupjosie/Beyond-October`
- Application source branch inspected: `fable/2i-beta-polish-2026-11-16`
- Separate CI branch: `codex/2i-beta-test-gates-2026-11-17`
- No edits to `main`, no use of the user's borrowed computer, and no claim of a finished beta.

## Completed: focused JavaScript execution

**67 individual checks in 27 existing `tests/test_2i_*_node.js` test files: 67 passed, 0 failed.**

**7 newly added hosted Save Now checks in `tests/test_2i_hosted_save_races_node.js`: 7 passed, 0 failed in the same isolated compatibility harness. Combined total: 74 focused checks passed, 0 failed.**

Source files and test bodies were fetched directly from the source branch through the GitHub connector. They were executed in a temporary V8 isolate with compatibility stand-ins for relevant Node test/assert/filesystem/VM APIs, plus fixture-specific browser APIs. This is **not** an actual Node.js `node --test` invocation and is **not** a browser, filesystem, or operating-system acceptance test. The result is limited to the behaviors exercised by those assertions in the harness.

Coverage included:

- Save Now: new and existing file handle, writes in progress, late edits, cancelled picker, failed write, concurrent switch, external-file conflicts before and during write, download fallback, browser recovery shelf and page-history identification.
- Document safety: independent drafts from parallel tabs, history-safe studio handoff, command availability, protected passages, revision identity, compare views, annotation anchoring, reference rendering, Unicode handling, screenwriting export and rich archive preservation.
- 2i integration logic: writing-room simulated host flow, narrative context and revision guardrails, typing cues, studio seat routing, menus, keyboard shortcut isolation, capture failure accounting and source-import guardrails.

A separate simulated narrative-room test passed, including its internally accumulated scenario checks. It counts as **one existing Node test**, not seven extra test passes.

All results are **focused behavioral evidence**, not a beta approval.

## Added test coverage

The new permanent test file `tests/test_2i_hosted_save_races_node.js` targets the real hosted saveDocument implementation, including a late edit during a request, two simultaneous Save clicks, HTTP 409, server failure, no-network browser recovery, and a manuscript switch during a late response. The source was checked in the isolated V8 harness and saved on the CI branch. **Its native Node CI execution is still blocked by runner allocation.**

## Remote GitHub Actions attempts

- Chromium smoke run: `44239174124`, failed. A retry failed as well.
- Expanded beta acceptance runs: `44239586896` and `44241747253`, both failed before any step.
- Jobs failed in approximately 2–3 seconds, before assignment to a runner and with zero executed steps. They are **infrastructure failures**, not application-test failures.
- Precise GitHub account-level or runner allocation reason is not established from available logs. Do not describe these as passed tests.

Workflow file in this branch: `.github/workflows/2i-beta-acceptance.yml`.

## Parallel Claude work discovered (2026-11-17, Los Angeles time)

**Do not mistake Fable's prior branch for the latest combined 2i implementation.** Claude published two separate branches from main, both still unmerged:

- `console-touch-typewriter-keys`, latest commit `3ee394a7c`: a separate `/typewriter-console` bench page built around `static/typewriter_keys.webp` (2560 × 1430), 48 mapped controls (47 keys and the carriage-return lever), multi-touch/hardware keyboard handling, optional Web Audio strike/lever/bell sounds and touchable studio consoles. **Not yet integrated with 2i's manuscript editing**; the bench page changes only its own decorative paper. Claude's handoff reports full suite `2302 passed, 6 skipped, 0 failed` after its polish pass; this report has not been independently reproduced here. `handoffs/CONSOLE_TOUCH_AND_TYPEWRITER_2026-11-17.md`.
- `2i-beta-polish`, latest commit `df737caae`: served v22 page and reach.css fixes, mobile layout, Write-mode line locks, safe keyboard undo, Replace All and correct attribution of UI notifications. Claude's handoff reports `2283 passed, 6 skipped, 0 failed` and 33 new browser checks; this report has not been independently reproduced here. `handoffs/2I_BETA_POLISH_2026-11-17.md`.
- The branches are **not integrated into Fable's `fable/2i-beta-polish-2026-11-16` baseline** used for our focused V8 checks. Treat all three as distinct sources of verified and unverified contributions. Do not merge blindly or infer cumulative test counts.
- Independently read Claude's typewriter manifest through GitHub: 48 unique non-overlapping mapped hotspots, within normalized image bounds. The lever is the RETURN control. This is structural manifest evidence, not a direct tap or sound test.
- Owner supplied two lapis-blue, malachite-green and brass typewriter images on 2026-11-17, and said she had given them to Claude earlier. Do not substitute an unrelated new drawing or redesign away from those references.
- Integration requirement: preserve the 2i real manuscript as source of truth while connecting the `pubcast:key` event from the touchable typewriter to the active 2i editor; restore cursor/selection, undo, save/recovery, accessibility, and optional audio. Reuse the original hotspots and audio implementation rather than rebuilding.
- An experimental `codex/2i-typewriter-visual-2026-11-17` branch predates discovery of the two Claude branches. **Do not merge it without revisiting its approach**; it only exposes Fable's decorative scene more widely, not Claude's functioning key art.

## Required verification before a beta decision

1. **Run the actual Node suite:** `node --test tests/test_2i_*_node.js`; record output, duration, failures and skips.
2. **Run Chromium/UI and persistence:** install `requirements.txt` and `requirements-dev.txt`, run `python -m playwright install --with-deps chromium`, then `python -m pytest -v -ra tests/test_2i_*.py tests/test_saves_survive_restart.py tests/test_writers_room_real_http.py tests/test_reach_writers_room.py`.
3. **Manuscript acceptance:** type a representative multi-page document in notebook, typewriter and standard views; Save Now; close/reopen; confirm byte-for-byte text, formatting, versions, blank lines, unsaved-state behavior and offline recovery.
4. **Real hosted integration:** verify 2i mounted inside PubCast, menus, navigation, standalone/host parity, touch and keyboard, document ownership, offline behavior and return-to-room state.
5. **Studio and recording acceptance:** verify camera-control operations, stop/PANIC stop, clacker/synchronization, crash/restore and a full 30-minute test capture with actual playback.
6. **Packaging and deployment:** verify runtime dependencies and the Windows executable deliverable, and independently review outstanding design/UX acceptance criteria.

Do not mark beta-ready based solely on this ledger. An unexecuted browser check remains unverified even when its equivalent simulated JavaScript unit checks pass.

## Reproducibility and change-control

- Do not rebuild already-working modules just to satisfy the checks.
- For actual defects, first write a regression that fails before the repair, then fix on a dedicated branch and rerun the relevant area and broader gates.
- Preserve existing work and `main`; merge only after independent review and evidence-backed acceptance.
- Once GitHub-hosted runners are available, use the existing CI workflow to generate persistent logs and JUnit output in GitHub Actions artifacts.

## ChatGPT native-runtime follow-up

A separate execution pass used ChatGPT's actual temporary execution container rather than the Code Mode V8 compatibility harness or GitHub-hosted Actions runners. This container has Node.js 22, Python Playwright, and Chromium installed, but cannot clone the full GitHub repository because direct outbound DNS/network access is blocked. The selected source files were therefore transferred from the GitHub connector.

- **Native `node --test`: 9 passed, 0 failed** across the original studio-bridge tests (2) and hosted Save Now race/failure tests (7). Test files were run through the real Node test runner, with the production bridge files copied unchanged and a source-identical hosted-save function excerpt. Git blob SHA for the bridge is `c526c173d8fa7845fc107ae5a65b54f0a48a6acb`; the bridge's original Node test has SHA `e5918b98f8fa0c4b82fdb0853365a3b6adcfc8be`. The hosted save excerpt matches GitHub's source length and FNV-1a digest (`1981` JavaScript UTF-16 units; `acd415c6`).
- **Real headless Chromium via Playwright:** 7 focused browser assertions passed, 0 failed, using the production studio-bridge script in a minimal HTML page at 390×844 viewport. Direct file URLs are administratively blocked in this runtime, so the page content and script were injected into Chromium. This does *not* validate the complete 2i interface.
- **Not executed in the native container:** the full 27-file Node suite, the real 2i HTML page with all companion assets, server-backed Save Now persistence, genuine file reopen, visual fidelity, Windows packaging, 30-minute recording test.

Do not merge or announce beta completion from these partial native-runtime results. They complement, not replace, the earlier 74 focused V8 compatibility checks.
