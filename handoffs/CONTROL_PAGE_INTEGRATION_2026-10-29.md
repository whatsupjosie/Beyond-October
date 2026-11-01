# Control page: working Vision Mixer, key assignment, camera operator station, 2026-10-29, Claude

## Reason

Josie, 2026-10-29: integrate the camera controls and the hotkey map into the program, wired in everywhere it is appropriate and useful, with the console controls. Reading the Control page (`/control`, `static/control.html`) first showed that the Vision Mixer on it was mostly dead: the Cut and Fade buttons and the source list had no code behind them anywhere, the station tabs did not switch (nothing on that page loaded `control_stations.js`), and only a few keyboard shortcuts in `static/switcher.js` worked. So wiring keys meant making that panel work too.

## What changed

| Path | Change |
| --- | --- |
| `static/control_keys.js` (new) | The key map for the Control page: the switcher's controls (Cut, Fade, Preview 1 to 9, Program 1 to 9) and the camera station's. Keeps each person's choices on the host. "Assign keys": click it, click any control, it asks "Where would you like the Cut button?", the next key answers. The transparent keyboard shows while assigning and at the camera station. |
| `static/control_switcher.js` (new) | Makes the Vision Mixer work through `/api/switcher/*`: the source list (click = Preview), Cut, Fade (a dissolve over the Mix ms box), Preview and Program by key. The line under the buttons now reports the real keys. |
| `static/camera_station.js` (new) | A Camera tab on the stations bar. Pick a camera, aim and move it with held keys or the mouse, zoom and pull focus, record the move, name and save it, play it back exactly. Every key is assignable; a table of them is in the panel. |
| `static/control.html` | Loads the above, plus `control_stations.js` (the station tab switching it was written for). |
| `static/switcher.js`, `static/control_stations.js` | Their fixed key handlers step aside when the shared key map is present, so two handlers never fight over a key. Without it they behave as before. |
| `modules/cameras.py` | Cameras gain `focus` (metres); `update_pose` accepts it and the pose event carries it. |
| `modules/switcher_routes.py` | `POST /api/switcher/ptz/{id}` now needs the moderator role (when sign-in is enforced), checks every number before touching a camera, and takes focus; new `GET /api/switcher/pose/{id}`. |
| `modules/camera_moves.py` (new) | Saved camera moves per person under `data/camera_moves/`: list, save, read, delete, every recording checked. |
| `static/keymap.js`, `static/camera_rig.js` | A held control kind (keys held, any number at once, released on key up, blur, leaving the station, or reassignment); the arrow keys are reserved only at stations with a fader; the camera's controls are described once and the key map takes them from there. |
| `main.py` | Mounts the camera moves router. |

## Behaviour that changes on the Control page

- Space still cuts and F still fades, and now they work (Fade is a real dissolve).
- Enter and C no longer cut, and Shift plus a number no longer takes a camera to Program: the key map has no modifier combinations, so Program is Numpad 1 to 9 by default. All of these are assignable.
- The old page error "Identifier 'WSHub' has already been declared" was already there (`ws.js` is loaded by `base.html` and again by `control.html`). It is not fixed here: removing the second tag left `WSHub` undefined for another script, so it needs a proper look.

## Assumptions to confirm

- A camera's rotation is stored as [tilt, pan, roll] in degrees and position in metres, y up. The repo did not say. If the Rust renderer expects another order, only `toApi` and `fromApi` in `camera_station.js` change.
- The Rust mirror (`modules/rust_camera_runtime.py`) does not yet pass focus to the renderer.

## Tested (observed, Linux, Node 22, headless Chromium, the real app under uvicorn)

- `tests/test_control_page_end_to_end.py`, 3 tests: the Vision Mixer works by mouse and by key (preview, cut, program, fade); assigning a key asks the question, takes the answer, warns about a key already in use, is kept on the host and survives a reload; the camera station moves a real camera with held keys, records a move, saves it, plays it back from a fresh page to where it ended, a camera key assigned on the spot works, and returning to the Director tab hands the keys back.
- `tests/test_camera_moves.py`, 46 tests: moves round trip; bad names, shapes, NaN, oversize, too many samples refused with nothing written; the pose route sets position, rotation, zoom and focus together, refuses bad numbers without changing anything, needs the moderator role, and 404s for a missing camera.
- Node: held controls and the camera action table (keymap and rig tests).

## Not wired, and why

- `static/control_room.html` has the stations bar but not the Vision Mixer buttons, so only its own fixed keys remain there.
- `static/studio_control_room.html` is a separate surface with its own Space and Esc (start, emergency). Left alone: those are safety keys and mixing them into an assignable map needs a decision.
- The walkable studio's control room consoles (in `/walk`) are still "not wired yet"; opening a station there should call `PubCastKeymap.open(...)` so the walker stops. That needs the console art and your decision on what each console does.
- Camera lock-on, orbit and scripted shots are in the rig but have no controls in the station yet (they need a subject picker).
- Audio mixer and video editor stations have no key registrations yet.
