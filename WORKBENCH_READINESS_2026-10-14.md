# PubCast Foresight — workbench readiness

## Objective
Launch PubCast into a blank Foresight Counter, then open actual 2i and PubPartner in trays to test their real backends. Visual polish and final tray physics tuning are explicitly deferred.

## Checks independently run on this packaged source
- `python -m pytest -q tests/test_foresight_*`: **49 passed**.
- Two tests were outdated: they asserted the former `/foresight` default and omitted the newly supported `foresight-legacy` option. Assertions were updated to match the current intended launch contract; no production logic was changed for these two tests.
- Inspected actual provider mappings: `twoi` -> `/writers-room`; `pubpartner_workspace` -> `/pubpartner`; `pubpartner_chat` -> `/pub-partner-chat`.
- Inspected server routes: `/writers-room` returns `2i/writers-room-v22.html`, `/pubpartner` returns `static/pubpartner.html`, `/foresight-counter` exists.
- The launcher uses loopback `127.0.0.1`, requires auth, owns the optional 2i sidecar lifecycle, and reserves the chosen port before opening the browser.
- Fresh Counter startup opens no trays; previously saved workspace restores unless `?fresh` is present.

## NOT independently certified
- Real browser interaction with menus and drag physics (browser loopback test blocked in previous attempts).
- Authentication first-run setup on Windows, dependency install on the target machine.
- A real manuscript edit/save/reopen in 2i; a real PubPartner send/receive.
- Performance under extended interactive use; optional backend and model availability.

## Launch
On Windows extract entire ZIP, then double-click `october/OPEN_REACH_WINDOWS.bat`. The first run may install dependencies. The server should open `http://127.0.0.1:8000/foresight-counter`. Keep the console open. The Counter may ask for first-run owner setup. To force a blank Counter without deleting saved data, navigate to `/foresight-counter?fresh`.

## Acceptance gate
1. Start with empty Counter and working menus.
2. Open 2i, type and save a manuscript, reopen and confirm content.
3. Open PubPartner, send a message, receive a real response, verify persistence.
4. Move, park, lock and restore both trays; restart and confirm workspace state.
5. Collect console and `reach-startup.log` for any failure, repair and rerun.

## Known limitations
Passing tests are not proof of a functional Windows installation. Do not label this build end-to-end certified until the above acceptance gate is exercised.
