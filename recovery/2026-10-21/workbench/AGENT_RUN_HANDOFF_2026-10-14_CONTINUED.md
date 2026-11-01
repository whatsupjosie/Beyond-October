# PubCast / Foresight — continued engineering handoff

## Objective
A first usable PubCast workbench: launch Reach into a blank Foresight Counter, open 2i and Pub Partner in trays, save manuscripts, and exchange real provider-backed messages. This archive is a **tested engineering checkpoint**, not a claim of completed GUI or live-provider certification.

## Baseline and preservation
Based on `PubCast_Foresight_Agent_Followup_2026-10-14.zip`. Previous source archives were not modified. The source is packaged as a complete `october/` tree.

## Changes in this pass
1. **2i local-document routing isolation** (`2i/2i-assets/reach.js`): Previously `baseURL()` followed `llmCfg.pubpartner.endpoint`, meaning configuring a remote Pub Partner AI endpoint could inadvertently send manuscript list, save, authentication, and account requests to that remote server instead of local Reach. The document/account API base is now explicitly the local Reach origin. AI turns may still use the separately configured Pub Partner endpoint.
2. **2i optional character-profile failure isolation** (`2i/2i-assets/reach.js`): Failure of `/api/pubpartner/profiles/friend` no longer prevents `connectReach()` from completing. Manuscript storage can stay connected even when character profile discovery is unavailable. The selected partner is restored in the selector.
3. **Regression tests** (`tests/test_foresight_workbench_acceptance.py`): Added assertions guarding both integration contracts above.

## Verified results
- `node --check 2i/2i-assets/reach.js`: PASS.
- Focused writer/Reach acceptance tests: **15 passed**.
- Launcher, preflight, writer and acceptance checks: **20 passed**.
- Full targeted Foresight + Reach + 2i + Pub Partner + Alex memory suite: **76 passed** in 28 seconds; log in `agent_evidence/continued_full_regression.log`.
- Internal Reach preflight: **PASS**; log in `agent_evidence/continued_preflight.log`.

## Critical outstanding acceptance gates
- Real browser operation of Counter menus, tray movement, opening 2i and Pub Partner.
- Real browser manuscript write, save, restart, and reopen.
- Live provider-backed Pub Partner send/receive; no synthetic replies should be counted as success.
- Fresh Windows machine installation and launcher verification.

The sandbox's Chromium has previously reported `ERR_BLOCKED_BY_ADMINISTRATOR` for localhost navigation. Internal FastAPI preflight is not a replacement for browser testing.

## Next pass
1. Run the extracted ZIP on a browser-capable host, ideally through GitHub-connected integration environment or user hardware.
2. Exercise full first-session workflow and repair actual failures.
3. Only after live interaction succeeds, mark the workbench as first-use ready.

## Start
Extract the ZIP, open `october/`, and run `OPEN_REACH_WINDOWS.bat` on Windows. On other systems with Python 3.11+ and installed requirements, run `python run_reach.py` from `october/`. User data is stored under `reach_userdata/`; do not delete it when updating builds.
