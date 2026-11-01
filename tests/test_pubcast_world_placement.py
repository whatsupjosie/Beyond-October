"""Placements (data/world/placements.json): floors, altitude, avatar scale, draw order, doors, hotspots."""
import copy
import json
import math
import re
from pathlib import Path

import pytest

from modules import pubcast_world as world
from modules import pubcast_world_placement as P

ROOT = Path(__file__).resolve().parents[1]
DATA = P.load()


def with_view(key, **changes):
    d = copy.deepcopy(DATA)
    d["views"][key].update(changes)
    return d


def test_shipped_placements_are_sound():
    assert P.validate() == []


def test_every_picture_has_an_entry_even_if_not_fitted():
    # the design rule: a picture cannot be added without a decision about its avatar size
    for r in world.WORLD.values():
        for v in r.views:
            assert P.view_key(r.room_id, v.view_id) in DATA["views"]
    d = copy.deepcopy(DATA)
    del d["views"]["lobby/main"]
    assert any("lobby/main" in m and "no placements entry" in m for m in P.validate(d))


def test_nothing_is_marked_approved_until_josie_approves():
    # statuses are 'proposed' for everything I placed; only her own annotator doors are 'confirmed'
    for key, v in DATA["views"].items():
        assert v["status"] == "proposed", key


def test_her_own_door_positions_are_kept_exactly():
    gr = {d["to"]: d for d in DATA["views"]["green_room/main"]["doors"]}
    assert gr["control_room"]["at"] == [1477, 297]
    assert gr["studio_overlook"]["at"] == [954, 220]
    assert gr["dressing_room"]["at"] == [5, 583]
    assert gr["palace_hallway"]["at"] == gr["writers_room"]["at"] == [343, 252]
    assert gr["palace_hallway"]["group"] == gr["writers_room"]["group"]
    assert all(d["status"] == "confirmed" for d in gr.values())
    dr = {d["to"]: d for d in DATA["views"]["dressing_room/wide"]["doors"]}
    assert dr["green_room"]["at"] == [951, 435] and dr["avatar_foundry"]["at"] == [486, 425]


# ── scale ───────────────────────────────────────────────────────────────────

def test_one_sample_is_flat_two_are_perspective():
    flat = [{"y": 500, "ppi": 4.0}]
    assert P.ppi_at(flat, 100) == P.ppi_at(flat, 900) == 4.0
    two = [{"y": 400, "ppi": 2.0}, {"y": 800, "ppi": 6.0}]
    assert P.ppi_at(two, 400) == pytest.approx(2.0)
    assert P.ppi_at(two, 600) == pytest.approx(4.0)
    assert P.ppi_at(two, 800) == pytest.approx(6.0)
    assert P.horizon_y(two) == pytest.approx(200.0)      # ppi would reach 0 at row 200
    assert P.ppi_at([], 500) is None


def test_each_character_is_drawn_at_their_own_height_in_one_room():
    s = [{"y": 500, "ppi": 5.0}]
    h = {k: P.avatar_pixel_height(s, v, 500) for k, v in world.CHARACTER_HEIGHT_IN.items()}
    assert h == {"sir_purfluous": 370.0, "pete": 340.0, "repeat": 350.0}
    assert h["sir_purfluous"] > h["repeat"] > h["pete"]


def test_unfitted_picture_returns_no_height_rather_than_a_guess():
    assert P.avatar_pixel_height([], 74, 500) is None


def _size(key):
    return next(x.size for r in world.WORLD.values() for x in r.views
                if P.view_key(r.room_id, x.view_id) == key)


def test_far_studio_shot_makes_avatars_small_and_green_room_makes_them_big():
    def frac(key, y):
        return P.avatar_height_px(DATA["views"][key], 74, y) / _size(key)[1]
    assert frac("studio_overlook/main", 650) < 0.12          # tiny figure in a giant hangar
    assert frac("green_room/main", 620) > 2 * frac("studio_overlook/main", 650)


def test_a_scale_that_overflows_or_vanishes_is_rejected():
    big = with_view("lobby/main", scale=[{"y": 400, "ppi": 20.0}])
    tiny = with_view("lobby/main", scale=[{"y": 400, "ppi": 0.05}])
    assert any("scale" in m for m in P.validate(big))
    assert any("scale" in m for m in P.validate(tiny))


def test_unfitted_pictures_are_listed():
    listed = set(P.unfitted_views())
    assert "projection_booth/main" in listed and "dressing_room/corkboard" in listed
    assert "green_room/main" not in listed


# ── altitude: stairs, ramps, levels ─────────────────────────────────────────

