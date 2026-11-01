"""
pubcast_world_placement.py — where things stand inside each room picture
==============================================================================
Rear View Foresight LLC · Feic Mo Chroí™

Loads and checks data/world/placements.json, which holds, for every picture in
pubcast_world.WORLD:

  camera    per-picture camera {"horizon_y", "eye_in"}: the row where avatars
            shrink to nothing and the camera's height above the floor in
            inches. The preferred way to size avatars (see below).
  scale     avatar size samples [{"y", "ppi"}]: used when a picture has no
            usable camera (curved, fisheye or sketch-style pictures), see below
  scale_info  how the size was arrived at: {"confidence": good|fair|low,
            "basis": plain-language why, "refs": what was measured,
            "measured": [{"row", "ppi"}] the numbers the fit was checked
            against, "alt": an alternative reading when two kinds of reference
            disagree}
  zones     walkable areas in source-picture pixels. Each zone is a polygon with
            a kind (floor | stairs | ramp), a level name and an altitude, so
            steps, platforms and slopes are marked, not flattened:
              floor   flat ground at altitude z_in (inches above this picture's
                      base level, 0 for the main floor)
              stairs / ramp   an axis [[x,y],[x,y]] from the start to the end
                      of the climb, and rise_in, the altitude gained going
                      along it (negative = going down). Altitude at a point
                      is z_in + rise_in * t, t = how far along the axis.
            A number that is not known yet is null, and is listed by
            open_questions() instead of being guessed.
  blockers  solid things on the floor that nobody can walk on: {"id", "label",
            "footprint", "note"}. The footprint is the floor under the object
            (a couch, a table, a statue base), traced tight against the
            picture in source pixels, so the walkable area stays right up to
            the furniture. Floor BEHIND an object stays walkable (the avatar
            is hidden by the object's occluder outline there). A hotspot may
            sit on a blocker: that is how you sit on a couch you cannot walk on.
  doors     {"to", "at", "r"}: where each exit sits in this picture
  hotspots  {"id", "label", "at", "r", "action"}: things to use or look at
  elevations  per-room altitude in inches above the Palace ground floor, null
            until Josie gives it (the Vortex Bar is lower than the Palace
            Theater; the green room is up the hallway stairs)
  status    "proposed" (placed by Claude from looking at the picture, needs
            Josie's eye) | "confirmed" (Josie has checked it)

DESIGN RULE (Josie, 2026-10-18): every picture used as a background gets its
own avatar size, fitted once to that picture. Every picture must have an entry
here even when its scale is not fitted yet (``"scale": []``), so adding a
picture without deciding is impossible: validate() fails and so does the test.

How the size works with a camera. Every picture is a different camera, so each
gets its own: ``ppi(y, z) = (y - horizon_y) / (eye_in - z)`` pixels per real inch
for a floor at altitude ``z`` inches (negative = below the main floor, which
makes avatars smaller, because the camera is further above that floor). A
character is drawn at ``canonical_height_in * ppi`` pixels tall with the feet on
row ``y``. This assumes a pinhole camera with little tilt; pictures that break
that (curved, fisheye, sketch-style, or painted inconsistently) carry samples
instead and a "low" confidence. ``scale_info`` says why, and nothing is ever
better than "proposed" until Josie has looked at it.

How the size works with samples. Positions are in source-picture pixels. A scale sample is
"at screen row ``y`` one real inch of height is ``ppi`` pixels tall". One
sample means the same size everywhere; two or more are fitted by least squares
(a flat floor seen in perspective is linear in y, so near the camera, lower in
the picture, avatars are bigger). A character is drawn at
``canonical_height_in * ppi(y)`` pixels tall with their feet at row ``y``.
Canonical heights are in pubcast_world.CHARACTER_HEIGHT_IN. Big rooms get
small avatars on purpose.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import pubcast_world as world

PLACEMENTS_PATH = Path(__file__).resolve().parent.parent / "data" / "world" / "placements.json"

Point = Tuple[float, float]
STATUSES = ("proposed", "confirmed")
ACTION_TYPES = ("view", "animation", "custom", "program")
ZONE_KINDS = ("floor", "stairs", "ramp")
CONFIDENCE = ("good", "fair", "low")
# A camera is believable only inside these limits (inches above the floor).
EYE_MIN_IN, EYE_MAX_IN = 12.0, 600.0
# Every measurement a camera was fitted from must agree with that camera within
# this fraction (painted pictures are not geometrically exact).
RESIDUAL_TOL = 0.25
# Two zones whose edges are this close count as touching (a step edge, a rim).
TOUCH_PX = 12
# A door can sit on the wall behind the floor (a door in a back wall); this is
# how far from the walkable floor it may be before something is wrong.
DOOR_REACH_PX = 300


def view_key(room_id: str, view_id: str) -> str:
    return f"{room_id}/{view_id}"


def load(path: Path = PLACEMENTS_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ════════════════════════════════════════════════════════════════════════════
# GEOMETRY
# ════════════════════════════════════════════════════════════════════════════

def point_in_polygon(pt: Point, poly: Sequence[Point]) -> bool:
    """Ray casting; points on an edge count as inside."""
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if _on_segment(pt, (x1, y1), (x2, y2)):
            return True
        if (y1 > y) != (y2 > y):
            if x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
    return inside


def _on_segment(p: Point, a: Point, b: Point, eps: float = 1e-9) -> bool:
    cross = (p[1] - a[1]) * (b[0] - a[0]) - (p[0] - a[0]) * (b[1] - a[1])
    if abs(cross) > eps * max(1.0, abs(b[0] - a[0]) + abs(b[1] - a[1])):
        return False
    return (min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
            and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps)


def closest_point_on_segment(p: Point, a: Point, b: Point) -> Point:
    dx, dy = b[0] - a[0], b[1] - a[1]
    seg = dx * dx + dy * dy
    if seg == 0:
        return a
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / seg))
    return (a[0] + t * dx, a[1] + t * dy)


def floor_contains(floor: Sequence[Sequence[Point]], pt: Point) -> bool:
    return any(point_in_polygon(pt, poly) for poly in floor)


def snap_to_floor(floor: Sequence[Sequence[Point]], pt: Point) -> Optional[Point]:
    """The point itself if it is on the floor, else the nearest floor edge
    point. None when there is no floor."""
    if not floor:
        return None
    if floor_contains(floor, pt):
        return (float(pt[0]), float(pt[1]))
    best, best_d = None, math.inf
    for poly in floor:
        for i in range(len(poly)):
            c = closest_point_on_segment(pt, poly[i], poly[(i + 1) % len(poly)])
            d = math.dist(c, pt)
            if d < best_d:
                best, best_d = c, d
    return best


def distance_to_floor(floor: Sequence[Sequence[Point]], pt: Point) -> float:
    s = snap_to_floor(floor, pt)
    return math.inf if s is None else math.dist(s, pt)


def polygon_area(poly: Sequence[Point]) -> float:
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1]
                   - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2.0


def _segments_cross(a, b, c, d) -> bool:
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return (o1 * o2 < 0) and (o3 * o4 < 0)


def polygon_self_intersects(poly: Sequence[Point]) -> bool:
    n = len(poly)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            if _segments_cross(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                return True
    return False



def polygons_overlap(a: Sequence[Point], b: Sequence[Point]) -> bool:
    if any(point_in_polygon(p, b) for p in a) or any(point_in_polygon(p, a) for p in b):
        return True
    for i in range(len(a)):
        for j in range(len(b)):
            if _segments_cross(a[i], a[(i + 1) % len(a)], b[j], b[(j + 1) % len(b)]):
                return True
    return False


def polygon_distance(a: Sequence[Point], b: Sequence[Point]) -> float:
    """0 when the polygons overlap, else the closest edge-to-edge distance."""
    if polygons_overlap(a, b):
        return 0.0
    best = math.inf
    for poly, other in ((a, b), (b, a)):
        for p in poly:
            for j in range(len(other)):
                c = closest_point_on_segment(p, other[j], other[(j + 1) % len(other)])
                best = min(best, math.dist(p, c))
    return best


def axis_fraction(axis: Sequence[Point], pt: Point) -> float:
    """How far along the axis (0 at its start, 1 at its end) ``pt`` projects."""
    (x1, y1), (x2, y2) = axis
    dx, dy = x2 - x1, y2 - y1
    seg = dx * dx + dy * dy
    if seg == 0:
        return 0.0
    return max(0.0, min(1.0, ((pt[0] - x1) * dx + (pt[1] - y1) * dy) / seg))


def zone_points(zone: dict) -> List[Point]:
    return [tuple(p) for p in zone["points"]]


def altitude_at(zone: dict, pt: Point) -> Optional[float]:
    """Altitude (inches above the picture's base level) at ``pt`` inside
    ``zone``, or None while the number is not known yet."""
    z = zone.get("z_in")
    if zone.get("kind") == "floor" or z is None:
        return z
    rise = zone.get("rise_in")
    if rise is None:
        return None
    return z + rise * axis_fraction(zone["axis"], pt)


def zone_at(zones: Sequence[dict], pt: Point) -> Optional[dict]:
    """The zone ``pt`` stands in. Where zones overlap, stairs and ramps win
    over flat floor (you are on the steps, not on the landing)."""
    inside = [z for z in zones if point_in_polygon(pt, zone_points(z))]
    if not inside:
        return None
    inside.sort(key=lambda z: 0 if z.get("kind") != "floor" else 1)
    return inside[0]


def zone_components(zones: Sequence[dict]) -> List[List[str]]:
    """Groups of zone ids that touch each other (so you can walk between them)."""
    ids = [z["id"] for z in zones]
    parent = {i: i for i in ids}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(zones)):
        for j in range(i + 1, len(zones)):
            if polygon_distance(zone_points(zones[i]), zone_points(zones[j])) <= TOUCH_PX:
                parent[find(zones[i]["id"])] = find(zones[j]["id"])
    groups: Dict[str, List[str]] = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())

# ════════════════════════════════════════════════════════════════════════════
# AVATAR SCALE
# ════════════════════════════════════════════════════════════════════════════

def fit_scale(samples: Sequence[dict]) -> Optional[Tuple[float, float]]:
    """(intercept, slope) so that ppi(y) = intercept + slope * y, or None when
    there are no samples. One sample (or all at the same row) is flat."""
    pts = [(float(s["y"]), float(s["ppi"])) for s in samples]
    if not pts:
        return None
    ys = [p[0] for p in pts]
    if len(pts) == 1 or max(ys) == min(ys):
        return (sum(p[1] for p in pts) / len(pts), 0.0)
    my = sum(ys) / len(pts)
    mp = sum(p[1] for p in pts) / len(pts)
    var = sum((y - my) ** 2 for y in ys)
    slope = sum((y - my) * (p - mp) for y, p in pts) / var
    return (mp - slope * my, slope)


def ppi_at(samples: Sequence[dict], y: float) -> Optional[float]:
    """Pixels per inch at row ``y``, or None if the picture is not fitted."""
    fit = fit_scale(samples)
    if fit is None:
        return None
    return fit[0] + fit[1] * y


def avatar_pixel_height(samples: Sequence[dict], height_in: float, y: float) -> Optional[float]:
    """Pixels tall to draw an avatar of ``height_in`` inches with feet on row
    ``y``, or None when the picture is not fitted. Never a guess."""
    ppi = ppi_at(samples, y)
    return None if ppi is None else height_in * ppi


def zone_scale(view: dict, zone: Optional[dict]) -> Sequence[dict]:
    """A zone may carry its own scale (a raised platform does not follow the
    floor's perspective); otherwise the picture's scale applies."""
    return (zone or {}).get("scale") or view.get("scale", [])


def horizon_y(samples: Sequence[dict]) -> Optional[float]:
    """Row where avatars shrink to nothing (the horizon), when the fit slopes."""
    fit = fit_scale(samples)
    if fit is None or fit[1] == 0:
        return None
    return -fit[0] / fit[1]


def camera_of(view: dict) -> Optional[Tuple[float, float]]:
    """(horizon row, eye height in inches) when the picture has a camera."""
    cam = view.get("camera")
    if not cam:
        return None
    return (float(cam["horizon_y"]), float(cam["eye_in"]))


def ppi_for(view: dict, y: float, z: Optional[float] = None,
            zone: Optional[dict] = None) -> Optional[float]:
    """Pixels per inch at row ``y`` for a floor at altitude ``z`` inches.

    A zone's own scale wins (a raised platform may not follow the floor's
    perspective). Then the picture's camera. Then its samples. ``z`` None means
    the altitude is not known yet: it is treated as the main floor (0) and the
    number is listed by open_questions(), never invented. Returns None when the
    picture is not fitted, or the row is at or above the horizon.
    """
    if zone and zone.get("scale"):
        ppi = ppi_at(zone["scale"], y)
    else:
        cam = camera_of(view)
        if cam:
            horizon, eye = cam
            drop = 0.0 if z is None else float(z)
            if eye - drop == 0:
                return None
            # A floor higher than the camera (stairs climbing past eye level)
            # appears ABOVE the horizon: numerator and denominator are both
            # negative and the size is still positive.
            ppi = (y - horizon) / (eye - drop)
        else:
            ppi = ppi_at(view.get("scale", []), y)
    if ppi is None or ppi <= 0:
        return None
    return ppi


def avatar_height_px(view: dict, height_in: float, y: float, z: Optional[float] = None,
                     zone: Optional[dict] = None) -> Optional[float]:
    """Pixels tall to draw a ``height_in`` character with feet on row ``y``,
    or None when the picture is not fitted. Never a guess."""
    ppi = ppi_for(view, y, z, zone)
    return None if ppi is None else height_in * ppi


def scale_known(view: dict) -> bool:
    return bool(view.get("camera") or view.get("scale"))


# ════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ════════════════════════════════════════════════════════════════════════════

def _all_view_sizes() -> Dict[str, Tuple[int, int]]:
    return {view_key(r.room_id, v.view_id): v.size
            for r in world.WORLD.values() for v in r.views}


def _exit_view(room: world.WorldRoom, ex: world.Exit) -> str:
    return ex.view or (room.views[0].view_id if room.views else "")


def _check_polygon(issues: List[str], where: str, pts, w: int, h: int) -> bool:
    """Shared polygon checks. Returns True when usable."""
    if not isinstance(pts, list) or len(pts) < 3:
        issues.append(f"{where}: needs at least 3 points")
        return False
    ok = True
    for pt in pts:
        if not (isinstance(pt, list) and len(pt) == 2 and 0 <= pt[0] <= w and 0 <= pt[1] <= h):
            issues.append(f"{where}: point {pt} outside {w}x{h}")
            ok = False
    if not ok:
        return False
    poly = [tuple(p) for p in pts]
    if polygon_area(poly) <= 0:
        issues.append(f"{where}: no area")
        return False
    if polygon_self_intersects(poly):
        issues.append(f"{where}: crosses itself")
        return False
    return True


def _check_scale(issues: List[str], where: str, samples, h: int, tallest: float):
    for s in samples:
        y, ppi = s.get("y"), s.get("ppi")
        if not isinstance(y, (int, float)) or not isinstance(ppi, (int, float)):
            issues.append(f"{where}: scale sample {s} needs numeric y and ppi")
            continue
        if not (0 <= y <= h):
            issues.append(f"{where}: scale sample row {y} outside the picture (0..{h})")
        frac = ppi * tallest / h
        if ppi <= 0 or not (0.02 <= frac <= 1.0):
            issues.append(f"{where}: scale {ppi} px/in draws the tallest character at "
                          f"{frac:.0%} of the picture height; must be 2%..100%")


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _check_camera(issues: List[str], key: str, v: dict, usable: Sequence[dict], h: int, tallest: float):
    cam = v.get("camera")
    if not cam:
        return
    if v.get("scale"):
        issues.append(f"{key}: give a camera or scale samples, not both")
    if not (isinstance(cam, dict) and _is_num(cam.get("horizon_y")) and _is_num(cam.get("eye_in"))):
        issues.append(f"{key}: camera needs numeric horizon_y and eye_in")
        return
    horizon, eye = float(cam["horizon_y"]), float(cam["eye_in"])
    if not (-h <= horizon <= h):
        issues.append(f"{key}: camera horizon_y {horizon} is nowhere near the picture (0..{h})")
    if not (EYE_MIN_IN <= eye <= EYE_MAX_IN):
        issues.append(f"{key}: camera eye_in {eye} outside {EYE_MIN_IN:g}..{EYE_MAX_IN:g} inches")
        return
    for z in usable:
        for (px, py) in z["points"]:
            alt = altitude_at(z, (px, py))
            a = 0.0 if alt is None else float(alt)
            den = eye - a
            if den == 0:
                issues.append(f"{key} zone '{z['id']}': altitude {a:g} in is exactly at the camera height, "
                              f"so no avatar size exists there")
                break
            if alt is None and z["kind"] != "floor":
                # A climb of unknown height: the size at its upper rows depends on a
                # height nobody knows yet, so there is nothing to check. What the
                # picture does prove about it is reported by implied_climb_minimums().
                continue
            ppi = (py - horizon) / den
            if ppi <= 0:
                issues.append(f"{key} zone '{z['id']}': point ({px:g}, {py:g}) is on the wrong side of the camera's "
                              f"horizon (row {horizon:g}) for altitude {a:g} in; no avatar size exists there")
                break
            frac = tallest * ppi / h
            if not (0.02 <= frac <= 1.0):
                issues.append(f"{key} zone '{z['id']}': at ({px:g}, {py:g}) the tallest character would be "
                              f"{frac:.0%} of the picture height; must be 2%..100%")
                break


def _check_scale_info(issues: List[str], key: str, v: dict):
    if not scale_known(v):
        return
    info = v.get("scale_info")
    if not isinstance(info, dict):
        issues.append(f"{key}: a fitted size needs scale_info (confidence, basis, refs, measured)")
        return
    if info.get("confidence") not in CONFIDENCE:
        issues.append(f"{key}: scale_info confidence must be one of {CONFIDENCE}")
    if not (isinstance(info.get("basis"), str) and info["basis"].strip()):
        issues.append(f"{key}: scale_info needs a plain-language basis (why this size)")
    refs = info.get("refs")
    if not (isinstance(refs, list) and refs and all(isinstance(r, str) and r.strip() for r in refs)):
        issues.append(f"{key}: scale_info needs refs (what was measured)")
    measured = info.get("measured")
    if not (isinstance(measured, list) and measured and all(
            isinstance(m, dict) and _is_num(m.get("row")) and _is_num(m.get("ppi")) and m["ppi"] > 0
            for m in measured)):
        issues.append(f"{key}: scale_info needs measured [{{row, ppi}}] numbers")
    elif v.get("camera") and not _camera_malformed(v):
        for m in measured:
            pred = ppi_for({"camera": v["camera"]}, m["row"])
            if pred is None or abs(pred - m["ppi"]) / m["ppi"] > RESIDUAL_TOL:
                issues.append(f"{key}: measurement {m['ppi']} px/in at row {m['row']} disagrees with its "
                              f"camera (predicts {pred if pred is None else round(pred, 2)}); "
                              f"more than {RESIDUAL_TOL:.0%} off")
    alt = info.get("alt")
    if alt is not None:
        ok = (isinstance(alt, dict) and isinstance(alt.get("label"), str) and alt["label"].strip()
              and isinstance(alt.get("samples"), list) and len(alt["samples"]) >= 2
              and all(isinstance(a, dict) and _is_num(a.get("y")) and _is_num(a.get("ppi")) and a["ppi"] > 0
                      for a in alt["samples"]))
        if not ok:
            issues.append(f"{key}: scale_info alt needs a label and two or more {{y, ppi}} samples")


def _camera_malformed(v: dict) -> bool:
    cam = v.get("camera")
    return not (isinstance(cam, dict) and _is_num(cam.get("horizon_y")) and _is_num(cam.get("eye_in"))
                and cam["eye_in"] > 0)


def validate(data: Optional[dict] = None) -> List[str]:
    """Problems with the placements. Empty list means they are sound.

    Structural errors only. Things that are merely not decided yet (a null
    altitude, an unfitted scale, an unplaced door) are not errors; they are
    listed by open_questions().
    """
    data = load() if data is None else data
    issues: List[str] = []
    sizes = _all_view_sizes()
    views = data.get("views", {})
    tallest = max(h for h in world.CHARACTER_HEIGHT_IN.values() if h)

    for key in sizes:
        if key not in views:
            issues.append(f"{key}: no placements entry (every picture needs one, "
                          f"even with scale [])")
    for key in views:
        if key not in sizes:
            issues.append(f"{key}: not a picture in the world manifest")

    for rid, z in data.get("elevations", {}).items():
        if rid not in world.WORLD:
            issues.append(f"elevations: '{rid}' is not a room")
        if z is not None and not isinstance(z, (int, float)):
            issues.append(f"elevations: '{rid}' must be a number or null")

    for key, v in views.items():
        if key not in sizes:
            continue
        w, h = sizes[key]
        room_id, view_id = key.split("/", 1)
        room = world.WORLD[room_id]

        if v.get("status") not in STATUSES:
            issues.append(f"{key}: status must be one of {STATUSES}")
        if v.get("pad_status", "proposed") not in STATUSES:
            issues.append(f"{key}: pad_status must be one of {STATUSES}")
        _check_scale(issues, key, v.get("scale", []), h, tallest)

        # zones
        zones = v.get("zones", [])
        zone_ids = set()
        usable = []
        for z in zones:
            zid = z.get("id")
            where = f"{key} zone '{zid}'"
            if not zid or zid in zone_ids:
                issues.append(f"{key}: zone id '{zid}' missing or duplicated")
            zone_ids.add(zid)
            if z.get("kind") not in ZONE_KINDS:
                issues.append(f"{where}: kind must be one of {ZONE_KINDS}")
                continue
            if not z.get("level"):
                issues.append(f"{where}: needs a level name")
            if "z_in" not in z or not (z["z_in"] is None or isinstance(z["z_in"], (int, float))):
                issues.append(f"{where}: z_in must be a number or null")
            if z["kind"] != "floor":
                ax = z.get("axis")
                if not (isinstance(ax, list) and len(ax) == 2 and all(
                        isinstance(p, list) and len(p) == 2 and 0 <= p[0] <= w and 0 <= p[1] <= h
                        for p in ax)) or ax[0] == ax[1]:
                    issues.append(f"{where}: {z['kind']} needs an axis of two different points "
                                  f"inside the picture")
                if "rise_in" not in z or not (z["rise_in"] is None or isinstance(z["rise_in"], (int, float))):
                    issues.append(f"{where}: {z['kind']} needs rise_in (a number, or null if not known)")
            if "estimated" in z and not isinstance(z["estimated"], bool):
                issues.append(f"{where}: estimated must be true or false")
            if z.get("estimated") and z["kind"] == "floor" and z.get("z_in") is None:
                issues.append(f"{where}: marked estimated but has no number")
            if "scale" in z:
                _check_scale(issues, where, z["scale"], h, tallest)
            if _check_polygon(issues, where, z.get("points"), w, h):
                usable.append(z)

        # a level change between touching flat floors needs steps or a ramp between them
        floors = [z for z in usable if z["kind"] == "floor" and isinstance(z.get("z_in"), (int, float))]
        for i in range(len(floors)):
            for j in range(i + 1, len(floors)):
                a, b = floors[i], floors[j]
                if a["z_in"] != b["z_in"] and polygon_distance(zone_points(a), zone_points(b)) <= TOUCH_PX:
                    issues.append(f"{key}: floors '{a['id']}' (z {a['z_in']}) and '{b['id']}' "
                                  f"(z {b['z_in']}) touch with no stairs or ramp between them")

        _check_camera(issues, key, v, usable, h, tallest)
        _check_scale_info(issues, key, v)

        # scale must stay positive across the walkable rows
        if v.get("scale") and usable:
            ys = [p[1] for z in usable for p in z["points"]]
            for y in (min(ys), max(ys)):
                ppi = ppi_at(v["scale"], y)
                if ppi is None or ppi <= 0:
                    issues.append(f"{key}: fitted scale is not positive at walkable row {y}")

        # occluders: things the avatar walks in front of or behind
        occ_ids = set()
        for o in v.get("occluders", []):
            oid = o.get("id")
            where = f"{key} occluder '{oid}'"
            if not oid or oid in occ_ids:
                issues.append(f"{key}: occluder id '{oid}' missing or duplicated")
            occ_ids.add(oid)
            _check_polygon(issues, where + " outline", o.get("points"), w, h)
            always = o.get("always") is True
            by = o.get("base_y")
            if always == (by is not None):
                issues.append(f"{where}: give either always=true (foreground, always in "
                              f"front of the avatar) or base_y (the row where it meets the floor)")
            if by is not None and not (isinstance(by, (int, float)) and 0 <= by <= h):
                issues.append(f"{where}: base_y {by} outside the picture")
            fp = o.get("footprint")
            if fp is not None:
                _check_polygon(issues, where + " footprint", fp, w, h)

        # blockers: solid things on the floor
        block_ids = set()
        for b in v.get("blockers", []):
            bid = b.get("id")
            where = f"{key} blocker '{bid}'"
            if not bid or bid in block_ids:
                issues.append(f"{key}: blocker id '{bid}' missing or duplicated")
            block_ids.add(bid)
            if not b.get("label"):
                issues.append(f"{where}: needs a label")
            if _check_polygon(issues, where + " footprint", b.get("footprint"), w, h):
                fp = [tuple(p) for p in b["footprint"]]
                if usable and not any(polygons_overlap(fp, zone_points(z)) for z in usable):
                    issues.append(f"{where}: sits outside every walkable zone, so it blocks nothing")

        # doors
        exits_here = {e.to for e in room.exits if _exit_view(room, e) == view_id}
        seen_door = set()
        for d in v.get("doors", []):
            to, at = d.get("to"), d.get("at")
            if to not in exits_here:
                issues.append(f"{key}: door to '{to}' but {room_id} has no exit "
                              f"to '{to}' in this picture")
            # One destination may have several spots (the monument's two side
            # roads both lead back to the parking lot); the same spot twice is a slip.
            spot = (to, tuple(at) if isinstance(at, list) else at)
            if spot in seen_door:
                issues.append(f"{key}: two doors to '{to}' at the same spot {at}")
            seen_door.add(spot)
            if not (isinstance(at, list) and len(at) == 2
                    and 0 <= at[0] <= w and 0 <= at[1] <= h):
                issues.append(f"{key}: door to '{to}' at {at} outside {w}x{h}")
                continue
            if usable and min(polygon_point_distance(zone_points(z), tuple(at))
                              for z in usable) > DOOR_REACH_PX:
                issues.append(f"{key}: door to '{to}' is more than {DOOR_REACH_PX}px "
                              f"from the walkable floor")
            if d.get("status") not in STATUSES:
                issues.append(f"{key}: door to '{to}' status must be one of {STATUSES}")

        # hotspots
        ids = set()
        for hs in v.get("hotspots", []):
            hid = hs.get("id")
            if not hid or hid in ids:
                issues.append(f"{key}: hotspot id '{hid}' missing or duplicated")
            ids.add(hid)
            at = hs.get("at")
            if not (isinstance(at, list) and len(at) == 2
                    and 0 <= at[0] <= w and 0 <= at[1] <= h):
                issues.append(f"{key}: hotspot '{hid}' at {at} outside {w}x{h}")
            act = hs.get("action", {})
            if act.get("type") not in ACTION_TYPES:
                issues.append(f"{key}: hotspot '{hid}' action type must be one of "
                              f"{ACTION_TYPES}")
            if act.get("type") == "view" and act.get("view") not in {
                    x.view_id for x in room.views}:
                issues.append(f"{key}: hotspot '{hid}' goes to unknown view "
                              f"'{act.get('view')}'")
    return issues


def polygon_point_distance(poly: Sequence[Point], pt: Point) -> float:
    """0 inside the polygon, else the distance to its nearest edge."""
    if point_in_polygon(pt, poly):
        return 0.0
    return min(math.dist(pt, closest_point_on_segment(pt, poly[i], poly[(i + 1) % len(poly)]))
               for i in range(len(poly)))


# ════════════════════════════════════════════════════════════════════════════
# DRAW ORDER (2.5D)
# ════════════════════════════════════════════════════════════════════════════

def footprint_front_y(footprint: Sequence[Sequence[float]], x: float) -> Optional[float]:
    """The lowest row (nearest the camera) of a footprint polygon at column ``x`` (x is held inside the
    polygon's own width, so an avatar beside an object is compared with its nearest corner)."""
    pts = [tuple(p) for p in footprint]
    xs = [p[0] for p in pts]
    x = min(max(x, min(xs)), max(xs))
    best = None
    for i in range(len(pts)):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
        if x1 == x2:
            if x == x1:
                best = max(y1, y2) if best is None else max(best, y1, y2)
            continue
        if min(x1, x2) <= x <= max(x1, x2):
            y = y1 + (x - x1) / (x2 - x1) * (y2 - y1)
            best = y if best is None else max(best, y)
    return best


def object_base_y(occluder: dict, x: Optional[float] = None) -> Optional[float]:
    """The row where an object meets the floor. With a footprint and a column ``x`` it follows the object's
    real front edge (a slanted couch or a table turned on the diagonal); otherwise the single ``base_y``."""
    fp = occluder.get("footprint")
    if fp and x is not None:
        y = footprint_front_y(fp, x)
        if y is not None:
            return y
    return occluder.get("base_y")


def occluder_in_front(occluder: dict, feet_y: float, x: Optional[float] = None) -> bool:
    """True when the object is drawn OVER an avatar whose feet are on row
    ``feet_y`` (at column ``x`` when known): foreground objects always,
    otherwise when the avatar is further back (higher up the picture) than
    the row where the object meets the floor, i.e. walking behind it. Walking
    in front of it, the avatar is drawn over the object."""
    if occluder.get("always"):
        return True
    return feet_y < object_base_y(occluder, x)


def occluders_over(view: dict, feet_y: float, x: Optional[float] = None) -> List[dict]:
    """The occluders to paint on top of an avatar standing on row ``feet_y`` (column ``x`` when known)."""
    return [o for o in view.get("occluders", []) if occluder_in_front(o, feet_y, x)]


def blocked_at(view: dict, pt: Point) -> bool:
    """True when ``pt`` is on something solid: inside a blocker's footprint (or, for older data,
    an occluder's own footprint)."""
    solids = [b.get("footprint") for b in view.get("blockers", [])]
    solids += [o.get("footprint") for o in view.get("occluders", [])]
    return any(fp and point_in_polygon(pt, [tuple(p) for p in fp]) for fp in solids)


def _free_cells(view: dict, cell: int, with_blockers: bool):
    """Grid cells (centre points) of walkable floor, as {(i, j): (x, y)}."""
    polys = [zone_points(z) for z in view.get("zones", [])]
    if not polys:
        return {}
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    cells = {}
    for j in range(int(min(ys) // cell), int(max(ys) // cell) + 1):
        for i in range(int(min(xs) // cell), int(max(xs) // cell) + 1):
            pt = (i * cell + cell / 2, j * cell + cell / 2)
            if floor_contains(polys, pt) and not (with_blockers and blocked_at(view, pt)):
                cells[(i, j)] = pt
    return cells


def _components(cells: dict) -> Dict[Tuple[int, int], int]:
    label, n = {}, 0
    for start in cells:
        if start in label:
            continue
        n += 1
        label[start] = n
        stack = [start]
        while stack:
            i, j = stack.pop()
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    nb = (i + di, j + dj)
                    if nb in cells and nb not in label:
                        label[nb] = n
                        stack.append(nb)
    return label


def _door_component(cells: dict, label: dict, at: Point) -> Optional[int]:
    if not cells:
        return None
    best = min(cells, key=lambda c: math.dist(cells[c], at))
    return label[best]


def broken_routes(view: dict, cell: int = 5) -> List[Tuple[str, str]]:
    """Pairs of exits (by destination) that could be walked between on the bare floor but not once the
    blockers are cut out: a blocker that walls somebody in. Empty when the cut-outs leave every route open."""
    doors = view.get("doors", [])
    if len(doors) < 2:
        return []
    bare, cut = _free_cells(view, cell, False), _free_cells(view, cell, True)
    lb, lc = _components(bare), _components(cut)
    out = []
    for a in range(len(doors)):
        for b in range(a + 1, len(doors)):
            da, db = doors[a], doors[b]
            if tuple(da["at"]) == tuple(db["at"]):
                continue
            joined_bare = _door_component(bare, lb, tuple(da["at"])) == _door_component(bare, lb, tuple(db["at"]))
            joined_cut = _door_component(cut, lc, tuple(da["at"])) == _door_component(cut, lc, tuple(db["at"]))
            if joined_bare and not joined_cut:
                out.append((da["to"], db["to"]))
    return out


# ════════════════════════════════════════════════════════════════════════════
# QUESTIONS FOR JOSIE
# ════════════════════════════════════════════════════════════════════════════

def unfitted_views(data: Optional[dict] = None) -> List[str]:
    """Pictures whose avatar size is not fitted yet ("room/view")."""
    data = load() if data is None else data
    return [k for k in _all_view_sizes() if not scale_known(data.get("views", {}).get(k, {}))]


def low_confidence_views(data: Optional[dict] = None) -> List[str]:
    """Pictures sized from thin or conflicting evidence: Josie's eye decides."""
    data = load() if data is None else data
    return [k for k, v in data.get("views", {}).items()
            if scale_known(v) and (v.get("scale_info") or {}).get("confidence") == "low"]


def implied_climb_minimums(data: Optional[dict] = None) -> List[str]:
    """Facts the pictures already prove about heights that are not known yet:
    a climb that is drawn above the camera's horizon must rise past the
    camera's eye height."""
    data = load() if data is None else data
    out = []
    for key, v in data.get("views", {}).items():
        cam = camera_of(v)
        if not cam:
            continue
        horizon, eye = cam
        for z in v.get("zones", []):
            if z.get("kind") != "floor" and z.get("rise_in") is None:
                top = min(p[1] for p in z["points"])
                if top <= horizon:
                    out.append(f"{key} zone '{z['id']}': drawn up to row {top:g}, above the horizon (row "
                               f"{horizon:g}), so it must climb more than the camera's {eye:g} in")
    return out


def conflicting_views(data: Optional[dict] = None) -> List[str]:
    """Pictures where two kinds of reference disagree, so an alternative reading
    is kept next to the proposed one."""
    data = load() if data is None else data
    return [k for k, v in data.get("views", {}).items() if (v.get("scale_info") or {}).get("alt")]


def unplaced_exits(data: Optional[dict] = None) -> List[Tuple[str, str]]:
    """(picture key, destination room) for exits with no door spot yet."""
    data = load() if data is None else data
    out = []
    for r in world.WORLD.values():
        for e in r.exits:
            key = view_key(r.room_id, _exit_view(r, e)) if r.views else None
            if key is None:
                continue
            doors = {d["to"] for d in data.get("views", {}).get(key, {}).get("doors", [])}
            if e.to not in doors:
                out.append((key, e.to))
    return out


def proposed(data: Optional[dict] = None) -> List[str]:
    """Pictures still marked "proposed" (not checked by Josie)."""
    data = load() if data is None else data
    return [k for k, v in data.get("views", {}).items() if v.get("status") != "confirmed"]


def unapproved_paths(data: Optional[dict] = None) -> List[str]:
    """Pictures that have walkable outlines Josie has not approved yet (she approves the outlines on their
    own, after seeing them filled in on the picture; the picture as a whole can still be "proposed")."""
    data = load() if data is None else data
    return [k for k, v in data.get("views", {}).items()
            if v.get("zones") and v.get("pad_status", "proposed") != "confirmed"]


def unset_altitudes(data: Optional[dict] = None) -> List[str]:
    """Altitude numbers that exist but are not known yet."""
    data = load() if data is None else data
    out = []
    for key, v in data.get("views", {}).items():
        for z in v.get("zones", []):
            if z.get("kind") != "floor" and z.get("rise_in") is None:
                out.append(f"{key} zone '{z['id']}': how far the {z['kind']} climbs")
            if z.get("z_in") is None:
                out.append(f"{key} zone '{z['id']}': altitude of its start")
    for rid, z in data.get("elevations", {}).items():
        if z is None:
            out.append(f"room {rid}: altitude relative to the Palace ground floor")
    return out


def estimated_altitudes(data: Optional[dict] = None) -> List[str]:
    """Height numbers that are MY estimate, not Josie's: they are used so the pictures can be tested, and listed here
    until she confirms or corrects them."""
    data = load() if data is None else data
    out = []
    for key, v in data.get("views", {}).items():
        for z in v.get("zones", []):
            if z.get("estimated"):
                num = z.get("rise_in") if z.get("kind") != "floor" else z.get("z_in")
                what = "climb" if z.get("kind") != "floor" else "floor height"
                out.append(f"{key} zone '{z['id']}': {what} {num} in is my estimate, not confirmed")
    return out


def unlinked_zones(data: Optional[dict] = None) -> List[Tuple[str, List[List[str]]]]:
    """Pictures whose walkable zones split into groups that do not touch
    (so the avatar could not walk from one to the other)."""
    data = load() if data is None else data
    out = []
    for key, v in data.get("views", {}).items():
        zones = v.get("zones", [])
        if len(zones) > 1:
            comps = zone_components(zones)
            if len(comps) > 1:
                out.append((key, comps))
    return out


def open_questions(data: Optional[dict] = None) -> dict:
    """Everything still waiting on Josie, grouped."""
    data = load() if data is None else data
    return {
        "unapproved_pictures": proposed(data),
        "walking_paths_not_approved": unapproved_paths(data),
        "avatar_size_not_fitted": unfitted_views(data),
        "avatar_size_low_confidence": low_confidence_views(data),
        "avatar_size_references_disagree": conflicting_views(data),
        "climbs_the_pictures_already_imply": implied_climb_minimums(data),
        "doors_not_placed": unplaced_exits(data),
        "altitudes_not_known": unset_altitudes(data),
        "altitudes_estimated_not_confirmed": estimated_altitudes(data),
        "walkable_zones_that_do_not_touch": unlinked_zones(data),
    }


# ════════════════════════════════════════════════════════════════════════════
# EXPORT FOR THE VIEWER
# ════════════════════════════════════════════════════════════════════════════

def merged_world(data: Optional[dict] = None) -> dict:
    """The manifest and the placements in one JSON-ready document, for
    static/world/world.json (built by tools/build_world_json.py)."""
    data = load() if data is None else data
    out = world.to_dict()
    out["elevations"] = dict(data.get("elevations", {}))
    for room in out["rooms"]:
        for view in room["views"]:
            p = data.get("views", {}).get(view_key(room["id"], view["id"]), {})
            view["status"] = p.get("status", "proposed")
            view["pad_status"] = p.get("pad_status", "proposed")
            view["camera"] = p.get("camera")
            view["scale"] = p.get("scale", [])
            view["scale_info"] = p.get("scale_info")
            view["zones"] = p.get("zones", [])
            view["occluders"] = p.get("occluders", [])
            view["blockers"] = p.get("blockers", [])
            view["doors"] = p.get("doors", [])
            view["hotspots"] = p.get("hotspots", [])
            view["notes"] = p.get("notes", "")
    return out
