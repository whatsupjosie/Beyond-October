# Bella Faux Pas Studio (walkable world) integrated into October-24, 2026-10-27, Claude

## Reason

Josie, 2026-10-27, asked for the world maps to be integrated into the October-24 repo and for these to work:

- It starts up and opens on blank trays.
- You can open 2i and PubPartner.
- You can open the Bella Faux Pas Studio, which starts in the dressing room.

Bella Faux Pas Studio is her name for the game section of PubCast. She also asked for it to get its own fan blade.

## Provenance

- **World model, camera math, viewer, GLB walker:** rebuilt by replaying the 2026-10-18 to 2026-10-21 session "Startup options and first boot setup" step by step on October `b44db35`. Published in `whatsupjosie/October`, first on branch `world-walk-rebuild`, then integrated there on `world-walk-on-prime`. The files here are copied from that commit (`1d9f48f`).
- **October-24 files that matched exactly:** these were byte-identical to the October versions the edits were made on, so the edited versions were copied over unchanged:
  - `modules/pubcast_room_layout.py`
  - `static/foresight.html`
  - `static/foresight_programs.js`
  - `static/launch.html`
  - `static/world.html`
  - the four registry tests
- **October-24 files that differed:** `main.py` and `.gitignore`, so the same small edits were applied to October-24's own versions.
- **three.js:** this repo's own copy at `static/vendor/three-0.160.0` is used, not a second copy. Its `build/three.module.js`, `GLTFLoader.js` and `BufferGeometryUtils.js` are byte-identical to npm `three@0.160.0`. The one missing file, `examples/jsm/utils/SkeletonUtils.js`, was added from that same release and recorded in its `PROVENANCE.json` with its SHA-256.

## What changed

| Path | Change |
| --- | --- |
| `main.py` | `/walk` and `/world-walk` serve the studio (`static/world_walk.html`). |
| `static/world_walk.html`, `static/world_walk_glb.js`, `static/world_walk_live.js`, `static/world/` | The studio:<br>• it walks each picture's floor at its own camera scale<br>• GLB avatars<br>• the live link to the host: presence over `/pubworld/ws` by live room id, the `pubcast:room` audio event, and hotspots through `/pubworld/api/hotspot`<br>• with nothing given it starts at the world's start room, the dressing room. Before this it opened on the first room in the list (the monument) and ignored `start`.<br>• its title is "Bella Faux Pas Studio" |
| `static/foresight_programs.js` | Counter program `bella_faux_pas`, "Bella Faux Pas Studio", in Programs next to 2i and PubPartner, at `/walk`. |
| `static/foresight_counter.js` | New `opt.blades = [{label, run}]` option: fixed blades right after New. Tray blades follow them, and all blade indexing goes through `NF` (the number of fixed blades). With no `opt.blades` it behaves exactly as before. |
| `static/foresight_counter.html` | Passes `blades: [{label: 'Bella Faux Pas', run: () => programs.open('bella_faux_pas')}]`. Also loads `foresight_canvas2d.js` and falls back to it when WebGL2 fails (see below). |
| `static/foresight.html`, `static/launch.html`, `static/world.html` | Legacy Foresight entry; launcher "Bella Faux Pas" pill; "WALK THIS ROOM" on `/world`, which opens the studio at the room you are in. |
| `modules/pubcast_world.py`, `modules/pubcast_world_placement.py`, `data/world/`, `tools/build_world_json.py`, `tools/world_src/` | World model, floors, cut-outs, per-picture camera math, generators. |
| `tests/…` | 121 world tests, 12 host integration tests, 1 launch acceptance test, and the repo's page/route registries. |

## A fix found on the way: the Canvas 2D fallback was not wired in

`STATUS.md` lists a Canvas 2D fallback for machines without WebGL2. But `static/foresight_counter.html` never loaded `foresight_canvas2d.js`, and on a WebGL failure it showed "could not start its graphics renderer" and stopped. Only the test page in `tests/test_foresight_airgapped_ui.py` loaded the fallback. Now the real page:

- tries the HDR renderer first, exactly as before
- falls back to `ForesightCanvas2D` when that fails, with a plain notice
- shows the original error only if both fail

`tests/test_bella_faux_pas_launch_acceptance.py` proves it: the browser there has 3D switched off.

## Tested (observed, Linux, Python 3.12)

- **Acceptance test:** `tests/test_bella_faux_pas_launch_acceptance.py`, 1 passed. It does the following:
  - starts with `run_reach.py`
  - signs in through `/login`
  - lands on the empty Counter, whose fan shows New and Bella Faux Pas
  - opens 2i and PubPartner from File › Open…
  - clicks the Bella Faux Pas blade, which opens the studio in a tray, in the dressing room, connected live
  - clicks it again, which brings the open studio forward instead of opening a second tray
  - finishes with no page errors
- **World, host and registry tests:** 274 passed.
- **Counter, Foresight and frame tests:** 102 passed, 17 failed. The same 17 fail on clean October-24 (`022d9ec`): 13 in `test_foresight_file_workspace.py` and 4 in `test_foresight_airgapped_ui.py`. These are the known Foresight browser tests.
- **Full suite:** compared against the clean October-24 baseline (1,798 passed, 15 failed, 2 errors, Python 3.12, 120 s limit per test). The result is in `STATUS.md`.

## Untested

- Windows / PowerShell 5 on Josie's laptop.
- The HDR (WebGL2) Counter with its animation loop on real graphics. Here it ran on the Canvas 2D fallback.
- Auth enforced (`PUBCAST_ENFORCE_AUTH`).
- Two people in one room. The host does not broadcast presence yet.

## Open (Josie decides)

- **Monument floor:** the two halves of the monument floor do not connect.
- **Control room consoles:** they are still "not wired yet".
- **Sizes still low confidence:** lobby, lobby upstairs, studio fixed sets, writers' room, basement bar, monument day.