def test_stairs_climb_along_their_axis():
    z = {"id": "s", "kind": "stairs", "level": "main", "z_in": 0, "rise_in": -18,
         "axis": [[0, 0], [0, 100]], "points": [[0, 0], [50, 0], [50, 100], [0, 100]]}
    assert P.altitude_at(z, (10, 0)) == 0
    assert P.altitude_at(z, (10, 50)) == pytest.approx(-9)
    assert P.altitude_at(z, (10, 100)) == pytest.approx(-18)
    assert P.altitude_at(z, (10, 500)) == pytest.approx(-18)       # clamped past the end
    z["rise_in"] = None
    assert P.altitude_at(z, (10, 50)) is None                      # unknown stays unknown


def test_the_places_josie_named_have_marked_altitude_changes():
    kinds = {k: {z["kind"] for z in v["zones"]} for k, v in DATA["views"].items()}
    assert "stairs" in kinds["green_room/main"]                 # steps down into the sunken living room
    assert "stairs" in kinds["basement_bar/main"]               # spiral stair in the pit below the Vortex Bar
    assert "stairs" in kinds["palace_hallway/main"]             # stairs at the back, up to the green room
    assert "ramp" in kinds["parking_lot/main"]                  # the lot slopes: Vortex Bar lower than the Palace
    levels = {z["level"] for z in DATA["views"]["green_room/main"]["zones"]}
    assert levels == {"main", "sunken-living-room"}


def test_unknown_altitudes_are_asked_about_not_guessed():
    text = " ".join(P.unset_altitudes())
    assert "spiral-stairs" in text and "lot-slope" in text
    assert "vortex_bar" in text and "basement_bar" in text and "green_room" in text
    for key, v in DATA["views"].items():
        for z in v["zones"]:
            if z["kind"] != "floor" and not z.get("estimated"):
                assert z["rise_in"] is None, "I do not know these numbers"


def test_the_sunken_living_room_heights_are_my_estimate_and_say_so():
    assert len(P.estimated_altitudes()) == 2
    text = " ".join(P.estimated_altitudes())
    assert "sunken-living-room-steps" in text and "sunken-living-room'" in text and "estimate" in text
    assert P.open_questions()["altitudes_estimated_not_confirmed"] == P.estimated_altitudes()
    zs = {z["id"]: z for z in DATA["views"]["green_room/main"]["zones"]}
    assert zs["sunken-living-room"]["estimated"] and zs["sunken-living-room-steps"]["estimated"]
    assert not zs["main"].get("estimated")
    d = copy.deepcopy(DATA)
    d["views"]["green_room/main"]["zones"][3]["estimated"] = "yes"
    assert any("estimated must be true or false" in m for m in P.validate(d))


def test_a_level_change_without_steps_is_rejected():
    d = copy.deepcopy(DATA)
    d["views"]["lobby/main"]["zones"] = [
        {"id": "low", "kind": "floor", "level": "a", "z_in": 0, "points": [[300, 400], [500, 400], [500, 500], [300, 500]]},
        {"id": "high", "kind": "floor", "level": "b", "z_in": 20, "points": [[500, 400], [700, 400], [700, 500], [500, 500]]},
    ]
    assert any("no stairs or ramp" in m for m in P.validate(d))
    d["views"]["lobby/main"]["zones"][1]["z_in"] = 0
    assert not any("no stairs or ramp" in m for m in P.validate(d))


def test_stairs_must_say_how_far_they_climb_even_if_the_answer_is_null():
    d = copy.deepcopy(DATA)
    z = d["views"]["green_room/main"]["zones"][2]
    assert z["kind"] == "stairs"
    del z["rise_in"]
    assert any("rise_in" in m for m in P.validate(d))
    z["rise_in"] = None
    del z["axis"]
    assert any("axis" in m for m in P.validate(d))


def test_zone_at_prefers_steps_over_the_landing():
    zones = DATA["views"]["green_room/main"]["zones"]
    on_steps = P.zone_at(zones, (925, 400))
    assert on_steps["id"] == "sunken-living-room-steps"
    assert P.zone_at(zones, (5, 5)) is None


def test_zones_that_do_not_touch_are_reported():
    keys = [k for k, _ in P.unlinked_zones()]
    assert "monument/day" in keys                       # the two sides of the pool
    assert "green_room/main" not in keys                # the steps join the sunken living room to the back floor


# ── 2.5D draw order ─────────────────────────────────────────────────────────

def test_walking_behind_an_object_puts_it_in_front_of_you():
    couch = {"id": "c", "points": [[0, 0], [10, 0], [10, 10]], "base_y": 500}
    assert P.occluder_in_front(couch, 450) is True     # further back than the couch: covered by it
    assert P.occluder_in_front(couch, 500) is False    # level with its front: you are drawn over it
    assert P.occluder_in_front(couch, 560) is False    # in front of it


def test_foreground_objects_cover_everyone():
    door = {"id": "d", "points": [[0, 0], [10, 0], [10, 10]], "always": True}
    assert P.occluder_in_front(door, 0) and P.occluder_in_front(door, 10 ** 6)


