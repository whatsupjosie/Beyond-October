"""Build static/typewriter_console_hotspot_manifest.json from the key grid.

The typewriter art is a painting, so key positions are measured, not computed.
They are stored below in the pixel space of the 3840 x 2145 master (the same
space the lettering was drawn in) and written out as fractions of the image,
which is what the console renderer needs and why a sharper repaint at any size
only needs this table nudged, not rewritten.

Run from the repo root:  python tools/build_typewriter_manifest.py
"""
from __future__ import annotations

import json
from pathlib import Path

MASTER_W, MASTER_H = 3840, 2145
IMAGE = {"clean_path": "/static/typewriter_keys.webp", "width_px": 2560, "height_px": 1430}

# (row centre y, [key centre x ...], legends) in master pixels.
ROWS = [
    (1394, [1334, 1456, 1576, 1696, 1814, 1934, 2054, 2172, 2286, 2408, 2530], "1234567890-"),
    (1504, [1276, 1396, 1516, 1636, 1756, 1876, 1992, 2112, 2228, 2344, 2468], "QWERTYUIOP½"),
    (1604, [1334, 1456, 1576, 1694, 1814, 1934, 2054, 2174, 2294, 2414, 2530], "ASDFGHJKL;'"),
    (1708, [1370, 1492, 1612, 1730, 1846, 1964, 2084, 2204, 2324, 2444], "ZXCVBNM,./"),
]
KEY_W, KEY_H = 118, 98          # touch cell: the key pitch, so there are no dead gaps
WIDE = [  # (id, legend, centre x, centre y, w, h)
    ("tw.key.shift_left", "SHIFT", 1214, 1710, 150, 100),
    ("tw.key.shift_right", "SHIFT", 2624, 1710, 150, 100),
    ("tw.key.blank", "BLANK", 1196, 1600, 110, 90),
]
SPACE = ("tw.key.space", "SPACE", 1922, 1822, 1032, 90)
# Carriage return lever, left of the machine (fractions of the image).
LEVER = {"x": 0.185, "y": 0.34, "w": 0.115, "h": 0.2}
PAPER = {"x": 0.347, "y": 0.0, "w": 0.308, "h": 0.372}
# Show only the machine: the art has wide dark margins, and on a tablet the keys
# are too small to touch unless the machine fills the screen width.
VIEW = {"x": 0.16, "w": 0.68}


def cell(cx: float, cy: float, w: float, h: float) -> dict:
    return {
        "x": round(cx / MASTER_W - w / MASTER_W / 2, 5),
        "y": round(cy / MASTER_H - h / MASTER_H / 2, 5),
        "w": round(w / MASTER_W, 5),
        "h": round(h / MASTER_H, 5),
    }


def build() -> dict:
    hotspots = []
    for cy, xs, legends in ROWS:
        assert len(xs) == len(legends), (cy, len(xs), len(legends))
        for index, (cx, char) in enumerate(zip(xs, legends)):
            # Never wider than the gap to a neighbour, so cells touch but never overlap.
            gaps = [abs(cx - xs[j]) for j in (index - 1, index + 1) if 0 <= j < len(xs)]
            width = min(KEY_W, min(gaps))
            name = {"-": "dash", ";": "semicolon", "'": "apostrophe", ",": "comma", ".": "period", "/": "slash", "½": "half"}.get(char, char.lower())
            hotspots.append({"id": f"tw.key.{name}", "kind": "key", "label": f"Key {char}", "char": char, **cell(cx, cy, width, KEY_H)})
    for ident, char, cx, cy, w, h in WIDE:
        label = "Blank key" if char == "BLANK" else "Shift"
        hotspots.append({"id": ident, "kind": "key", "label": label, "char": char, **cell(cx, cy, w, h)})
    ident, char, cx, cy, w, h = SPACE
    hotspots.append({"id": ident, "kind": "key", "label": "Space bar", "char": char, **cell(cx, cy, w, h)})
    hotspots.append({"id": "tw.lever.return", "kind": "lever", "label": "Carriage return lever", "char": "RETURN", **LEVER})
    return {
        "schema": "pubcast.console_hotspot_manifest.v1",
        "console_id": "typewriter_console",
        "keyboard_mirror": True,
        "image": {**IMAGE, "coordinate_mode": "normalized_percentages"},
        "paper": PAPER,
        "view": VIEW,
        "color_legend": {"key": "typewriter key: acts on touch-down, announces pubcast:key"},
        "hotspots": hotspots,
    }


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "static" / "typewriter_console_hotspot_manifest.json"
    out.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", out, len(build()["hotspots"]), "hotspots")
