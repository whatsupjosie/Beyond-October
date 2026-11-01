"""static/world/world.json is generated from the manifest and placements; it must never go stale."""
import json
import subprocess
import sys
from pathlib import Path

from modules import pubcast_world as world
from modules import pubcast_world_placement as P

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "static" / "world" / "world.json"


def test_world_json_is_in_sync_with_the_manifest_and_placements():
    on_disk = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(P.merged_world())), \
        "run: python tools/build_world_json.py"


def test_the_builder_check_passes_and_is_deterministic():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_world_json.py"), "--check"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    sys.path.insert(0, str(ROOT / "tools"))
    import build_world_json
    assert build_world_json.build_text() == build_world_json.build_text()


def test_every_picture_in_the_json_exists_and_matches_the_manifest():
    # the manifest's own sizes are checked against the image files in test_pubcast_world.py
    m = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    n = 0
    for room in m["rooms"]:
        for v in room["views"]:
            assert (ROOT / v["image"].lstrip("/")).exists(), v["image"]
            declared = next(x for x in world.WORLD[room["id"]].views if x.view_id == v["id"])
            assert (v["w"], v["h"]) == declared.size, (room["id"], v["id"])
            n += 1
    assert n == sum(len(r.views) for r in world.WORLD.values())


def test_the_json_carries_what_the_walkable_viewer_needs():
    m = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert m["character_height_in"] == {"sir_purfluous": 74, "pete": 68, "repeat": 70}
    for room in m["rooms"]:
        for v in room["views"]:
            for k in ("camera", "scale", "scale_info", "zones", "occluders", "doors", "hotspots", "status", "pad_status"):
                assert k in v, (room["id"], v["id"], k)
            if v["zones"]:
                assert (v["camera"] is not None) != bool(v["scale"]), (room["id"], v["id"])
    # no picture is approved as a whole; only the parking lot's walking path is (Josie, 2026-10-18)
    assert all(v["status"] == "proposed" for r in m["rooms"] for v in r["views"])
    paths = {f"{r['id']}/{v['id']}" for r in m["rooms"] for v in r["views"] if v["pad_status"] == "confirmed"}
    assert paths == {"parking_lot/main"}