def test_green_room_couch_tv_and_table_follow_that_rule():
    v = DATA["views"]["green_room/main"]
    behind_tv = {o["id"] for o in P.occluders_over(v, 470)}
    assert "tv" in behind_tv and "sofa-front" in behind_tv
    in_front = {o["id"] for o in P.occluders_over(v, 650)}
    assert "tv" not in in_front and "sofa-front" not in in_front
    assert "foreground-bust" in behind_tv and "foreground-bust" in in_front


def test_dressing_room_sofa_is_always_in_front():
    v = DATA["views"]["dressing_room/wide"]
    sofa = next(o for o in v["occluders"] if o["id"] == "sofa-foreground")
    assert sofa["always"] is True


def test_an_occluder_needs_exactly_one_depth_rule():
    for bad in ({}, {"always": True, "base_y": 100}):
        d = copy.deepcopy(DATA)
        o = {"id": "x", "label": "x", "points": [[10, 10], [50, 10], [50, 50]]}
        o.update(bad)
        d["views"]["lobby/main"]["occluders"] = [o]
        assert any("either always=true" in m for m in P.validate(d)), bad


def test_solid_footprints_block_walking():
    v = {"occluders": [{"id": "t", "points": [[0, 0], [9, 0], [9, 9]], "base_y": 9,
                        "footprint": [[100, 100], [200, 100], [200, 200], [100, 200]]}]}
    assert P.blocked_at(v, (150, 150)) and not P.blocked_at(v, (50, 50))


def test_outlines_do_not_cross_themselves_and_stay_in_the_picture():
    d = copy.deepcopy(DATA)
    d["views"]["lobby/main"]["occluders"] = [{"id": "x", "label": "x", "base_y": 10,
                                              "points": [[0, 0], [100, 100], [100, 0], [0, 60]]}]
    assert any("crosses itself" in m for m in P.validate(d))
    d["views"]["lobby/main"]["occluders"][0]["points"] = [[0, 0], [100, 100], [100, 0], [0, 100]]
    assert any("no area" in m for m in P.validate(d))           # a perfect bowtie cancels to zero area
    d["views"]["lobby/main"]["occluders"][0]["points"] = [[0, 0], [5000, 0], [5000, 5000]]
    assert any("outside" in m for m in P.validate(d))


# ── doors, hotspots, geometry ───────────────────────────────────────────────

def test_doors_must_match_a_real_exit_in_that_picture():
    d = copy.deepcopy(DATA)
    d["views"]["lobby/main"]["doors"].append({"to": "basement_bar", "at": [10, 10], "r": 40, "status": "proposed"})
    assert any("no exit to 'basement_bar'" in m for m in P.validate(d))


def test_a_door_far_from_any_walkable_floor_is_rejected():
    d = copy.deepcopy(DATA)
    d["views"]["lobby/main"]["doors"][0]["at"] = [5, 5]
    assert any("from the walkable floor" in m for m in P.validate(d))


def test_unplaced_exits_are_listed():
    # Josie, 2026-10-18: the projection booth picture has no floor or door; the Vortex Bar picture has
    # no spiral staircase yet and will be tweaked to show one. Everything else has a spot.
    assert set(P.unplaced_exits()) == {("projection_booth/main", "lobby_upstairs"),
                                       ("vortex_bar/main", "basement_bar")}


def test_hotspots_that_open_views_point_at_real_views():
    d = copy.deepcopy(DATA)
    d["views"]["dressing_room/wide"]["hotspots"][0]["action"] = {"type": "view", "view": "nope"}
    assert any("unknown view" in m for m in P.validate(d))


def test_dressing_room_hotspots_chain_the_typewriter_views():
    wide = {h["id"]: h for h in DATA["views"]["dressing_room/wide"]["hotspots"]}
    assert wide["typewriter"]["action"]["view"] == "typewriter_standing_above"
    above = DATA["views"]["dressing_room/typewriter_standing_above"]["hotspots"][0]
    assert above["action"]["view"] == "typewriter_sitting"


def test_geometry_helpers():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert P.point_in_polygon((5, 5), sq) and P.point_in_polygon((10, 5), sq)
    assert not P.point_in_polygon((11, 5), sq)
    assert P.snap_to_floor([sq], (20, 5)) == (10.0, 5.0)
    far = [(30, 0), (40, 0), (40, 10), (30, 10)]
    assert P.polygon_distance(sq, far) == pytest.approx(20.0)
    assert P.polygon_distance(sq, [(5, 5), (15, 5), (15, 15), (5, 15)]) == 0
    assert P.polygon_self_intersects([(0, 0), (10, 10), (10, 0), (0, 10)])
    assert not P.polygon_self_intersects(sq)
    assert P.polygon_area(sq) == 100


