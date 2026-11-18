import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_manifest(name: str) -> dict:
    return json.loads((ROOT / "static" / name).read_text(encoding="utf-8"))


def assert_manifest_is_renderable(manifest: dict, expected_width: int, expected_height: int):
    image = manifest["image"]
    assert image["width_px"] == expected_width
    assert image["height_px"] == expected_height
    assert image["coordinate_mode"] == "normalized_percentages"
    assert manifest["hotspots"]

    for hotspot in manifest["hotspots"]:
        assert hotspot["id"]
        assert hotspot["kind"] in {"monitor", "button", "fan", "slider", "knob", "dial", "lever"}
        assert hotspot["action_id"]
        for key in ("x", "y", "w", "h"):
            assert 0 <= hotspot[key] <= 1, hotspot
        assert hotspot["x"] + hotspot["w"] <= 1.02, hotspot
        assert hotspot["y"] + hotspot["h"] <= 1.02, hotspot


def test_audio_console_manifest_keeps_source_dimensions_and_controls():
    manifest = load_manifest("audio_console_hotspot_manifest.json")
    assert manifest["console_id"] == "audio_console"
    assert_manifest_is_renderable(manifest, 1408, 768)
    kinds = {item["kind"] for item in manifest["hotspots"]}
    action_ids = {item["action_id"] for item in manifest["hotspots"]}
    assert {"monitor", "slider", "knob", "button", "fan"} <= kinds
    assert "audio.event" in action_ids
    assert "audio.stop_all" in action_ids


def test_director_console_manifest_keeps_source_dimensions_and_controls():
    manifest = load_manifest("director_console_hotspot_manifest.json")
    assert manifest["console_id"] == "director_console"
    assert_manifest_is_renderable(manifest, 1024, 1024)
    kinds = {item["kind"] for item in manifest["hotspots"]}
    action_ids = {item["action_id"] for item in manifest["hotspots"]}
    assert {"monitor", "slider", "knob", "button", "lever", "dial"} <= kinds
    assert "camera.switch.program" in action_ids
    assert "camera.cut" in action_ids


def _corners(hotspot, width, height):
    """Screen-space corners of a hotspot, turned by its track angle if it has one."""
    import math
    x, y = hotspot["x"] * width, hotspot["y"] * height
    w, h = hotspot["w"] * width, hotspot["h"] * height
    cx, cy = x + w / 2, y + h / 2
    a = math.radians(hotspot.get("angle_deg", 0))
    cos, sin = math.cos(a), math.sin(a)
    out = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        out.append((cx + dx * cos - dy * sin, cy + dx * sin + dy * cos))
    return out


def _polygons_overlap(p, q):
    """Separating-axis test for two convex quadrilaterals."""
    for poly in (p, q):
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            nx, ny = y2 - y1, x1 - x2
            a = [nx * px + ny * py for px, py in p]
            b = [nx * px + ny * py for px, py in q]
            if max(a) <= min(b) or max(b) <= min(a):
                return False
    return True


def test_audio_console_controls_do_not_overlap_so_every_touch_lands_on_one_control():
    manifest = load_manifest("audio_console_hotspot_manifest.json")
    width, height = manifest["image"]["width_px"], manifest["image"]["height_px"]
    controls = [h for h in manifest["hotspots"] if h["kind"] != "monitor"]
    shapes = {h["id"]: _corners(h, width, height) for h in controls}
    ids = list(shapes)
    clashes = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:] if _polygons_overlap(shapes[a], shapes[b])]
    assert clashes == []


def test_audio_console_faders_carry_a_sane_track_angle():
    manifest = load_manifest("audio_console_hotspot_manifest.json")
    for hotspot in manifest["hotspots"]:
        if hotspot["kind"] == "slider":
            assert -89 < hotspot["angle_deg"] < 89, hotspot["id"]
            assert hotspot["h"] * 768 > hotspot["w"] * 1408, hotspot["id"]
