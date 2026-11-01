"""
pubcast_world.py — the connected PubCast world (rooms, views, exits, images)
==============================================================================
Rear View Foresight LLC · Feic Mo Chroí™

One manifest that ties every room image to the rooms around it. Geography is
Josie's, as told on 2026-10-18:

  monument ── parking_lot ── (Palace front door) ── lobby
  parking_lot ── (Vortex Bar front door) ── vortex_bar
  monument is the end of the world for now: no way out to the rest of Hollywood.
  lobby ── (bottom) ── palace_hallway (gold statue, right outside the theater)
  palace_hallway ── (stairs at the back, one bubble: Green Room first, then the
                     Writers' Room) ── green_room / writers_room
  lobby ── (walk off the right edge) ── lobby_upstairs ── projection_booth
  lobby_upstairs ── (walk off the left edge) ── lobby
  lobby_upstairs ── manager_office            (MANAGER door)
  green_room ── writers_room / studio / control_room / vortex_bar / dressing
  vortex_bar ── basement_bar (spiral stair; not drawn in the picture yet)

This file is topology: which rooms, which pictures, which exits lead where.
Where things stand inside each picture (floor, avatar size, door spots,
hotspots) is in data/world/placements.json, loaded by
pubcast_world_placement.py, in source-picture pixels like the Level Annotator
exports (data/hotspots/*.json). ``provisional`` here marks a link that was
inferred rather than stated, so nothing inferred passes as confirmed.

Design rule (Josie, 2026-10-18): every picture used as a background gets its
own avatar size, fitted once to that picture; see pubcast_world_placement.py.

Images are the originals, copied unaltered; ``sha256`` is checked by the tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

IMAGE_ROOT = "/static/world/rooms/"


@dataclass(frozen=True)
class View:
    """One picture of a room (a room may have several angles).

    Where things stand in the picture (floor, avatar scale, doors, hotspots)
    lives in data/world/placements.json, see pubcast_world_placement.py.
    """
    view_id: str
    image: str                 # file name under IMAGE_ROOT
    size: Tuple[int, int]      # (width, height) in pixels
    label: str = ""
    time_of_day: str = ""      # "", "day" or "night"


@dataclass(frozen=True)
class Exit:
    """A way out of a room.

    kind: door | stairs | gate | portal | edge-left | hotspot-view
    The door's spot in the picture is in placements.json, keyed by view and
    destination.
    """
    to: str
    label: str
    kind: str = "door"
    view: str = ""             # view_id the door sits in ("" = the room's main view)
    provisional: bool = False
    note: str = ""


@dataclass(frozen=True)
class WorldRoom:
    room_id: str
    name: str
    views: Tuple[View, ...]
    exits: Tuple[Exit, ...] = ()
    layout_id: str = ""        # id in pubcast_room_layout.ROOMS, if any
    live_id: str = ""          # id the running app uses (world.html / RoomManager), if any
    outdoors: bool = False
    locked: bool = False
    note: str = ""

    @property
    def main_view(self) -> View:
        return self.views[0]


def _v(view_id, image, w, h, label="", tod=""):
    return View(view_id, image, (w, h), label, tod)


WORLD: Dict[str, WorldRoom] = {r.room_id: r for r in (

    # ── OUTSIDE ──────────────────────────────────────────────────────────
    WorldRoom(
        "monument", "Monument Entrance",
        views=(
            _v("day", "monument_day.png", 1536, 1024, "Day", "day"),
            # Josie (2026-10-27): the monument should be in the daytime, so the three night views are dropped.
        ),
        exits=(Exit("parking_lot", "Back to the parking lot", "gate",
                    note="Josie (2026-10-18): you drive in along the roads at "
                         "the sides and off into the distance behind the "
                         "monument; once you are back there a hotspot takes "
                         "you back to the parking lot. This is the end of the "
                         "world for now: no way out to the rest of Hollywood."),),
        layout_id="monument",
        outdoors=True,
    ),
    WorldRoom(
        "parking_lot", "Parking Lot",
        views=(_v("main", "parking_lot.png", 1536, 1024, "Aerial"),),
        exits=(
            Exit("monument", "To the monument", "gate"),
            Exit("lobby", "Palace Theater front door", "door"),
            Exit("vortex_bar", "Vortex Bar front door", "door",
                 note="Josie (2026-10-18): the door of the Vortex Bar, right "
                      "in front of the car in the middle of the three parked "
                      "there."),
        ),
        layout_id="parking_lot",
        outdoors=True,
    ),

    # ── PALACE THEATER, GROUND FLOOR ─────────────────────────────────────
    WorldRoom(
        "lobby", "Palace Theater Lobby",
        views=(_v("main", "lobby.jpg", 1024, 565, "Rounded lobby"),),
        exits=(
            Exit("parking_lot", "Front door", "door",
                 note="The door in the back of the lobby image."),
            Exit("palace_hallway", "To the theater hallway", "door",
                 note="The very bottom of the lobby image."),
            Exit("lobby_upstairs", "Upstairs", "stairs",
                 note="Josie (2026-10-18): off to the right; it leads upstairs "
                      "to the second floor."),
        ),
        layout_id="lobby",
        live_id="lobby",
    ),
    WorldRoom(
        "palace_hallway", "Palace Theater Hallway",
        views=(_v("main", "palace_hallway.jpg", 1408, 768,
                  "Gold statue, outside the theater"),),
        exits=(
            Exit("lobby", "Back to the lobby", "door",
                 note="Josie (2026-10-18): the bottom of the screen leads back "
                      "to the lobby."),
            Exit("palace_theater", "Into the theater", "door", provisional=True,
                 note="Parked. Josie (2026-10-18): no Palace Theater image yet "
                      "and she does not know if or when it will be used, so "
                      "this hotspot is not to be worried about now. Locked "
                      "until the story is earned."),
            Exit("green_room", "Stairs up to the Green Room", "stairs",
                 note="Josie (2026-10-18): at the very back the character walks "
                      "up the stairs and, going left off screen, gets two "
                      "choices. Green Room is listed first because almost "
                      "everybody picks it almost every time."),
            Exit("writers_room", "Stairs up to the Writers' Room", "stairs",
                 note="The second choice in the same bubble as the Green Room."),
        ),
        layout_id="hallway",
        live_id="hallway",
    ),
    WorldRoom(
        "palace_theater", "Palace Theater Auditorium",
        views=(),   # no picture yet; only seen through the office window
        exits=(Exit("palace_hallway", "Out to the hallway", "door"),),
        layout_id="palace_theater",
        live_id="palace_theater",
        locked=True,
        note="No image of its own yet, and none needed soon: in the story the "
             "theater is still busted up. Seen from the manager's office "
             "window and the projection booth window.",
    ),

    # ── PALACE THEATER, UPSTAIRS ─────────────────────────────────────────
    WorldRoom(
        "lobby_upstairs", "Upstairs Lobby",
        views=(_v("main", "lobby_upstairs.png", 1536, 1024,
                  "Second-floor view of the lobby"),),
        exits=(
            Exit("lobby", "Down to the lobby", "stairs",
                 note="Josie (2026-10-18): walking left out of frame takes you "
                      "back downstairs to the main lobby."),
            Exit("manager_office", "MANAGER door", "door", view="main",
                 note="The door marked MANAGER in the picture (Josie, "
                      "2026-10-18: right)."),
            Exit("projection_booth", "To the projection booth", "door",
                 view="main",
                 note="The smaller door beside the MANAGER door (Josie, "
                      "2026-10-18: right, it is the projection booth)."),
        ),
        layout_id="lobby_upstairs",
    ),
    WorldRoom(
        "manager_office", "Sir Purfluous's Office",
        views=(_v("main", "manager_office.png", 1536, 1024,
                  "Theater manager's office"),),
        exits=(Exit("lobby_upstairs", "Out to the upstairs lobby", "door",
                    note="Josie (2026-10-18): the entrance and exit is a "
                         "hotspot at the bottom of the screen."),),
        layout_id="manager_office",
        note="Window looks down on the Palace auditorium and stage. Josie "
             "(2026-10-18): the back door leads into the back of the theater's "
             "mezzanine, up on the second floor; not built, so no exit yet.",
    ),
    WorldRoom(
        "projection_booth", "Projection Booth",
        views=(_v("main", "projection_booth.png", 1536, 1024),),
        exits=(Exit("lobby_upstairs", "Out to the upstairs lobby", "door",
                    provisional=True,
                    note="Not placed: this picture has no floor or door."),),
        layout_id="projection_booth",
        note="One booth only; the second projection room is dropped.",
    ),

    # ── THE HUB ──────────────────────────────────────────────────────────
    WorldRoom(
        "green_room", "Green Room",
        views=(_v("main", "green_room.jpg", 1586, 672, "Hub, drawn map overlay"),),
        exits=(
            Exit("palace_hallway", "Palace Hall (the theater lobby hallway)", "stairs",
                 note="One bubble with two choices: the Writers' Room or the Palace Hall. "
                      "The theater itself, off that hall, is locked until it is built."),
            Exit("writers_room", "Writers' Room", "door",
                 note="Same bubble as the Palace Hall: two choices, one door."),
            Exit("control_room", "Control Room", "door"),
            Exit("studio_overlook", "Studio", "door",
                 note="Opens on the far shot of the studio, not on PubWorld."),
            Exit("dressing_room", "Dressing Room", "door"),
            Exit("vortex_bar", "Vortex Bar", "door",
                 note="Authored 14 px below the 672 px image edge; treat as "
                      "the bottom edge."),
        ),
        layout_id="green_room",
        live_id="greenroom",
    ),

    # ── DRESSING ROOM (one room, many angles) ────────────────────────────
    WorldRoom(
        "dressing_room", "Dressing Room",
        views=(
            _v("wide", "dressing_wide.png", 1536, 1024, "Wide"),
            _v("typewriter_sitting", "dressing_typewriter_sitting.png", 1536, 1024,
               "Sitting at the typewriter"),
            _v("typewriter_standing_above", "dressing_typewriter_standing_above.jpg",
               687, 1024, "Standing, looking down at the typewriter"),
            _v("makeup_mirror", "dressing_makeup_mirror.png", 1536, 1024,
               "Makeup mirror"),
            _v("corkboard", "dressing_corkboard.png", 1536, 1024, "Message board"),
        ),
        exits=(
            Exit("green_room", "Door to the Green Room", "door", view="wide"),
            Exit("avatar_foundry", "Avatar Foundry", "hotspot-view", view="wide",
                 note="The wood stage before the full-length mirror: the "
                      "avatar maker program. No close-up picture yet."),
        ),
        layout_id="dressing_room",
        live_id="dressing",
    ),
    WorldRoom(
        "avatar_foundry", "Avatar Foundry",
        views=(),
        exits=(Exit("dressing_room", "Back to the Dressing Room", "hotspot-view"),),
        note="Program, not a room: opens the avatar maker over the wide "
             "dressing room view.",
    ),

    # ── STUDIO WING (off the Green Room) ─────────────────────────────────
    WorldRoom(
        "writers_room", "Writers' Room",
        views=(_v("main", "writers_room.jpg", 1024, 1024),),
        exits=(
            Exit("green_room", "Back to the Green Room", "door",
                 note="Josie (2026-10-18): just the one door in and out."),
            Exit("palace_hallway", "Out to the Palace Hall", "door",
                 provisional=True,
                 note="My inference, not hers: the Writers' Room can be entered "
                      "from the Green Room or from the hallway stairs, so the "
                      "one door offers both ways back. Green Room first."),
        ),
        layout_id="writers_room",
        live_id="writers",
    ),

    # The studio is three pictures walked in a line, then PubWorld:
    #   far shot -> (hotspot, walking up) -> closer crop -> (walk all the way
    #   left) -> director's chair -> (portal at the back) -> PubWorld.
    WorldRoom(
        "studio_overlook", "Studio, far shot",
        views=(_v("main", "studio_overlook.jpg", 1024, 1024,
                  "The open studio from far off"),),
        exits=(
            Exit("green_room", "Back to the Green Room", "door"),
            Exit("studio_fixedsets", "Walk up into the studio", "hotspot-view",
                 note="Triggered when the avatar walks up to a certain point; "
                      "the trigger spot is not placed yet."),
        ),
        layout_id="studio",
        live_id="studio_overlook",
    ),
    WorldRoom(
        "studio_fixedsets", "Studio, closer",
        views=(_v("main", "studio_fixedsets.png", 1024, 1024,
                  "Slightly closer crop of the same studio"),),
        exits=(
            Exit("studio_overlook", "Step back", "hotspot-view"),
            Exit("studio_director", "Wander off to the left", "edge-left",
                 note="All the way to the left edge of the picture."),
        ),
        layout_id="studio_floor",
        live_id="studio_fixedsets",
    ),
    WorldRoom(
        "studio_director", "Studio, director's chair",
        views=(_v("main", "studio_director.jpg", 1024, 768,
                  "Director's chair, toward the back of the studio"),),
        exits=(
            Exit("studio_fixedsets", "Back right", "edge-left"),
            Exit("pubworld", "Portal to PubWorld", "portal",
                 note="Toward the back of this picture. Josie will draw a "
                      "portal or a ghostly door there; not drawn or placed "
                      "yet."),
        ),
        layout_id="studio_director",
        live_id="studio_director",
    ),
    WorldRoom(
        "pubworld", "PubWorld",
        views=(),
        exits=(Exit("studio_director", "Back through the portal", "portal"),),
        layout_id="pubworld",
        note="Program, not a picture: PubWorld opens from the portal in the "
             "director's-chair view.",
    ),
    WorldRoom(
        "control_room", "Control Room",
        views=(_v("main", "control_room.jpg", 1024, 687),),
        exits=(Exit("green_room", "Back to the Green Room", "door"),),
        layout_id="control_room",
        live_id="controlroom",
    ),
    WorldRoom(
        "vortex_bar", "Vortex Bar",
        views=(_v("main", "vortex_bar.jpg", 1024, 1024),),
        exits=(
            Exit("green_room", "Back to the Green Room", "door",
                 note="Josie (2026-10-18): coming from the green room you enter "
                      "through the very back door, the back wall at the top "
                      "middle of the picture."),
            Exit("parking_lot", "Front door to the parking lot", "door",
                 note="Josie (2026-10-18): coming from the parking lot you "
                      "enter from the door on the left, behind the three "
                      "booths."),
            Exit("basement_bar", "Spiral stair down", "stairs",
                 note="Josie (2026-10-18): there should be a spiral staircase "
                      "leading down; the picture will be tweaked to show it, "
                      "so there is no click spot yet."),
        ),
        layout_id="bar",
        live_id="vortex",
        note="Old layout calls this 'bar' (The Pub). Same room unless Josie "
             "says otherwise.",
    ),
    WorldRoom(
        "basement_bar", "Basement Bar",
        views=(_v("main", "basement_bar.png", 1024, 1536),),
        exits=(Exit("vortex_bar", "Spiral stair up", "stairs"),),
    ),
)}

# Canonical heights, in inches (Josie, 2026-10-18). Keys are the ids in
# pubcast_room_layout.AVATAR_STYLES. A user's own avatar brings its own height.
CHARACTER_HEIGHT_IN: Dict[str, Optional[int]] = {
    "sir_purfluous": 74,   # 6'2"
    "pete": 68,            # 5'8"
    "repeat": 70,          # 5'10"
}

START_ROOM = "dressing_room"      # private spawn, per the layout rules


# ════════════════════════════════════════════════════════════════════════════
# QUERIES
# ════════════════════════════════════════════════════════════════════════════

def get_room(room_id: str) -> Optional[WorldRoom]:
    return WORLD.get(room_id)


def neighbours(room_id: str) -> List[str]:
    room = WORLD.get(room_id)
    return sorted({e.to for e in room.exits}) if room else []


def image_url(view: View) -> str:
    return IMAGE_ROOT + view.image


def shortest_path(src: str, dst: str) -> Optional[List[str]]:
    """Fewest-doors route, or None. Plain breadth-first search."""
    if src not in WORLD or dst not in WORLD:
        return None
    seen = {src: None}
    queue = [src]
    for cur in queue:
        if cur == dst:
            break
        for nxt in neighbours(cur):
            if nxt not in seen:
                seen[nxt] = cur
                queue.append(nxt)
    if dst not in seen:
        return None
    path, cur = [], dst
    while cur is not None:
        path.append(cur)
        cur = seen[cur]
    return path[::-1]


def validate_world() -> List[str]:
    """Problems with the manifest. Empty list means it is sound.

    Checks: every exit lands on a real room and is mirrored back; an exit's
    named view exists; every room can be reached from the start room.
    Positions inside pictures are checked by pubcast_world_placement.
    """
    issues: List[str] = []
    for rid, room in WORLD.items():
        if room.room_id != rid:
            issues.append(f"{rid}: key does not match room_id {room.room_id}")
        view_ids = [v.view_id for v in room.views]
        if len(view_ids) != len(set(view_ids)):
            issues.append(f"{rid}: duplicate view ids")
        for ex in room.exits:
            if ex.to not in WORLD:
                issues.append(f"{rid} -> {ex.to}: no such room")
                continue
            if rid not in neighbours(ex.to):
                issues.append(f"{rid} -> {ex.to}: {ex.to} has no way back")
            if ex.view and ex.view not in view_ids:
                issues.append(f"{rid} -> {ex.to}: exit view '{ex.view}' not found")
    if START_ROOM not in WORLD:
        issues.append(f"start room {START_ROOM} missing")
    else:
        reach = {START_ROOM}
        stack = [START_ROOM]
        while stack:
            for nxt in neighbours(stack.pop()):
                if nxt in WORLD and nxt not in reach:
                    reach.add(nxt)
                    stack.append(nxt)
        for rid in WORLD:
            if rid not in reach:
                issues.append(f"{rid}: unreachable from {START_ROOM}")
    return issues


def to_dict() -> dict:
    """JSON-ready form for an API endpoint or the viewer."""
    return {
        "start": START_ROOM,
        "image_root": IMAGE_ROOT,
        "character_height_in": dict(CHARACTER_HEIGHT_IN),
        "rooms": [
            {
                "id": r.room_id, "name": r.name, "outdoors": r.outdoors,
                "locked": r.locked, "layout_id": r.layout_id, "live_id": r.live_id,
                "note": r.note,
                "views": [
                    {"id": v.view_id, "image": image_url(v), "w": v.size[0],
                     "h": v.size[1], "label": v.label, "time": v.time_of_day}
                    for v in r.views
                ],
                "exits": [
                    {"to": e.to, "label": e.label, "kind": e.kind,
                     "view": e.view or (r.views[0].view_id if r.views else ""),
                     "provisional": e.provisional, "note": e.note}
                    for e in r.exits
                ],
            }
            for r in WORLD.values()
        ],
    }