def test_open_questions_covers_everything_waiting_on_josie():
    q = P.open_questions()
    assert set(q) == {"unapproved_pictures", "walking_paths_not_approved", "avatar_size_not_fitted",
                      "avatar_size_low_confidence", "avatar_size_references_disagree",
                      "climbs_the_pictures_already_imply", "doors_not_placed", "altitudes_not_known",
                      "altitudes_estimated_not_confirmed", "walkable_zones_that_do_not_touch"}
    assert len(q["unapproved_pictures"]) == len(DATA["views"])


def test_the_parking_lot_walking_path_is_the_only_approved_path():
    # Josie, 2026-10-18 16:37, on the parking lot sheet: "that's the area that you can walk in"
    with_paths = {k for k, v in DATA["views"].items() if v["zones"]}
    assert set(P.unapproved_paths()) == with_paths - {"parking_lot/main"}
    assert DATA["views"]["parking_lot/main"]["pad_status"] == "confirmed"
    # approving the walking path does not approve the picture: its size reading is still unanswered
    assert DATA["views"]["parking_lot/main"]["status"] == "proposed"
    assert "parking_lot/main" in P.open_questions()["unapproved_pictures"]
    assert "that's the area that you can walk in" in DATA["views"]["parking_lot/main"]["notes"]


def test_pad_status_must_be_proposed_or_confirmed():
    d = copy.deepcopy(DATA)
    d["views"]["lobby/main"]["pad_status"] = "approved"
    assert any("pad_status" in i for i in P.validate(d))
    d["views"]["lobby/main"]["pad_status"] = "confirmed"
    assert not any("pad_status" in i for i in P.validate(d))
    assert "lobby/main" not in P.unapproved_paths(d)


def test_merged_world_is_json_and_carries_everything_for_the_viewer():
    m = json.loads(json.dumps(P.merged_world()))
    gr = next(r for r in m["rooms"] if r["id"] == "green_room")
    v = gr["views"][0]
    for k in ("camera", "scale", "scale_info", "zones", "occluders", "doors", "hotspots", "status"):
        assert k in v
    assert v["camera"] == {"horizon_y": 180, "eye_in": 66}        # the green room's own camera
    assert m["elevations"]["lobby"] == 0 and m["elevations"]["vortex_bar"] is None


def test_writers_room_door_is_one_bubble_with_two_choices():
    # Josie, 2026-10-18: a bubble offers the Writers' Room or the Palace Hall (the theater lobby hallway)
    doors = [d for d in DATA["views"]["green_room/main"]["doors"] if d.get("group") == "hall_or_writers"]
    assert {d["to"] for d in doors} == {"writers_room", "palace_hallway"}
    assert len({tuple(d["at"]) for d in doors}) == 1            # one door spot, two choices
    assert {d["label"] for d in doors} == {"Writers' Room", "Palace Hall (theater lobby hallway)"}
    assert world.get_room("palace_theater").locked              # the theater itself is not built yet


# ── per-picture camera ──────────────────────────────────────────────────────

CAM = {"camera": {"horizon_y": 200, "eye_in": 60}}


def test_camera_size_grows_toward_the_lens_and_vanishes_at_the_horizon():
    assert P.ppi_for(CAM, 200) is None                         # at the horizon: no size
    assert P.ppi_for(CAM, 100) is None                         # above the horizon, level floor: no size
    assert P.ppi_for(CAM, 500) == pytest.approx(5.0)           # (500-200)/60
    assert P.ppi_for(CAM, 800) == pytest.approx(10.0)
    assert P.avatar_height_px(CAM, 70, 500) == pytest.approx(350.0)


def test_a_floor_below_the_main_floor_draws_smaller_and_a_higher_one_bigger():
    base = P.ppi_for(CAM, 500)
    assert P.ppi_for(CAM, 500, z=-24) < base                   # pit: camera is further above it
    assert P.ppi_for(CAM, 500, z=-24) == pytest.approx(300 / 84)
    assert P.ppi_for(CAM, 500, z=24) > base                    # platform: camera is closer to it
    assert P.ppi_for(CAM, 500, z=None) == base                 # unknown altitude is treated as the main floor


def test_a_floor_higher_than_the_camera_appears_above_the_horizon():
    # stairs climbing past eye level: rows above the horizon are valid for a floor higher than the camera
    assert P.ppi_for(CAM, 150, z=100) == pytest.approx((150 - 200) / (60 - 100))
    assert P.ppi_for(CAM, 150, z=100) > 0
    assert P.ppi_for(CAM, 150, z=30) is None                   # still below eye level: it cannot be up there
    assert P.ppi_for(CAM, 300, z=60) is None                   # exactly eye level: undefined, not infinite


