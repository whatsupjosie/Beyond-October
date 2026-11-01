# Camera operation and repeatable camera moves, spec, 2026-10-29, Claude

Status: DESIGN ONLY. Nothing here is built. "What exists" was read from the code, not run.

## Josie's words, 2026-10-29 21:28, exactly as she gave them (not edited)

> The exception to that might be the camera, because because with a camera you do have to move or truck or rally sometimes while you say zoom. That's conceivable, but that's a special case. Operating the video switcher, you will not be walking. Whereas operating the camera, by nature of having to operate the camera, you'll need to be able to control 360 degrees where the camera is pointing, and 360 degrees where the camera is moving simultaneously. With possibly, well, most definitely, a vertical consideration too. So we're going to need an X, Y, and Z axis controls for the cameras. And those movements have to be trackable. They have to be recordable, so they can be repeatable. Because if you get the perfect shot, even if it wasn't planned and kind of on accident, but you want to be able to repeat it, then the movement needs to be remembered so you can save it. So you can keep having that exact same camera move repeated over and over and over if you need more characters to react to the shot, or if you need something for special effects, or if you just need if you just want to make sure the camera is doing the exact right thing while you try to get the best take from a performer.

## How this is read (Josie to confirm)

- Sitting at a camera is a station like the video switcher: the person does not walk. What differs is that several controls act at once and are held, not tapped.
- The camera has seven things to control at the same time: where it points (pan, tilt, and roll if wanted), where it is (X sideways, Y up and down, Z forward and back), and zoom.
- Every move can be recorded as it happens, saved with a name, and played back exactly, as many times as needed, for other characters to react to, for effects, or to get a performer's best take against an identical shot.

## What already exists (read, not run)

- `modules/cameras.py`: each camera has `position` [x, y, z], `rotation` and `fov`, and `update_pose(source_id, position=, rotation=, fov=)` changes them and announces a `CameraPoseEvent`. So the pose a move needs is already there.
- `modules/cameras_advanced.py`, `camera_manager.py`, `camera_broadcast.py`: camera sources, roles and the switcher feed.
- The production lifecycle SLATE, READY, ACTION, CUT (see `handoffs/` and `pubcast-ai` notes) is the clock a take runs on.
- Not found: held multi-axis control from the keyboard, any recording of a camera's movement, or any playback of one. The notes list "FOLLOW_SUBJECT movement math missing" as open.

## Proposed design

1. Control kind "axis" in `static/keymap.js`. A button is tapped and a fader is selected then stepped. An axis is two keys, one for each direction, that act while held, each with its own speed. Any number of axes can be held at once, which gives pan, tilt, X, Y, Z and zoom together. The same "Where would you like the Pan left button?" question assigns them. The existing rules (no Esc, F5, F11, F12, Tab, arrows; warn on a taken key) apply unchanged. This is the one addition keymap.js needs and it is not built yet.
2. Movement per frame, not per key repeat: each frame, for every held axis, change that channel by speed times the time since the last frame, then call `update_pose`. Limits are clamped by the camera, so the pose that results is the pose that is recorded.
3. Recording stores the resulting pose, never the key presses. Sample the pose at a fixed rate (30 a second) against the take clock, with the start pose stored first. Replaying keys would not repeat a shot that was clamped, slowed or started elsewhere; replaying poses does.
4. A move is a small JSON file, one per move: name, camera, start pose, rate, samples of [time, x, y, z, pan, tilt, roll, fov]. Kept per person under `data/camera_moves/`, written the way studio progress is written (temp file then replace, revisioned, size capped).
5. Playback drives the same `update_pose` from the take clock, interpolating between samples (straight lines for position and zoom, spherical interpolation for aim so a full 360 turn is smooth), starting from the stored start pose. Same file, same take clock, same shot, every time.
6. Useful controls that follow from this: loop, speed (half to double), rewind to the start pose, trim, and record over one channel while the others replay (so the dolly can be kept while the pan is redone).

## Questions only Josie can answer

- Do you want a mouse drag or joystick for aiming as well as keys, or keys only?
- Should a recorded move be tied to one camera or usable on any?
- Should playback of a move lock the camera so the operator's keys are ignored, or can the operator nudge it while it plays?
- Is hand-held shake a thing you want recorded, or added on top of a clean move?
