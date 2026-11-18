"""The typewriter hotspot manifest must stay renderable and complete."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "static" / "typewriter_console_hotspot_manifest.json").read_text(encoding="utf-8"))


def test_manifest_matches_generator_output():
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_typewriter_manifest", ROOT / "tools" / "build_typewriter_manifest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build() == MANIFEST, "run: python tools/build_typewriter_manifest.py"


def test_image_exists_and_dimensions_are_declared():
    image = MANIFEST["image"]
    assert (ROOT / image["clean_path"].lstrip("/")).exists()
    assert image["width_px"] == 2560 and image["height_px"] == 1430
    assert image["coordinate_mode"] == "normalized_percentages"


def test_every_legend_has_a_key_and_ids_are_unique():
    chars = [h["char"] for h in MANIFEST["hotspots"]]
    for needed in list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") + ["SHIFT", "SPACE", "RETURN", ";", "'", ",", ".", "/", "-"]:
        assert needed in chars, needed
    assert chars.count("SHIFT") == 2
    ids = [h["id"] for h in MANIFEST["hotspots"]]
    assert len(ids) == len(set(ids))


def test_hotspots_are_inside_the_image_and_do_not_overlap():
    boxes = []
    for h in MANIFEST["hotspots"]:
        for key in ("x", "y", "w", "h"):
            assert 0 <= h[key] <= 1, h
        assert h["x"] + h["w"] <= 1 and h["y"] + h["h"] <= 1, h
        if h["kind"] == "key":
            boxes.append((h["id"], h["x"], h["y"], h["x"] + h["w"], h["y"] + h["h"]))
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            overlap_w = min(a[3], b[3]) - max(a[1], b[1])
            overlap_h = min(a[4], b[4]) - max(a[2], b[2])
            assert not (overlap_w > 0.0005 and overlap_h > 0.0005), (a[0], b[0])


def test_keys_carry_no_studio_action():
    for h in MANIFEST["hotspots"]:
        assert h["kind"] in {"key", "lever"}
        assert "action_id" not in h
