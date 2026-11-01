# PubCast + Foresight — continued implementation checkpoint

## Mission
Deliver a usable PubCast workbench: launch Reach into blank Foresight, open real 2i and Pub Partner trays, save/reopen a manuscript, send a real provider-backed reply when credentials are configured. Preserve originals and do not call a page-200 check end-to-end certification.

## Source baseline
Started from `PubCast_Foresight_Agent_Continued_2026-10-14.zip`, extracted into a separate working directory. The original ZIP was not modified.

## Changes made in this run
1. `tests/test_writers_room_real_http.py` — **new real HTTP integration test**, using a subprocess with a bound loopback port and disposable temporary document database. Creates a manuscript with partner conversation state, checks optimistic revision conflict, reads it, terminates the server, restarts a fresh server process, retrieves the manuscript again, and saves a second revision. This specifically addresses the earlier gap where tests only used FastAPI TestClient or source-string assertions. Uses multiprocessing spawn for portability.
2. `tools/foresight_checks/check_workbench_browser.py` — **new Chromium browser smoke test** for a real Reach server. It opens a fresh Counter, checks zero initial trays, opens 2i and Pub Partner using the actual program registry, and verifies their iframe navigation. It intentionally does not fake an AI response or claim to have tested manuscript editing in the browser.
3. `.github/workflows/foresight-workbench.yml` — installs Chromium/Playwright; adds packaged preflight, real HTTP manuscript restart test, and a real Reach+Chromium smoke step; uploads server logs alongside JUnit XML. Adds changed-file triggers for these checks and launchers. Workflow YAML parsed successfully. **Not yet run on GitHub**; browser smoke may reveal startup/auth/graphics issues requiring repair.

## Evidence collected
- `python -m pytest -q tests/test_writers_room_real_http.py`: **1 passed**.
- `python -m pytest -q tests/test_writers_room_real_http.py tests/test_reach_writers_room.py tests/test_foresight_workbench_acceptance.py`: **17 passed**.
- `python tools/workbench_preflight.py`: **PASS**, including routes/assets/2i runtime checks (in-process only).
- Python compilation for both new scripts: PASS.
- Workflow YAML parser: PASS.
- **No browser run completed here**; no live AI response demonstrated. Do not claim certified first-use workbench.

## Immediate next engineering actions
1. Run GitHub workflow on a safe development branch, ensuring repository checkout root corresponds to the `october/` directory. Diagnose Chromium startup, Foresight rendering, authentication overlay, and iframe loading from its server log and Playwright errors.
2. Extend browser test to interact with 2i's actual UI (type/save/reload), then check Pub Partner UI messaging and provider-unavailable status. Do not silently use a mock reply as live-provider certification.
3. Test startup with a genuinely empty data directory and configured persistent owner credentials, without touching bundled user data. Review process-local JWT secret warning: browser login tokens may not survive restart if persistent secret is not configured.
4. Improve the program picker/crowded tray behavior only where it blocks normal use; defer decorative polish.
5. Package another full source ZIP with exact pass/fail evidence and a single consolidated handoff after sustained implementation, not after each small bug.

## Security and caution
Do not push bundled `data/`, API keys, user manuscripts, tokens, or entire archive to public GitHub. Commit only reviewed code and tests. Real AI replies require configured provider credentials and reachable backend. CI's Chromium result is not a substitute for the user's machine-specific final acceptance.
