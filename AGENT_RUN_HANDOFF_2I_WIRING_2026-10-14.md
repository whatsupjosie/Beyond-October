# PubCast + Foresight agent-run handoff — 2i integration repair

## Baseline and objective
Based on PubCast_Foresight_Agent_Checkpoint_Preflight_2026-10-14.zip. Objective: a first-use PubCast workbench with a functional 2i and Pub Partner embedded in Foresight. Original ZIPs untouched.

## Confirmed defects repaired
1. The `/writers-room` HTML did **not include** `/2i-assets/reach.js` or `reach.css`, even though these assets and backend routes existed. This meant the page used its older local-only document behavior and omitted the server-backed Reach integration. Added both to the actual page.
2. Reach runtime expected controls (`shelfBtn`, `partnerSelect`, `partnerNote`, `reachProvider`, `reachModel`, `reachCredential`, `reachBaseURL`) that were missing from the page. Added the actual controls.
3. The donor `getDocState`/`loadDocState` omitted the Reach partner conversation state. Added `partnerId`, `conversations`, and `conversationIds` to saved state and restored them on load.
4. Preflight previously checked only that pages/assets existed. It now checks that the writer page **loads** its runtime and has the required controls, and that runtime assets are served.
5. Added two regression tests in `tests/test_foresight_workbench_acceptance.py` to prevent missing runtime and lost conversation-state wiring from recurring.

## Evidence
- 44 selected Foresight/Reach/Writer's Room/launcher tests passed (see `agent_evidence/final_regression.log`).
- Expanded internal Reach preflight passed (see `agent_evidence/final_preflight.log`).
- These are code/API tests, **not** proof of a live browser manuscript round trip or live model reply.

## Remaining first-use gates
- Run actual browser in a compatible environment and confirm Counter menus/tray actions.
- Open 2i, type, save to Reach, restart, reopen, confirm text and partner conversation history.
- Open Pub Partner, configure a reachable provider, send a real message and receive a reply.
- Verify clean Windows installation and restart; test local provider availability.

## Next development priority
Live browser/end-to-end integration testing. Avoid spending time on nonblocking visual polish. The old Foresight route and original archives remain preserved.
