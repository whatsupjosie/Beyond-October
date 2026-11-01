"""Build static/world/world.json from the world manifest and the placements.

    python tools/build_world_json.py           write the file
    python tools/build_world_json.py --check   exit 1 if the file is out of date

The viewer (static/world_walk.html) reads that one file. It is generated, never
edited by hand: change modules/pubcast_world.py (topology) or
data/world/placements.json (positions, sizes), then run this. A test fails when
the committed file is stale.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules import pubcast_world_placement as placement  # noqa: E402

OUT = ROOT / "static" / "world" / "world.json"


def build_text() -> str:
    """Deterministic JSON: same inputs always give byte-identical output."""
    return json.dumps(placement.merged_world(), indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    text = build_text()
    if "--check" in args:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
        if current != text:
            print(f"{OUT.relative_to(ROOT)} is out of date: run python tools/build_world_json.py")
            return 1
        print(f"{OUT.relative_to(ROOT)} is up to date")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
