# Bella Faux Pas Studio: the walkable world (2.5D)

Bella Faux Pas Studio is the game section of PubCast. A character walks through the room pictures. It walks on the drawn floor, routes round furniture, goes behind and in front of the cut-outs, and grows and shrinks with depth by each picture's own camera math.

Rebuilt on 2026-10-27 by replaying the 2026-10-18 to 2026-10-21 build session step by step. Nothing in it is approved except the parking lot walking path.

## Run it inside PubCast (Windows PowerShell 5)

From the repo root:

    python run_reach.py

Sign in when asked. The Counter opens empty. Click the **Bella Faux Pas** blade on the fan (right after **+ New**), or go to http://127.0.0.1:8000/walk (`/world-walk` also works). It is also in the Counter's Open picker as "Bella Faux Pas Studio". The studio starts in the dressing room.

Inside PubCast the walker is part of the same world as the classic PubWorld page (`/world`):

- **Presence:** it joins the same live socket (`/pubworld/ws`) and reports each room under the id the rest of PubCast uses (`dressing`, `greenroom`, `controlroom` and so on). The chip at the top says Connected, On air or Offline.
- **Room audio:** it raises the same `pubcast:room` event, so the room audio rules follow you. In the dressing room only director announcements play.
- **Hotspots:** the dressing room's typewriter, scripts, phone, wardrobe, hair and makeup, message board, the green room TV, and every couch, booth and stool run on the host through `/pubworld/api/hotspot`, the same as on `/world`. The control room consoles stay "not wired yet" until you decide what they do.
- **Hopping across:** "WALK THIS ROOM" on `/world` opens the walker in the room you are in. "Classic view" in the walker goes back the other way.
- **Starting room:** with nothing given it starts in the dressing room (`START_ROOM` in `modules/pubcast_world.py`). `/walk?live=greenroom` starts in a room by its PubCast id, and `/walk?view=writers_room/main` starts at a picture.

## Run it on its own, with no host

    python -m http.server 8000

Then open http://localhost:8000/static/world_walk.html. Walking, sizing, cans and 3D avatars all work. Hotspots say the host is not running, and the chip says Offline.

It must be served from the repo root, because the page loads `/static/...` paths. Opening the file straight from disk will not work.

## Controls

- **Click anywhere:** it walks there, routing round tables and chairs. If there is no route, it creeps round awkwardly and stops after 3 seconds of getting nowhere.
- **Arrow keys or WASD:** walk while held. Up goes away from you and down comes towards you. Shift walks faster.
- **Walk as:** choose Pete (68 in), RePete (70 in) or Purfluous (74 in).
- **3D avatar:** "Load a GLB..." (or drag a .glb onto the picture) sizes any rigged GLB to the chosen character height at every spot and plays its available walk/idle clips. The built-in demo buttons offer Xbot (Walk/Idle), MakeHuman female and male (Wave clips only; a procedural biped gait animates their Mixamo-standard legs while walking), and a Quaternius Husky (native quadruped Walk animation). The Husky is drawn **36 inches tall** rather than sized as a human. These bundled CC0 demos are session-only selections; they do not replace library avatars or persist their height overrides. The normal library picker and manual GLB import remain unchanged. "Hologram look" gives it a cyan glow.
- **Reference cans:** drop a 12 oz Coke can (4.83 in) on the picture and size it until it looks right. Tick "Size the avatars from my cans" and the avatars follow it.
- **Size tuner:** one slider makes everything bigger or smaller, and there are per-picture camera sliders. "Copy my changes" gives the numbers as JSON. Changes are kept in that browser only.

## Files

| Path | What it is |
| --- | --- |
| `static/world_walk.html` | the viewer (walking, routing, keys, cans, tuner) |
| `static/world_walk_glb.js` | the GLB avatar loader and renderer (three.js) |
| `static/world_walk_live.js` | the live link to the host: presence, room audio event, hotspot actions |
| `static/vendor/three-0.160.0/` | three.js 0.160.0, shared with the avatar import page, so it works offline |
| `static/world/world.json` | everything the viewer reads, built by `tools/build_world_json.py` |
| `static/world/rooms/` | the room pictures |
| `static/world/test_avatars/Xbot.glb` | the free test mannequin from the three.js examples |
| `modules/pubcast_world.py` | rooms, views (one per picture) and exits |
| `modules/pubcast_world_placement.py` | floors, stairs and ramps with altitude, cut-outs, blockers, camera math and validation |
| `data/world/placements.json` | the per-picture data, generated |
| `tools/world_src/` | the sources that generate `placements.json` |

## Camera and size math

Each picture has its own rule in `tools/world_src/calib_data.py`, and every number has its reason and references written next to it.

- **camera:** pixels per inch at a floor row = (row - horizon row) / eye height in inches.
- **samples:** a straight line through objects of known size (doors, tables, chairs, mugs) measured on that picture.

Confidence is marked per picture. These are still low confidence: lobby, lobby upstairs, studio fixed sets, writers' room, basement bar and monument day.

## Rebuild the data after an edit

    python tools/world_src/gen_placements.py
    python tools/build_world_json.py
    python tools/world_src/calib_proof.py writers_room/main

The first command rewrites `data/world/placements.json`. The second rewrites `static/world/world.json`. The third draws a proof sheet into `tools/world_src/proof_sheets/`. All three work from any folder.

## Tests

    python -m pytest tests/test_pubcast_world.py tests/test_pubcast_world_placement.py tests/test_pubcast_world_json.py tests/test_world_walk_browser.py tests/test_world_walk_glb_browser.py tests/test_world_walk_host_integration.py tests/test_bella_faux_pas_launch_acceptance.py

There are 134 tests. The browser ones need Playwright with Chromium. `test_world_walk_host_integration.py` boots the real `main.app` against a throwaway data folder and signs in as a first-run owner.

## Open questions (only Josie can answer)

- **Monument day:** the floor is two separate halves, left and right, with the reflecting pool between them, so you cannot walk from one side to the other. Should there be a way across?
- **Low-confidence pictures:** the sizes in the pictures listed above are estimates.
- **Approval:** no picture is approved as a whole yet.
- **Monument:** it is daytime only (Josie, 2026-10-27). The night views were removed.
