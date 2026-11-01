# Host control, server half, 2026-10-29, Claude

## Reason

Josie, 2026-10-29: build host control (possess, timeout, profile, gifts, tracker). Design is in `handoffs/HOST_CONTROL_SPEC_2026-10-29.md`. This is the first code for it: the server side, built on the existing governance engine and hub.

## What changed

| Path | Change |
| --- | --- |
| `modules/host_control.py` (new) | `HostControl` and the routes under `/api/host`. Possess and release (the existing avatar freeze, plus who is in control, a timer and an automatic release), drive (host clicks go to the possessed person only), timeout and end-timeout (teleport to the disciplinary side of the waiting room with recording on; ends by itself or by the host), profile (title, position, notes, tracked; the name can never change), privileges (`control_room`), gifts (control room access, accessory), and the tracker log (`data/people_log/<person>/<date>.md`, written only for tracked people). |
| `modules/pubworld_private.py` (new) | Private delivery to walker sockets. See "A finding" below. |
| `static/world_walk_live.js`, `static/world_walk.html` | The walker reacts to the host: the possession notice is shown as plain text exactly as sent, the person's own keys and clicks no longer walk while the host has control or they are in the waiting room, the host's drive moves the avatar, and release and the end of a timeout hand control back. A banner shows the title, the wording and the time left. |
| `main.py` | Imports; mounts the router next to governance; the walker socket handler registers a socket under its verified person (enforced handshake, or a valid in-band token) and removes it when it closes. |
| `tests/test_host_control.py`, `tests/test_pubworld_private.py`, `tests/test_host_control_end_to_end.py` (new) | 38, 4 and 6 tests. |

Rules built in:

- Reading (`state`, a profile, the tracker log) needs `mod`. Taking control, timeout, editing a profile, privileges and gifts need `admin` (the owner passes). Set by `CONTROL_ROLE` and `READ_ROLE`.
- No audit entry, no action: the governance audit entry is written first, and if it cannot be written the action is refused (503).
- Possession is undone, and the audit says so, if nobody verified received the notice (409 `target_not_connected`). It is also refused for someone already frozen by other means (409 `already_frozen`) and for a second possession of the same person in any letter case.
- A possession and a timeout each keep their own timer.

## A finding that shaped this (observed in the code)

The walker's socket (`/pubworld/ws/{client_id}` in `main.py`) is not in the Hub, so `Hub.send_private_event` reaches nobody there. The first version of this code would have refused every possession for that reason. Three ways to fix delivery were weighed: put the walker socket into the Hub (reuses existing delivery but changes shared Hub behaviour), give the walker socket its own per-person registry (smallest change, no extra data use), or have the walker poll an inbox (works anywhere but spends the limited data on constant polling and arrives late). The second was built. `HostControl` tries every channel it was given and counts a delivery on any.

## Josie's wording is not in the code

The possession notice and the timeout message are read from `data/host_control/messages.json` (keys `possession_notice` and `timeout_notice`) at the moment they are used. Possession refuses with 409 `possession_notice_not_set` until Josie has put her approved text there. Timeout still teleports without a message. The tests use made-up wording.

## Tested (observed, Linux, Python 3.13)

48 passed (`tests/test_host_control.py`, `tests/test_pubworld_private.py`, `tests/test_host_control_end_to_end.py`).

Unit and route level: every route refuses a viewer; moderators can read but not take control; the notice reaches the target only and the public mark carries none of its words; possession is undone when undelivered; an already frozen person is not taken over; letter case is one person; no audit entry means no action; a timeout ends by itself or by the host; separate timers; two possessions at once, only one wins; 300 rounds of hostile input on every route (odd ids, huge values, NaN and Infinity, bad JSON, path tricks) never cause a server error and write nothing outside the folders it owns.

End to end, through the real app (`main.app` under uvicorn, a throwaway data folder, auth enforced) with real walker sockets that prove who they are with a token: a possession reaches both tabs of the possessed person (any letter case) and not a third person; drive, timeout (with recording flag and the configured wording), end-timeout and release each arrive as the right event at the possessed person only; a person with no verified socket, a closed socket, a socket that sent no token and a socket with a wrong token cannot be possessed; viewer and moderator are refused and an admin may try, by the real app; the governance audit log holds POSSESS, RELEASE, TIMEOUT and TIMEOUT_END.

Regression: 15 tests in the websocket, route-authorization and walker-host files fail. The same 15 fail with this change removed (checked), so none are caused by it. The PubWorld socket connect tests pass.

## Added later the same day: roster, host panel, waiting-room screen, removal, reconnect

Reason: the host could only act by calling routes. Josie asked for the whole thing to be integrated: a list of who is on the walker, their stats and profile, the actions, and the disciplinary waiting room.

