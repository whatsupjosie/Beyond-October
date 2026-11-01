# PubCast prime integration — October 26, 2026 (Claude)

Branch: `prime/integrated-2026-10-26` on whatsupjosie/October.
Parent chain: `1420d51` (GitHub main, five-round review) → `0fb401c` (reconstructed reviewed build, also pushed as `prime/reviewed-2026-10-25`) → `128d6d6` (merged-all and every October branch) → `3008c71` (Alex rephrase module). Main has not been changed.

## Why main was broken

The five-round review fixed the Oct 25 full-build ZIP, then pushed only its own changed files onto `1f2b130`. That commit never had the ~250 files the full build carried (Foresight workspace, file formats, host tools, rich 2i documents, turn requests and more). Result: `import main` failed on a clean checkout and zero tests ran.

## What was done

1. **Reviewed build reconstructed exactly** (`0fb401c`): the intact Oct 25 full build (ChatGPT recovery package, Part 1) plus every file the review changed (from `1420d51`) plus the 51 storage-scaffolding records the review restored. On the review's own environment (Python 3.12, strict gates) it gives **1,409 passed, 6 skipped**, identical to `handoffs/five-round-review-2026-10-25/round5-strict-final.log`.
2. **merged-all integrated** (`128d6d6`). The merged-all ZIP was truncated; 836 of its files survived. Classification against the reviewed tree and every GitHub branch: 711 identical, 113 from known branches, 12 unique (that session's own work). Its tests had been cut off, but the session's earlier archive `PubCast_changes_on_main_1f2b130_2026-10-25.zip` (Part 2 recovery store) had six new tests and four test updates, all restored.
   - Alex Core: witness/anchor recovery mid-conversation, negation-aware whole-word matching, memory path containment. Targeted edits; state machine, memory logic and personality untouched.
   - `/api/internal/*` routes require mod when auth is enforced; runtime folders created at startup.
   - `modules/unicode_guard.py`: invalid-Unicode JSON returns 400 instead of 500.
   - `modules/control_plane_guard.py`: 24 live-control routes require mod when `PUBCAST_ENFORCE_AUTH` is on; default behaviour unchanged.
   - Per-route request limits (Foresight 44 MB, 2i documents 3 MB, media 256 MB).
   - 2i reload data-loss fix.
   - jsdom 26.1.0; scikit-learn declared.
   - Branches, each three-way merged against its real fork point `b44db35`, no conflicts:
     - `evo/semantic-runtime`: segmented capture, range preservation, 2i editor engine and vendor assets, avatar recovery folder.
     - `pete-director`.
     - `care-routines`: five files.
     - `october-24-prime-rust-recovery`: `experiments/`, isolated.
     - `integration-ci`.
     - `status-test` docs.
   - `main.py`: four conflicts, all the reviewed build's EVO start/stop and host-tool lines against an equivalent reordering. The reviewed side was kept.
3. **New tests**, replacing the originals lost with the ZIP tail:
   - `tests/test_request_guards.py`: 37 tests covering both guards.
   - `tests/test_2i_reload_restores_solo_text.py`: real Chromium. Run against the unfixed page it fails (blank textarea; manuscript wiped to `[]` on the first keystroke); with the fix it passes.
4. **Test-only leak fixes** caught by the strict gate:
   - an unclosed file in a care-routines test;
   - the FFmpeg log handle in a simulated-crash capture test. Production code closes it on every normal path; a real crash releases it.
5. **Alex rephrase module** (`3008c71`): `modules/pubpartner_rephrase.py` with its 16 tests, bytes matching the recovery index. Unwired.

## Verification (observed)

| Tree | Environment | Result |
|---|---|---|
| main `1420d51` (clean clone) | 3.13 | import fails; 0 tests collected |
| `0fb401c` reviewed | 3.12, strict | 1,409 passed, 6 skipped |
| `128d6d6` working tree | 3.12, strict | 1,664 passed, 7 skipped, 0 failed |
| `128d6d6` fresh export, run 1 | 3.12, strict | 1,664 passed, 7 skipped, 0 failed |
| `128d6d6` fresh export, run 2 | 3.12, strict | 1,664 passed, 7 skipped, 0 failed |
| `128d6d6` fresh export, Playwright 1.63 + Chromium | 3.12 | 1,687 passed, 15 failed, 2 errors, 3 skipped (see below) |
| `3008c71` fresh GitHub clone | 3.12, strict | 1,680 passed, 7 skipped, 0 failed |

"Strict" means asyncio debug, with ResourceWarning, RuntimeWarning and unraisable-exception warnings promoted to errors, matching the review. The skips are opt-in Alex Little One research tests and browser checks when Playwright is absent.

ChatGPT's `test_eq_known_defects.py` against this tree: 6 passed, 1 failed. The failing case calls `_analyze_input` directly. Recovery is applied one level up in `process_message`, which `tests/test_alex_witness_recovery.py` exercises and which passes. Inferred: a test-scope mismatch, not a missing fix. ChatGPT should either move that probe to `process_message` or argue that recovery belongs in the analyzer.

## Browser tests (never green before; not caused by this integration)

With Playwright 1.63 and a real Chromium, 17 Foresight browser tests fail: all 13 in `test_foresight_file_workspace.py` and 4 in `test_foresight_airgapped_ui.py`. The same 17 fail on the reviewed build `0fb401c`, which skipped them because Playwright was not installed. The merged-all run used an older `foresight_files.js`.

Observed cause for the file-workspace tests: `static/foresight_files.js` now scopes working copies to the signed-in owner through `/api/writers-room/config`, and 2i calls `/api/auth/status` before opening a file. The test's stand-in server serves neither route, so the provider shows "Sign in to Reach before accessing working copies" and 2i never mounts. The code under test is never reached. Serving the real routes in the fixture got past the first error, but then needed an initialised user database. That fixture rework was reverted to keep this commit clean.

The air-gapped UI timeouts were not diagnosed.

Unverified: whether the real Foresight file flow works end to end in the full app. That is the commissioning goal in `CLAUDE.md`, and the next piece of work.

## Not verified

- Windows / PowerShell 5 launch, real cameras, microphones, GPU rendering, a live language model, phone deployment.
- Python 3.13: the suite under strict gates surfaces unclosed SQLite connections. 3.13 newly warns on these. They are real resource leaks (warnings only at runtime), not yet fixed.

## Not integrated (preserved, needs a decision or ChatGPT's recovery pass)

- 187 additive straggler targets still absent (46 `.py`, 24 `.rs`, plus docs and logs), many with ambiguous target paths (for example root-level `vault.py`, `jeremy.py`, `memory.py` from `EVO_Claude_Continuation`). Index: ChatGPT package Part 1 `STRAGGLERS/INTEGRATION_INDEX.csv`. 86 entries are flagged "different version, review before merge".
- merged-all's own test fixes for nested-lifespan isolation were not needed: the reviewed build solves the same problem with isolated-process lifecycle tests, and the full suite passes.

## Decisions waiting on Josie

1. Which branch becomes main, and the name of the new official repo.
2. Server default: binds all interfaces with auth off. Workspace file read/write is reachable from the local network unless `PUBCAST_ENFORCE_AUTH` is set.
3. Seven routes stay open even with auth on: STT, TTS, pubworld recognize, block-kit preview, media intake, mic cough, governance consent.
4. Unwired code: 988/crisis text in `companion_support/conversation_pacing.py` and `modules/wired/` is not on the live path, consistent with Josie's rule that Alex gives resources only when asked; 16 never-imported modules; the rephrase module.
5. Memory notes say `alex_core.py` must never be wired into PubCast, but `main.py` imports and starts `AlexCore`. Left as is.
6. EQ Revamp Plan items 2–7 (they touch Alex Core more deeply).
7. Google Fonts on three older pages (offline falls back to system fonts); the missing `/assets/rooms/dressing_polish.png`.

## Reproduce

Python 3.12, from the repo root:

    pip install -r requirements.txt -r requirements-dev.txt
    PYTHONASYNCIODEBUG=1 python -W error::ResourceWarning -W error::RuntimeWarning -m pytest -q -p no:cacheprovider -W default::DeprecationWarning -W error::pytest.PytestUnraisableExceptionWarning

`requirements-dev.txt` pins Playwright 1.56.0. Its browser must be installed separately (`python -m playwright install chromium`), or the browser tests skip.

## Next exact action

Josie picks the main/new-repo option. Then: push `prime/integrated-2026-10-26` to the new repo (or fast-forward October main), rerun the strict suite from a fresh clone there, and continue the directive's workstreams on that base.
