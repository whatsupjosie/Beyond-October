# PubCast / Foresight — continuous engineering follow-up

## Objective
Get PubCast to a genuinely usable Foresight workbench, including 2i manuscript persistence and Pub Partner messaging. This build is a checkpoint, **not** certified end-to-end usability.

## Changes this pass
- Inspected actual 2i `reach.js` save, recovery, manuscript switching, conversation state, authentication, and API behavior; reviewed the live Pub Partner page and Foresight program registry.
- Corrected 2i manuscript shelf behavior when Reach's document-list API is unreachable. Previously a caught exception silently presented an empty shelf as though no manuscripts existed. Now it displays a visible server-unavailable warning, retains browser recovery copies, and advises reconnecting before assuming manuscripts are missing.
- Added regression coverage to `tests/test_foresight_workbench_acceptance.py` for the unavailable-server shelf state.
- Ran a focused backend/integration/physics suite: **42 passed**. Log: `agent_evidence/followup_regression.log`.
- Ran packaged internal Reach preflight: **PASS**. Log: `agent_evidence/followup_preflight.log`.
- JavaScript syntax check: `node --check 2i/2i-assets/reach.js` passed.

## Browser-test obstacle, verified
Chromium exists at `/usr/bin/chromium`, but Chromium navigation to local `127.0.0.1` fails with `net::ERR_BLOCKED_BY_ADMINISTRATOR`. Even an attempted in-process Playwright route intercept could not bypass this policy. This is a sandbox restriction, **not** evidence of a failed application. No actual GUI acceptance or live provider response is claimed.

## Critical outstanding gates
1. In a browser with normal local-network access, start Reach and confirm empty Counter, picker, tray gestures, opening actual 2i and Pub Partner.
2. Create/edit/save/reload a 2i manuscript through the browser. Test browser recovery after simulated Reach disconnect.
3. Configure a real reachable provider and exchange a Pub Partner message; check auth, response, and conversation persistence.
4. Verify clean-install Windows launcher and restart with actual user hardware.

## Integrity and scope
Original archives preserved. No placeholder AI responses added. No existing bot configs overwritten. The user requested one consolidated handoff instead of per-bug announcements.