def test_a_zone_scale_overrides_the_picture_camera():
    zone = {"scale": [{"y": 500, "ppi": 3.0}]}
    assert P.ppi_for(CAM, 500, zone=zone) == pytest.approx(3.0)
    assert P.ppi_for({}, 500) is None and P.avatar_height_px({}, 74, 500) is None


def test_samples_are_used_when_a_picture_has_no_camera():
    v = {"scale": [{"y": 400, "ppi": 2.0}, {"y": 800, "ppi": 6.0}]}
    assert P.ppi_for(v, 600) == pytest.approx(4.0)
    assert P.ppi_for(v, 100) is None                           # the line goes negative up there


def test_every_picture_with_a_floor_has_its_own_fitted_size():
    for key, v in DATA["views"].items():
        if v["zones"]:
            assert P.scale_known(v), f"{key} has walkable floor but no avatar size"
            assert bool(v.get("camera")) != bool(v.get("scale")), f"{key}: camera or samples, exactly one"
            assert v["scale_info"]["confidence"] in P.CONFIDENCE


def test_the_calibrated_cameras_are_the_ones_measured_this_session():
    cams = {k: (v["camera"]["horizon_y"], v["camera"]["eye_in"]) for k, v in DATA["views"].items() if v.get("camera")}
    assert cams == {
        "green_room/main": (180, 66), "dressing_room/wide": (346, 60), "palace_hallway/main": (350, 62),
        "manager_office/main": (313, 87), "lobby_upstairs/main": (278, 62), "control_room/main": (242, 75),
        "studio_overlook/main": (315, 232), "studio_fixedsets/main": (310, 240), "studio_director/main": (380, 62),
        "vortex_bar/main": (333, 83)}   # re-measured 2026-10-18 from the door and two stools
    sampled = {k for k, v in DATA["views"].items() if v.get("scale")}
    assert sampled == {"lobby/main", "writers_room/main", "basement_bar/main",
                       "parking_lot/main", "monument/day"}


def test_every_measurement_agrees_with_its_camera_and_is_written_in_the_refs():
    for key, v in DATA["views"].items():
        info = v.get("scale_info")
        if not info:
            continue
        text = " ".join(info["refs"])
        ints = {int(t) for t in re.findall(r"\b\d+\b", text)}
        spans = [(int(a), int(b)) for a, b in re.findall(r"\b(\d+)-(\d+)\b", text)]
        for m in info["measured"]:
            assert m["row"] in ints or any(a <= m["row"] <= b for a, b in spans), \
                f"{key}: row {m['row']} not in refs"
            assert any(t in text for t in (f"{m['ppi']:.2f}", f"{m['ppi']:.1f}", f"{m['ppi']:g}")), \
                f"{key}: {m['ppi']} px/in not in refs"
            if v.get("camera"):
                pred = P.ppi_for(v, m["row"])
                assert pred is not None and abs(pred - m["ppi"]) / m["ppi"] <= P.RESIDUAL_TOL, \
                    f"{key}: row {m['row']} measured {m['ppi']} but camera says {pred}"


def test_known_references_come_out_at_their_real_size():
    # Josie's rule of thumb: a doorway is 6.5 to 7 ft. The three green-room doors, measured at their own rows
    gr = DATA["views"]["green_room/main"]
    for row, door_px_per_in in ((305, 1.9), (370, 2.9), (420, 3.6)):
        assert P.avatar_height_px(gr, 80, row) == pytest.approx(80 * door_px_per_in, rel=0.06)
    # the studio director's cart is 36 in: the proof drew it at about 104 px
    assert P.avatar_height_px(DATA["views"]["studio_director/main"], 36, 562) == pytest.approx(104, rel=0.06)


def test_taller_characters_are_always_drawn_taller_in_every_fitted_picture():
    h = world.CHARACTER_HEIGHT_IN
    for key, v in DATA["views"].items():
        if not v["zones"]:
            continue
        ys = [p[1] for z in v["zones"] for p in z["points"]]
        y = sum(ys) / len(ys)
        px = {c: P.avatar_height_px(v, h[c], y) for c in h}
        assert all(px.values()), key
        assert px["sir_purfluous"] > px["repeat"] > px["pete"] > 0, key


def test_low_confidence_and_conflicting_pictures_are_listed_for_josie():
    q = P.open_questions()
    assert {"lobby/main", "writers_room/main", "basement_bar/main", "lobby_upstairs/main",
            "monument/day", "studio_fixedsets/main"} == set(q["avatar_size_low_confidence"])
    assert set(q["avatar_size_references_disagree"]) == {"monument/day"}
    for key in q["avatar_size_references_disagree"]:
        alt = DATA["views"][key]["scale_info"]["alt"]
        v = DATA["views"][key]
        row = {"monument/day": 578, "parking_lot/main": 775}[key]          # where the two readings part company
        mine, theirs = P.ppi_at(v["scale"], row), P.ppi_at(alt["samples"], row)
        assert abs(theirs - mine) / mine > 0.2


