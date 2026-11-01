# Camera control modes: explored, 2026-10-29, Claude

## Reason

Josie, 2026-10-29: "Start experimenting with different modes of camera control." The AI has to be able to operate a camera as instructed; a person with only a keyboard and mouse must be able to move the camera, aim it, and adjust focus and zoom at the same time, cleanly and efficiently. Moves must be recordable and exactly repeatable (`CAMERA_MOVES_SPEC_2026-10-29.md`).

## What was built

| Path | What it is |
| --- | --- |
| `static/camera_rig.js` (new) | One camera pose (x, y, z, pan, tilt, zoom, focus) driven four ways, one smoothing stage, one recorder and player. Works in a browser and in Node. |
| `static/camera_try.html` (new) | A page to try each mode: a small set with a walking subject, a readout of the camera, a record and play back button. Soft focus shows when focus is off. |
| `tools/camera_experiment.js` (new) | Runs the four modes on the same job with a simple simulated operator (quarter-second late, decides ten times a second, a little noise, seeded). |
| `tests/test_camera_rig_node.js`, `tests/test_camera_try_browser.py` (new) | 16 node tests; 1 browser test. |

Nothing existing was changed.

## The four modes

- **A. Keys only.** Held key pairs for every channel at once (WASD move, Q and E down and up, arrows pan and tilt, brackets zoom, semicolon and quote focus).
- **B. Mouse aim + keys.** The mouse turns the camera (analogue, slow and fast both work), the wheel zooms, Shift and wheel pulls focus, keys move.
- **C. Lock on subject.** Aim and focus follow the subject by themselves. The operator only moves and zooms. An offset lets the operator hold the subject off centre.
- **D. Scripted shot.** A pose every second, eased between. This is how an AI operator or a saved move drives the camera.

Every mode produces wanted speeds for the same channels, and one smoothing stage (aim settles fast, bodies slower, limits stop a move without storing up speed) turns them into movement. The pose that results is what is recorded, so a take got by hand and one written by an AI are interchangeable.

## Result of the simulated experiment (20 runs each, same seeds)

| Mode | Framing off centre | Subject in the middle of the frame | Focus off | Pan shake | Things worked at once |
| --- | --- | --- | --- | --- | --- |
| A. keys only | 0.26 | 82% | 7.3% | 0.071 | 1.5 |
| B. mouse aim + keys | 0.15 | 100% | 7.6% | 0.002 | 1.7 |
| C. lock on subject | 0.02 | 100% | 1.5% | 0.009 | 0.2 |
| D. scripted shot (AI) | 0.01 | 100% | 0.4% | 0.006 | 0.0 |

How to read it, and what it does not say: the operator is a model, not a person. It says keys-only aim is steppy (a held key is a fixed speed, so the aim hunts around the subject and the shake is about 35 times the mouse's), that mouse aim is smooth and accurate but leaves focus entirely to the person, and that locking on takes aim and focus away from the person almost completely. It cannot say which feels best, and it uses one job only (a subject walking across, a slow push in). Try them in `static/camera_try.html`.

## Findings that matter for the next step

- A person with only a keyboard and mouse can work all seven channels together in B, at the price of capturing the mouse (pointer lock). A, held keys only, works without the mouse but aims coarsely.
- C is the natural way for one operator to hold a moving subject, and it is also what an AI does best. The two share one idea: say what to follow and let the rig do the aiming.
- Focus is the weakest channel by hand in every mode that leaves it to the person (about 7%). Following the subject's distance automatically (C and D) fixes it.

## Debugging pass and additions (later the same day)

Found and fixed: no roll channel; recording was sampled once per frame, so a slow laptop would record a stair-stepped move (integration and recording now run in slices of at most 1/120 s, so 12 and 144 frames a second give the same move); `setPose` accepted junk and ignored limits; a recording rate of NaN or 1e9 was accepted. Added: roll (`,` and `.`), dead zone and soft zone on lock on, orbit, rack focus, lens terms (millimetres, usual lenses, blur from aperture). The comparison with Cinemachine and Unreal is in `CAMERA_COMPARISON_2026-10-29.md`. The experiment was rerun after the changes and the table above is from that run.

## Tested (observed, Linux, Node 22, headless Chromium)

- Node: 16 passed (the 10 listed here, plus roll, frame-rate independence, junk handling, dead zone, orbit and rack focus, and lens terms). Several channels move at once; a held key settles to its speed and stops cleanly; moving follows where the camera points; pan turns the full 360 degrees and replays the short way across the wrap; limits stop a move without storing speed and junk input never corrupts the pose; projection matches the geometry; lock on keeps a moving subject framed and in focus; a scripted shot eases and ends exactly on its last pose; a recording replays exactly, also after saving and loading, and stores the pose that resulted, not the keys; mouse aim is analogue.
- Browser: 1 passed. The page draws, keys move aim and zoom together, lock on keeps the subject in the picture, a move recorded in one mode plays back in another and ends where it ended, the scripted shot runs, no page errors.
- The experiment is deterministic: the same seed gives the same result.

## Not done

- The rig's own key table is separate from `static/keymap.js`. The keymap map has buttons and faders; the camera needs its held-pair control kind, and the rig should take its keys from the map, so one question ("where would you like Pan left?") assigns them.
- Writing a move to disk and a list of saved moves (the format is in `CAMERA_MOVES_SPEC_2026-10-29.md`).
- Connecting the rig to the real cameras through `update_pose` in `modules/cameras.py`, to the take clock, and to a station that stops the walker.
- Feel: nobody has yet driven these by hand. Speeds, smoothing times and mouse sensitivity are first guesses.
- A person's camera input is not yet checked against anything; the AI's shot is not yet written by an AI.
