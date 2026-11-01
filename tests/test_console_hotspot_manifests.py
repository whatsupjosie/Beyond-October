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