| Path | What changed |
|---|---|
| `static/world_walk_live.js` | Sends `presence` every 2 s while the socket is ready (`setPresence(fn)`), answers the host's `rtt_ping` with `rtt_pong`, passes `banned` on and stops reconnecting after it. |
| `static/world_walk_glb.js` | Counts triangles and bones when an avatar is loaded; `info()` and `load()` return them. |
| `static/world_walk.html` | Frame rate (smoothed), the presence snapshot, a full-screen `#screen` for the waiting room and for removal (the side panel is made inert behind it), and the Host panel. |
| `modules/pubworld_private.py` | Keeps one presence record per verified person (values cleaned and limited), round trip time, a roster (forgotten after 15 s of silence, or at once when the last socket closes), room-change callback, and a `pending_for` hook. |
| `modules/governance.py` | One added method, `active_bans()` (a read of the bans in force). Nothing else in the engine changed. |
| `modules/host_control.py` | `GET /api/host/roster` and `GET /api/host/bans` (mod), `pending_for(person)` (a possession or timeout still running), `on_room_change` (a tracked person's moves go in their day log). |
| `main.py` | Walker socket: `presence` and `rtt_pong` handling (verified sockets only, one probe per 5 s, a proved identity cannot be swapped), a banned person is refused at connect and put out within one message, a reloaded or reconnected page is re-sent the possession or timeout that is still running. |

What the Host panel does (on `/walk`, only when `GET /api/host/state` answers 200 for the session, so a moderator or above):

- Roster of everyone on the walker with initials (there are no portrait pictures anywhere in the project), room, who they walk as, and flags (under control, in the waiting room, logged). The list updates every 2 s without rebuilding what you are typing.
- Stats for the selected person: frame rate (0 with the note "page not drawing" for a hidden tab), round trip to the host, avatar complexity (meshes, bones, triangles measured from the file the page loaded, or "flat figure"), who they walk as, room, picture and spot, seconds since last heard.
- Profile: title, position, notes, daily log on or off, control-room privilege, gifts (control room access, an accessory by name). The name has no field because the host refuses to change a name.
- Control: reason, take control for N seconds, release, "walk them where I click" (only while you have them and are looking at the same picture they are in; it switches itself off otherwise, and your own avatar does not walk while it is on), waiting room for N seconds, end waiting room.
- Remove: Boot (`/api/governance/kick`, a session ban) and Ban for good (`/api/governance/ban`, permanent). Each needs a second click within 6 s. The reason field is sent and kept. Below the roster, "Out of the server" lists everyone currently out with the kind, the reason and a "Let back in" button (`/api/governance/unban`). By the engine's code a boot lasts until the app restarts or it is lifted, and a permanent ban is saved and reloaded at start (read, not run).
- Every error is printed as the host gave it. Known codes are turned into plain sentences.

Waiting room: the person's whole picture is replaced by a plain screen with the title "Waiting room", Josie's text from `messages.json` exactly as sent, and the time left. It is not a place in the world. While in it, presence reports the room id `waiting_room_disciplinary`, so the roster and the day log show where they are. Reloading the page does not free them (found by thinking it through, then built and tested).

Removal: a banned person who is connected gets `{"type":"banned","reason":...}` and the socket is closed (code 4403) on their next message (presence arrives every 2 s); a banned person who connects is refused at the door. The page shows "Removed from the server" and the reason the host typed, and does not try again. Those two title words and the "Waiting room" title are mine; every body text is the host's or Josie's.

### Tested for this part (observed, Linux, Python 3.13, headless Chromium)

- `tests/test_host_control.py` and `tests/test_pubworld_private.py`: 48 passed (new: the ban list is read-only for a moderator and refused to a viewer, expired bans are left out; a new page is told only what is still running, in any letter case).
- `tests/test_host_control_end_to_end.py`: 11 passed. New: a walker that reports in shows up on the roster with the numbers it sent, a round trip time after a real ping and pong, a wrong pong id changes nothing, a viewer can read the roster and a guest cannot, a closed socket leaves the roster at once; a page reloaded during a timeout or a possession is re-sent it with the same end time and wording, and is free once it is over; a banned person on a live socket is told the reason and cut off with code 4403, is refused when they come back, and leaves the roster; someone else is untouched.
- The same file, two real browsers (an owner and a guest): a guest never sees the panel; the owner's panel lists the guest and shows frame rate, round trip, "flat figure"; the guest loads the test mannequin and the roster shows its measured meshes, bones and triangles, then goes back to "flat figure" when it is cleared; profile edits and an accessory gift are on the host; taking control from the panel shows Josie-configured test wording on the guest, the guest stops walking, and the roster flags it; "walk them where I click" moves the guest to the clicked spot while the owner's own avatar stays put; release; the waiting room replaces the guest's picture, locks their keys, shows on the roster with the room id, survives a reload, and ends from the panel; Ban needs a second click, then the guest is shown the host's reason and stays offline for 5 s and leaves the roster; the ban shows under "Out of the server" with the reason, "Let back in" lifts it, and after a reload the guest is back on the roster; the audit log holds POSSESS, RELEASE, TIMEOUT and TIMEOUT_END against the guest; the day log of a tracked person is not empty; no page errors other than the known duplicate `WSHub` declaration on the Control page (not this page).
- Regression set run after the change: 167 passed across the walker, GLB, host integration, private delivery, host control, key map, Control page, camera moves and camera try, progress, restart, and websocket files; the key map (10) and camera rig (17) Node tests pass.

### Not tested

- Two real machines over a real network (all browsers and sockets were on one Linux machine).
- Windows and PowerShell 5; real graphics (the 3D count was measured in headless Chromium).
- Two hosts using the panel at once.
- A restart of the app with a ban in force (the engine's code says a permanent ban comes back and a boot does not; I did not run it). Possession and timeout state live in memory and end with a restart.
- With `PUBCAST_ENFORCE_AUTH` off (the local default) every visitor passes the role check, so the panel shows for everyone who opens `/walk`. That is how all role-gated routes behave when auth is off; real use needs it on.

## Not done, in this order

1. The waiting room as a place in the world (a picture and a floor): there is none, so it is a screen. Josie decides the look.
2. The panel as a tray in the Counter, following the tray art rules, and real portraits (nothing exists to show).
3. Voice chat with a person and alias search (see the spec).
4. Private instant messages from the host.
