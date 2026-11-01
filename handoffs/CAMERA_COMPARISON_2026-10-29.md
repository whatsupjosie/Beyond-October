# Camera rig compared with established virtual cameras, 2026-10-29, Claude

Compared with Unity's Cinemachine and Unreal Engine's Cine Camera Actor and camera rigs, whose documentation was read for this (links below), plus general knowledge of cinematography. Josie's note: white balance is far less important for a virtual camera, since there is no daylight to match.

## The comparison

| Capability | Cinemachine / Unreal | `camera_rig.js` now | Needed? |
| --- | --- | --- | --- |
| Position and aim in three axes | yes | yes | built |
| Roll (tilted horizon) | yes | added today (it was missing) | built |
| Smooth, damped movement ("heavy" camera) | damping per axis | smoothing time per channel | built, feel to be tuned |
| Look at / follow a subject | Look At, Follow; Unreal look-at tracking | lock on (C) | built |
| Dead zone and soft zone | Cinemachine composer: subject can move inside the dead zone without the camera turning; the soft zone eases it back | added today as `zone` on lock on | built |
| Lens in millimetres, real lens sizes | Unreal: lens presets, focal length, filmback | mm to field of view both ways, usual lenses 14 to 135 mm | built (helpers); a lens picker in a station is not |
| Depth of field from aperture and focus | Unreal: aperture, focal length, focus distance | the thin-lens blur formula, used by the try page | built (formula); not yet used by the renderer |
| Tracking focus (focus follows a subject) | Unreal: Tracking focus method | lock on sets focus from the subject's distance | built |
| Rack focus (timed focus pull) | yes, by keyframe | `pullFocus`, and focus is a channel of any shot | built |
| Moves on a path: rail, dolly, crane | Cinemachine dolly track and cart; Unreal rail and crane rigs | not built | yes, soon: tracking shots are common |
| Orbit / arc around a subject | Cinemachine orbital and free look | added today (`fromOrbit`) | built |
| Recording and exact repeat | Unreal Take Recorder and Sequencer; Cinemachine with Timeline | records the pose that resulted, replays exactly, any frame rate | built (in memory; saving to disk not done) |
| Blends and cuts between cameras | Cinemachine brain blends by priority, custom blend styles | the switcher cuts; timed blends between two cameras not built | later |
| Handheld shake | Cinemachine noise profiles, added separately from the move so the move is not disturbed | not built | optional, easy: add after the move, never into it |
| Keep out of walls and set pieces | Cinemachine confiner and collision | position limits only | yes, once the studio sets are solid |
| Frame guides: thirds, safe area, aspect ratio | Cinemachine Game view guides; Unreal filmback presets | the try page shows a centre box only | yes, small |
| Several cameras at once | many virtual cameras, one live | the switcher already has camera sources | exists |
| Shutter angle, motion blur | Unreal exposure: shutter speed | not built | a rendering matter, not a control |
| ISO, exposure | Unreal exposure settings | not built | low; a look choice |
| White balance | post process | not built | agreed: not needed |

## What this means

Nothing major is missing from controlling the camera. The two gaps that matter are moves on a path (rail, dolly, crane) and keeping the camera out of solid things. Frame guides are small and useful. Depth of field is ready as a formula but needs the renderer to apply it. Everything else is optional or a rendering concern.

One idea from both products worth keeping in mind: Cinemachine adds shake separately from the move, so a handheld look never changes where the camera actually is or what gets recorded. If shake is added here, it should be added the same way.

## Sources

- Unity Cinemachine manual, Using: https://docs.unity3d.com/Packages/com.unity.cinemachine@3.0/manual/CinemachineUsing.html
- Unity Cinemachine Aim Composer (dead zone, soft zone, damping): https://docs.unity3d.com/Packages/com.unity.cinemachine@2.2/manual/CinemachineAimComposer.html
- Unity Learn, Cinemachine Dolly Cart and Track: https://learn.unity.com/tutorial/-2cinemachine-dolly-cart-and-track-2018?version=2019.4
- Unreal Engine CinematicCamera API (rig crane, rig rail, lens, focus, filmback, look-at and tracking-focus settings): https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/CinematicCamera?application_version=5.4
- Unreal Engine 4.27, Cine Camera Actors (lens presets, focus methods, aperture): https://docs.unrealengine.com/4.27/AnimatingObjects/Sequencer/Cameras/CineCameraActors