def test_the_hallway_stairs_are_on_the_back_wall_below_the_horizon_so_nothing_is_proven():
    # My first outline sat on the statue and reached above the horizon, which wrongly "proved" a climb
    # past eye height. Josie says the stairs are on the back wall; outlined there they stay below the
    # horizon, so the picture alone proves nothing about how far they climb.
    assert P.open_questions()["climbs_the_pictures_already_imply"] == []
    v = DATA["views"]["palace_hallway/main"]
    z = next(z for z in v["zones"] if z["id"] == "stairs-up")
    ys = [p[1] for p in z["points"]]
    assert min(ys) > v["camera"]["horizon_y"] and max(ys) < 480        # behind the statue's base (about row 480)
    assert z["rise_in"] is None                                         # how far they climb is still unknown


def test_a_climb_drawn_above_the_horizon_proves_it_rises_past_the_camera():
    d = copy.deepcopy(DATA)
    z = next(z for z in d["views"]["palace_hallway/main"]["zones"] if z["id"] == "stairs-up")
    z["points"] = [[722, 414], [862, 414], [852, 334], [734, 334]]      # the old outline, top above row 350
    notes = P.open_questions(d)["climbs_the_pictures_already_imply"]
    assert len(notes) == 1 and "palace_hallway/main" in notes[0] and "62 in" in notes[0]
    assert P.validate(d) == []                                          # allowed: unknown-height climbs may rise past the camera


def test_a_climb_of_unknown_height_is_not_size_checked_where_its_height_decides_the_size():
    d = copy.deepcopy(DATA)
    z = next(z for z in d["views"]["palace_hallway/main"]["zones"] if z["id"] == "stairs-up")
    z["points"] = [[772, 442], [925, 442], [915, 352], [838, 352]]      # a hair under the horizon: flat-floor maths would say 1%
    assert P.validate(d) == []
    z["rise_in"] = 0                                                    # but a known climb is checked like any floor
    assert any("tallest character" in m for m in P.validate(d))


# ── Josie's room-by-room answers, 2026-10-18 ────────────────────────────────

def _door_map(key):
    out = {}
    for d in DATA["views"][key]["doors"]:
        out.setdefault(d["to"], []).append(d)
    return out


def test_marks_she_said_were_right_are_confirmed():
    said_right = {
        "parking_lot/main": {"lobby"},
        "lobby/main": {"parking_lot", "palace_hallway"},
        "lobby_upstairs/main": {"manager_office", "projection_booth"},
        "writers_room/main": {"green_room"},
        "studio_overlook/main": {"green_room", "studio_fixedsets"},
        "studio_fixedsets/main": {"studio_director", "studio_overlook"},
        "studio_director/main": {"pubworld", "studio_fixedsets"},
        "control_room/main": {"green_room"},
        "vortex_bar/main": {"green_room"},
    }
    for key, tos in said_right.items():
        doors = _door_map(key)
        for to in tos:
            assert all(d["status"] == "confirmed" for d in doors[to]), (key, to)


def test_marks_placed_from_her_description_stay_proposed_until_she_sees_them():
    placed_by_me = [("parking_lot/main", "vortex_bar"), ("vortex_bar/main", "parking_lot"),
                    ("lobby/main", "lobby_upstairs"), ("lobby_upstairs/main", "lobby"),
                    ("palace_hallway/main", "lobby"), ("palace_hallway/main", "green_room"),
                    ("palace_hallway/main", "writers_room"), ("manager_office/main", "lobby_upstairs"),
                    ("monument/day", "parking_lot"), ("writers_room/main", "palace_hallway")]
    for key, to in placed_by_me:
        assert all(d["status"] == "proposed" for d in _door_map(key)[to]), (key, to)
    for h in DATA["views"]["control_room/main"]["hotspots"]:
        assert h["status"] == "proposed"


def test_the_monument_has_a_trigger_behind_the_monument_on_each_side_road():
    spots = [d["at"] for d in _door_map("monument/day")["parking_lot"]]
    w = world.get_room("monument").main_view.size[0]
    assert len(spots) == 2 and min(s[0] for s in spots) < w / 2 < max(s[0] for s in spots)
    assert set(_door_map("monument/day")) == {"parking_lot"}            # nothing leads out to the rest of Hollywood


def test_edge_and_bottom_triggers_sit_where_she_said():
    def size(rid):
        return world.get_room(rid).main_view.size
    lw, lh = size("lobby")
    assert _door_map("lobby/main")["lobby_upstairs"][0]["at"][0] >= lw - 20            # off to the right
    assert _door_map("lobby_upstairs/main")["lobby"][0]["at"][0] <= 20                 # walking left out of frame
    hw, hh = size("palace_hallway")
    assert _door_map("palace_hallway/main")["lobby"][0]["at"][1] >= hh - 20            # bottom of the screen
    mw, mh = size("manager_office")
    assert _door_map("manager_office/main")["lobby_upstairs"][0]["at"][1] >= mh - 20   # bottom of the screen


