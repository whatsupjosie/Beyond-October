# Human profile checkpoint — 2026-11-05

RAN on Linux, Python 3.12.14, Chromium 141 / Playwright 1.56:

`PLAYWRIGHT_NODEJS_PATH=$(command -v node) .venv/bin/python -m pytest -q tests/test_human_profiles.py tests/test_human_profiles_browser.py tests/test_websocket_cookie_auth.py tests/test_three_solution_rounds_auth_foundation.py tests/test_production_notes.py --junitxml=../profiles-checkpoint.xml`

**25 passed, one deprecation warning, 15.04 seconds.** Full output and JUnit
are adjacent. This is focused profile/auth/notes validation, not a whole-codebase
debugging round.

Implemented additive SQLite migration preserving existing permanent IDs; private
optional fields; explicit per-field discovery; metadata-stripped bounded images;
revision-fenced updates; stable IDs returned by setup/login/verify; first-run
profile editor; a Me menu opening the existing singleton tray; drafts; and
click-to-load reels. Discovery explicitly covers this host, not a nonexistent
global directory. No media host is contacted merely to view a reel link.

Real-browser tests exercise phone layout, API persistence after reload, explicit
sharing and reel loading, and a restored stale draft refused after another window
updates the host. A first test attempt passed its assertions but reported a page
error: its injected authentication script also ran in the sandboxed external
reel frame. Restricted the test injection to the actual host origin, then reran;
no product permission was relaxed. Subsequent combined run above passed.

The restored environment lost its Python launcher and browser cache. Repaired
the virtualenv launcher against the installed Python and reinstalled Chromium.
Existing installed application dependencies remained available.

Still open: independently admitted guests, one-owner migration of legacy crew,
contacts/message requests, full profile onboarding browser acceptance, native
Windows/device checks, groups/schedules, targeted debugging and both post-feature
whole-codebase debugging rounds. Existing local crew fixtures are regression
coverage, not proof of the new guest model. No main merge, Actions or deployment.

## First-run browser follow-up

RAN `tests/test_human_profile_onboarding_browser.py` and
`tests/test_human_profiles_browser.py`: **four passed**, one deprecation warning,
14.23 seconds. Two independent fresh-install journeys use the actual login page,
choose private/discoverable, skip optional fields, retain the permanent ID and
return to the requested same-origin destination. Existing setup disappears once
the owner exists. This closes the earlier first-run browser gap, not guest or
hardware acceptance. Corrected the login fallback to keep the server-returned ID.
