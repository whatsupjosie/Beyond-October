"""The connected PubCast world (modules/pubcast_world.py): graph soundness, Josie's stated geography, images on disk."""
import json
from pathlib import Path

import pytest

from modules import pubcast_room_layout as layout
from modules import pubcast_world as world

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "static" / "world" / "rooms"


def image_size(path: Path):
    """(width, height) read from the PNG or JPEG header, no imaging library needed."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = int.from_bytes(data[i + 2:i + 4], "big")
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
            i += 2 + length
    raise ValueError(f"not a PNG or JPEG: {path.name}")


def test_manifest_has_no_problems():
    assert world.validate_world() == []


def test_every_view_image_exists_with_the_declared_size():
    for room in world.WORLD.values():
        for view in room.views:
            path = IMAGES / view.image
            assert path.is_file(), f"{room.room_id}/{view.view_id}: {view.image} missing"
            assert image_size(path) == view.size, f"{view.image}: {image_size(path)} != {view.size}"


def test_no_two_views_share_an_image_file():
    names = [v.image for r in world.WORLD.values() for v in r.views]
    assert len(names) == len(set(names))


# ── Josie's geography, 2026-10-18 ──────────────────────────────────────────

@pytest.mark.parametrize("a,b", [
    ("parking_lot", "lobby"),            # Palace front door
    ("lobby", "palace_hallway"),         # bottom of the lobby image
    ("palace_hallway", "green_room"),    # stairs at the back
    ("lobby", "lobby_upstairs"),         # second-floor view
    ("lobby_upstairs", "projection_booth"),
    ("lobby_upstairs", "manager_office"),
    ("monument", "parking_lot"),
    ("parking_lot", "vortex_bar"),       # the Vortex Bar's front door (Josie, 2026-10-18)
    ("palace_hallway", "writers_room"),  # the second choice in the stairs bubble
    ("vortex_bar", "basement_bar"),      # the spiral staircase down
])
def test_stated_connections_exist_both_ways(a, b):
    assert b in world.neighbours(a)
    assert a in world.neighbours(b)


def test_the_monument_is_the_end_of_the_world_for_now():
    # Josie, 2026-10-18: you can go back into the parking lot, but not out into the rest of Hollywood
    assert world.neighbours("monument") == ["parking_lot"]


def test_only_what_was_inferred_is_still_marked_provisional():
    # everything Josie stated is not provisional; what is left was inferred or parked
    left = {(r.room_id, e.to) for r in world.WORLD.values() for e in r.exits if e.provisional}
    assert left == {
        ("palace_hallway", "palace_theater"),    # parked: no theater picture yet, her call if or when
        ("projection_booth", "lobby_upstairs"),  # this picture has no floor or door yet
        ("writers_room", "palace_hallway"),      # my inference: the same door offers both ways back
    }


def test_the_hallway_stairs_offer_the_green_room_before_the_writers_room():
    # Josie, 2026-10-18: Green Room first, because almost everybody picks it almost every time
    stairs = [e.to for e in world.get_room("palace_hallway").exits if e.kind == "stairs"]
    assert stairs == ["green_room", "writers_room"]


def test_the_green_room_is_not_a_door_off_the_lobby():
    assert "green_room" not in world.neighbours("lobby")
    assert world.shortest_path("lobby", "green_room") == ["lobby", "palace_hallway", "green_room"]


def test_one_projection_room_and_no_little_room():
    assert [r for r in world.WORLD if "projection" in r] == ["projection_booth"]
    assert "projection_booth" in world.neighbours("lobby_upstairs")


def test_pubworld_is_only_reached_through_the_studio_chain():
    # green room -> far shot -> closer crop -> director's chair -> PubWorld
    assert world.shortest_path("green_room", "pubworld") == [
        "green_room", "studio_overlook", "studio_fixedsets", "studio_director", "pubworld"]
    assert world.neighbours("pubworld") == ["studio_director"]
    assert "pubworld" not in world.neighbours("green_room")
    assert "studio_director" not in world.neighbours("green_room")
    assert "studio_director" not in world.neighbours("studio_overlook")


def test_studio_green_room_door_opens_on_the_far_shot():
    ex = [e for e in world.get_room("green_room").exits if e.to == "studio_overlook"]
    assert len(ex) == 1


def test_director_chair_is_reached_by_walking_left_from_the_closer_crop():
    ex = [e for e in world.get_room("studio_fixedsets").exits if e.to == "studio_director"]
    assert [e.kind for e in ex] == ["edge-left"]


def test_the_auditorium_hangs_off_the_hallway_and_starts_locked():
    theater = world.get_room("palace_theater")
    assert world.neighbours("palace_theater") == ["palace_hallway"]
    assert theater.locked


def test_dressing_room_keeps_every_angle():
    ids = {v.view_id for v in world.get_room("dressing_room").views}
    assert {"wide", "typewriter_sitting", "typewriter_standing_above",
            "makeup_mirror", "corkboard"} <= ids


def test_monument_is_daytime_only():
    # Josie (2026-10-27): "I want that picture to be in the daytime anyway"
    times = {v.time_of_day for v in world.get_room("monument").views}
    assert times == {"day"}


def test_start_room_reaches_everything():
    for rid in world.WORLD:
        assert world.shortest_path(world.START_ROOM, rid) is not None, rid


# ── the older layout module agrees ─────────────────────────────────────────

def test_layout_graph_is_still_sound():
    assert layout.validate_room_graph() == []


def test_layout_and_world_agree_on_every_shared_connection():
    to_layout = {r.room_id: r.layout_id for r in world.WORLD.values() if r.layout_id}
    from_layout = {v: k for k, v in to_layout.items()}
    for rid, lid in to_layout.items():
        want = {to_layout[n] for n in world.neighbours(rid) if n in to_layout}
        have = {n for n in layout.get_connections(lid) if n in from_layout}
        assert want == have, f"{rid}: world {sorted(want)} vs layout {sorted(have)}"


def test_to_dict_is_json_and_complete():
    d = json.loads(json.dumps(world.to_dict()))
    assert d["start"] == world.START_ROOM
    assert {r["id"] for r in d["rooms"]} == set(world.WORLD)
    dressing = next(r for r in d["rooms"] if r["id"] == "dressing_room")
    assert all(v["image"].startswith("/static/world/rooms/") for v in dressing["views"])


# ── the running app's ids ──────────────────────────────────────────────────

def test_live_ids_match_the_running_app():
    """world.html's ROOMS and the server's RoomManager use these ids."""
    import re
    html = (ROOT / "static" / "world.html").read_text(encoding="utf-8")
    live_html = set(re.findall(r"^  (\w+): \{\s*$", html, flags=re.M))
    from modules.rooms import RoomManager
    live_server = {rid for rid, _ in RoomManager.DEFAULT_ROOMS}
    for r in world.WORLD.values():
        if r.live_id:
            assert r.live_id in live_server, (r.room_id, r.live_id)
    for rid in ("studio_overlook", "studio_fixedsets", "studio_director", "lobby", "hallway"):
        assert rid in live_html and rid in live_server


def test_canonical_heights():
    assert world.CHARACTER_HEIGHT_IN == {"sir_purfluous": 74, "pete": 68, "repeat": 70}
    assert world.CHARACTER_HEIGHT_IN["sir_purfluous"] == 6 * 12 + 2
    assert world.CHARACTER_HEIGHT_IN["pete"] == 5 * 12 + 8
    assert world.CHARACTER_HEIGHT_IN["repeat"] == 5 * 12 + 10
    assert set(world.CHARACTER_HEIGHT_IN) <= set(layout.AVATAR_STYLES)


def test_to_dict_exports_heights():
    d = world.to_dict()
    assert d["character_height_in"] == {"sir_purfluous": 74, "pete": 68, "repeat": 70}
