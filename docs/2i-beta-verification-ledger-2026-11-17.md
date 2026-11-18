# 2i beta verification ledger | 2026-11-17

## Scope and source of truth

- Repository: `whatsupjosie/Beyond-October`
- Application source branch inspected: `fable/2i-beta-polish-2026-11-16`
- Separate CI branch: `codex/2i-beta-test-gates-2026-11-17`
- No edits to `main`, no use of the user's borrowed computer, and no claim of a finished beta.

## Completed: focused JavaScript execution

**67 individual checks in 27 existing `tests/test_2i_*_node.js` test files: 67 passed, 0 failed.**

Source files and test bodies were fetched directly from the source branch through the GitHub connector. They were executed in a temporary V8 isolate with compatibility stand-ins for relevant Node test/assert/filesystem/VM APIs, plus fixture-specific browser APIs. This is **not** an actual Node.js `node --test` invocation and is **not** a browser, filesystem, or operating-system acceptance test. The result is limited to the behaviors exercised by those assertions in the harness.

Coverage included:

- Save Now: new and existing file handle, writes in progress, late edits, cancelled picker, failed write, concurrent switch, external-file conflicts before and during write, download fallback, browser recovery shelf and page-history identification.
- Document safety: independent drafts from parallel tabs, history-safe studio handoff, command availability, protected passages, revision identity, compare views, annotation anchoring, reference rendering, Unicode handling, screenwriting export and rich archive preservation.
- 2i integration logic: writing-room simulated host flow, narrative context and revision guardrails, typing cues, studio seat routing, menus, keyboard shortcut isolation, capture failure accounting and source-import guardrails.

A separate simulated narrative-room test passed, including its internally accumulated scenario checks. It counts as **one existing Node test**, not seven extra test passes.

All results are **focused behavioral evidence**, not a beta approval.

## Remote GitHub Actions attempts

- Chromium smoke run: `44239174124`, failed. A retry failed as well.
- Expanded beta acceptance run: `44239586896`, failed.
- Jobs failed in approximately 2–3 seconds, before assignment to a runner and with zero executed steps. They are **infrastructure failures**, not application-test failures.
- Precise GitHub account-level or runner allocation reason is not established from available logs. Do not describe these as passed tests.

Workflow file in this branch: `.github/workflows/2i-beta-acceptance.yml`.

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
