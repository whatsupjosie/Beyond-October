"""Compare clickable rectangles with independently inspected artwork points.

This is geometry/source verification, not browser rendering or pointer hit testing.
"""
from pathlib import Path
import hashlib
import itertools
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    mapping = json.loads((ROOT / "2i/2i-assets/hotspots.json").read_text())
    reviewed = json.loads((ROOT / "writer_room_audit/hotspot_alignment_review.json").read_text())
    controls = {c["id"]: c["bounds"] for c in mapping["controls"]}
    assert set(controls) == set(reviewed["expected_centers"])
    assert hashlib.sha256((ROOT / "2i/2i-assets/writers-room-art.webp").read_bytes()).hexdigest() == mapping["image"]["sha256"]
    for name, (cx, cy) in reviewed["expected_centers"].items():
        x, y, width, height = controls[name]
        assert x <= cx <= x + width and y <= cy <= y + height, name
    for (a, ar), (b, br) in itertools.combinations(controls.items(), 2):
        intersection = min(ar[0]+ar[2], br[0]+br[2])-max(ar[0],br[0]), min(ar[1]+ar[3],br[1]+br[3])-max(ar[1],br[1])
        assert intersection[0] <= 0 or intersection[1] <= 0, (a, b, "overlap")
    viewports = [(1344,896), (1366,768), (1280,720), (1920,1080), (672,448), (390,844)]
    for vw, vh in viewports:
        scale = min(vw/1344, vh/896)
        ox, oy = (vw-1344*scale)/2, (vh-896*scale)/2
        for name, (cx, cy) in reviewed["expected_centers"].items():
            x,y,w,h = controls[name]
            px,py = ox+cx*scale,oy+cy*scale
            assert ox+x*scale <= px <= ox+(x+w)*scale
            assert oy+y*scale <= py <= oy+(y+h)*scale
    print(json.dumps({"ok":True,"controls":len(controls),"artwork":"original hash preserved","reference_points":"all inside their own control","control_overlaps":0,"projected_viewports":viewports,"browser_rendering_verified":False},indent=2))


if __name__ == "__main__":
    main()