def test_hallway_stairs_are_one_bubble_with_green_room_first():
    doors = [d for d in DATA["views"]["palace_hallway/main"]["doors"] if d.get("group") == "stairs_choice"]
    assert [d["to"] for d in doors] == ["green_room", "writers_room"]
    assert len({tuple(d["at"]) for d in doors}) == 1


def test_the_vortex_bar_front_door_is_on_the_left_and_the_parking_lot_door_is_at_the_bar():
    left = _door_map("vortex_bar/main")["parking_lot"][0]["at"]
    back = _door_map("vortex_bar/main")["green_room"][0]["at"]
    w = world.get_room("vortex_bar").main_view.size[0]
    assert left[0] < w / 2 and left[0] < back[0]                       # left of the back door at the top middle
    bar = _door_map("parking_lot/main")["vortex_bar"][0]["at"]
    assert bar[0] > 1000 and 600 < bar[1] < 720                         # the bar's frontage, right of the lot


def test_the_whirlpool_is_just_paint_so_the_floor_is_normal_and_has_no_way_down_yet():
    v = DATA["views"]["vortex_bar/main"]
    assert "paint" in v["notes"] and len(v["zones"]) == 1 and v["zones"][0]["kind"] == "floor"
    assert "basement_bar" not in _door_map("vortex_bar/main")


def test_the_control_room_consoles_are_where_she_described_them():
    hs = {h["id"]: h for h in DATA["views"]["control_room/main"]["hotspots"]}
    assert set(hs) == {"director-console", "audio-console", "right-console"}
    assert hs["audio-console"]["at"][0] < hs["director-console"]["at"][0] < hs["right-console"]["at"][0]
    assert "decided" in hs["right-console"]["label"].lower()          # VTR, Chyron or effects: she does not know yet


def test_one_destination_may_have_two_spots_but_not_the_same_spot_twice():
    d = copy.deepcopy(DATA)
    assert P.validate(d) == []
    mon = d["views"]["monument/day"]["doors"]
    mon.append(dict(mon[0]))
    assert any("same spot" in m for m in P.validate(d))


def test_a_picture_may_not_have_both_a_camera_and_samples():
    d = with_view("green_room/main", scale=[{"y": 400, "ppi": 3.0}])
    assert any("not both" in m for m in P.validate(d))


def test_camera_numbers_must_be_believable():
    for cam in ({"horizon_y": 180, "eye_in": 5}, {"horizon_y": 180, "eye_in": 5000},
                {"horizon_y": 180}, {"horizon_y": "x", "eye_in": 60}, {"horizon_y": 99999, "eye_in": 60}):
        assert P.validate(with_view("green_room/main", camera=cam)), cam


def test_walkable_floor_above_the_horizon_is_rejected():
    # a flat floor drawn above the camera's own horizon would have no size
    d = with_view("green_room/main", camera={"horizon_y": 600, "eye_in": 66})
    assert any("wrong side" in m for m in P.validate(d))


def test_a_measurement_that_disagrees_with_its_camera_is_rejected():
    d = copy.deepcopy(DATA)
    d["views"]["green_room/main"]["scale_info"]["measured"][0]["ppi"] = 9.0
    assert any("disagrees with its camera" in m for m in P.validate(d))
    d = with_view("green_room/main", camera={"horizon_y": 180, "eye_in": 160})       # a wrong eye height
    assert any("disagrees with its camera" in m for m in P.validate(d))


def test_a_fitted_size_must_say_how_it_was_arrived_at():
    d = copy.deepcopy(DATA)
    del d["views"]["control_room/main"]["scale_info"]
    assert any("scale_info" in m for m in P.validate(d))
    for field, bad in (("confidence", "great"), ("basis", " "), ("refs", []), ("measured", [])):
        d = copy.deepcopy(DATA)
        d["views"]["control_room/main"]["scale_info"][field] = bad
        assert P.validate(d), field


def test_a_floor_at_camera_height_or_wrongly_high_is_rejected():
    d = copy.deepcopy(DATA)
    gr = d["views"]["green_room/main"]
    gr["zones"][0]["z_in"] = 66                                  # exactly the eye height
    assert any("exactly at the camera height" in m or "wrong side" in m for m in P.validate(d))


# ── solid furniture: footprints, blockers, the sunken living room (Josie, 2026-10-18) ───────────────────

def _gr_view():
    return P.merged_world(DATA) and next(
        v for r in P.merged_world(DATA)["rooms"] if r["id"] == "green_room" for v in r["views"])


def _occ(view, oid):
    return next(o for o in view["occluders"] if o["id"] == oid)


