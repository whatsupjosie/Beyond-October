# PubCast/Foresight engineering checkpoint — 2026-10-14

## Objective
Get a first-use workbench into a safer, diagnosable state. Preserve the previous full source and all user data.

## Implemented in this checkpoint
- `tools/workbench_preflight.py`: read-only preflight that boots the actual FastAPI/Reach app via TestClient, checks all critical packaged Counter assets, validates `/foresight-counter`, `/writers-room`, `/pubpartner`, and `/pub-partner-chat`, checks program registrations, first-run bot defaults, and empty-start source behavior. Exits nonzero on failure and reports the failed check.
- `CHECK_WORKBENCH_WINDOWS.bat`: double-click diagnostic. Uses the existing Reach virtual environment, or calls the existing dependency installer in check-only mode before running the preflight. Leaves results visible.
- `tests/test_workbench_preflight.py`: regression test exercising the preflight as an independent process.

## Evidence
- Preflight executed successfully: `PREFLIGHT PASS` (full output retained outside the ZIP as run log).
- Focused regression: **25 passed** (`test_workbench_preflight`, `test_foresight_workbench_acceptance`, `test_foresight_front_door`, `test_foresight_chain`, `test_foresight_shapes`).
- Browser smoke attempted using installed Chromium and a local HTTP server; the environment returned `net::ERR_BLOCKED_BY_ADMINISTRATOR` for loopback. **No GUI pass claimed**.

## To use
1. Extract this ZIP fully.
2. Optionally double-click `CHECK_WORKBENCH_WINDOWS.bat` to check the install (first run may install Python dependencies and needs internet).
3. Double-click `OPEN_REACH_WINDOWS.bat` to start PubCast/Foresight.
4. In the blank Counter, File > Open; choose 2i or PubPartner. If something fails, retain `reach-startup.log` and the on-screen error.

## Still unverified
- Live tray dragging/resizing/locking in browser.
- 2i editing, saving and reopening from a real tray.
- Provider-backed PubPartner conversation from a real tray.
- Actual Windows installation and hardware environment.

This is a **preflight-enabled checkpoint**, not a claim of interactive certification.