def test_depth_follows_the_slanted_front_edge_of_the_couch_not_one_flat_row():
    v = _gr_view()
    back = _occ(v, "sofa-back")
    assert back["base_y"] == 503                              # the lowest corner of its footprint
    # the couch's front edge slants up to the right: at its left end the front line is row 503, at the right end 456
    assert P.occluder_in_front(back, 495, x=700)              # at the left end an avatar on row 495 is still behind it
    assert not P.occluder_in_front(back, 495, x=850)          # at the right end the same row is already in front of it
    assert not P.occluder_in_front(back, 510, x=700)
    assert P.object_base_y(back, 850) == pytest.approx(456, abs=1)
    assert P.object_base_y({"base_y": 77}, 850) == 77         # no footprint: the single base row, as before


def test_nobody_can_walk_on_the_coffee_table_tv_or_couch_but_can_walk_round_them():
    v = _gr_view()
    assert P.blocked_at(v, (880, 530))                        # under the coffee table top
    assert P.blocked_at(v, (780, 460))                        # on the back of the couch
    assert P.blocked_at(v, (1050, 470))                       # on the TV's feet
    assert P.blocked_at(v, (600, 440))                        # on the couch's left curve (a blocker, no outline of its own)
    assert not P.blocked_at(v, (930, 448))                    # carpet between the stairs and the TV
    assert not P.blocked_at(v, (820, 555))                    # carpet in front of the table
    assert P.floor_contains([P.zone_points(z) for z in v["zones"]], (930, 448))
    assert P.floor_contains([P.zone_points(z) for z in v["zones"]], (820, 555))


def test_the_sunken_living_room_is_reached_by_the_steps_and_only_by_the_steps():
    v = _gr_view()
    cells = P._free_cells(v, 5, True)
    lab = P._components(cells)
    near = lambda p: lab[min(cells, key=lambda c: math.dist(cells[c], p))]
    main, sunken, back = near((300, 560)), near((930, 448)), near((600, 350))
    assert main == sunken == back, "the steps must join the carpet to the floor"
    no_steps = dict(v, zones=[z for z in v["zones"] if z["kind"] != "stairs"])
    cells2 = P._free_cells(no_steps, 5, True)
    lab2 = P._components(cells2)
    near2 = lambda p: lab2[min(cells2, key=lambda c: math.dist(cells2[c], p))]
    assert near2((930, 448)) != near2((300, 560)), "without the steps the carpet must be cut off (you walk round to the stairs)"


def test_the_walkable_carpet_goes_round_the_coffee_table():
    v = _gr_view()
    cells = P._free_cells(v, 5, True)
    free = lambda p: any(math.dist(c, p) <= 4 for c in cells.values())
    for p in [(745, 520), (830, 556), (1000, 520), (940, 470)]:   # left, front, right and back of the table
        assert free(p), p
    lab = P._components(cells)
    ids = {lab[min(cells, key=lambda c: math.dist(cells[c], p))] for p in [(745, 520), (830, 556), (1000, 520), (940, 470)]}
    assert len(ids) == 1, "all four sides of the coffee table are one walkable area"


def test_solid_things_never_overlap_stairs_or_ramps():
    world = P.merged_world(DATA)
    for room in world["rooms"]:
        for v in room["views"]:
            ramps = [P.zone_points(z) for z in v["zones"] if z["kind"] != "floor"]
            solids = [o["footprint"] for o in v["occluders"] if o.get("footprint")] + [b["footprint"] for b in v["blockers"]]
            for fp in solids:
                xs, ys = [p[0] for p in fp], [p[1] for p in fp]
                hits = sum(1 for x in range(int(min(xs)), int(max(xs)) + 1, 3) for y in range(int(min(ys)), int(max(ys)) + 1, 3)
                           if P.point_in_polygon((x, y), [tuple(p) for p in fp]) and any(P.point_in_polygon((x, y), r) for r in ramps))
                assert hits <= 3, (room["id"], v["id"], "a solid overlaps stairs")


def test_every_picture_keeps_every_route_between_its_doors_open_after_the_cut_outs():
    world = P.merged_world(DATA)
    for room in world["rooms"]:
        for v in room["views"]:
            assert P.broken_routes(v) == [], (room["id"], v["id"])


def test_the_green_rooms_new_sit_spots_are_proposals_and_hers_are_untouched():
    v = _gr_view()
    spots = {h["id"]: h for h in v["hotspots"]}
    assert spots["couch-sit"]["status"] == "confirmed" and spots["couch"]["status"] == "confirmed"
    assert spots["couch-sit"]["at"] == [780, 429] and spots["couch"]["at"] == [684, 513]
    for hid in ("couch-sit-left", "couch-sit-right"):
        assert spots[hid]["status"] == "proposed" and "MY PROPOSAL" in spots[hid]["note"]
