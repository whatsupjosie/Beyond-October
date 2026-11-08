# PubCast AI — filler_cream_fixture.py
# Copyright © 2024–2026 Josie Curtsey Cobbley · Rearview Foresight
# Feic Mo Chroí™ — See My Heart
"""Inspectable Filler Cream proof fixtures. Designed in 1/64-block units; S scales them to the internal unit,
so they keep the same real size.

Built as a real voxel_studio.VoxelObject so it runs through the existing
baker. Every position and size is a whole number of 1/64-block fine units
(one fine unit = 0.15625 in = 3.97 mm). Layout, fine units, +y = up:

Strip one (z 0..8), left to right along x:
  P0..P3   x 0..32    stepped contour, tops 8 / 10 / 12 / 14 (2-unit steps)
  PROT     x 32..40   protrusion, top 30 (16 above P3), unmarked, so its base
                      blends; PROT_LOW under it is hidden by it
  RECESS   x 40..48   recess, top 24, tagged "recess" (6 below its sides)
  RIM      x 48..56   far wall of the recess, top 30
  opening  x 56..68   intentional opening, no pieces (12 units wide)
  P7, P8   x 68..84   tops 30 and 29 (one-unit step)
  crack    x 84..85   one-unit lateral crack
  P9       x 85..93   top 29

Strip two (z 40..48), an unrelated region:
  Q0..Q2   x 0..24    tops 8 / 11 / 13
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from .filler_cream import FINE_SUBDIVISION

# The tables below are written in 1/64-block units (the unit when they were
# designed). S converts them to the engine's internal unit, so every fixture
# keeps the same real size whatever FINE_SUBDIVISION is.
S = FINE_SUBDIVISION // 64
from .voxel_studio import VoxelObject, VoxelPrimitive, VoxelShape

# (primitive_id, x, y, z, size) in fine units
STRIP_ONE: List[Tuple[str, int, int, int, int]] = [
    ("P0", 0, 0, 0, 8), ("P1", 8, 2, 0, 8), ("P2", 16, 4, 0, 8), ("P3", 24, 6, 0, 8),
    ("PROT_LOW", 32, 14, 0, 8), ("PROT", 32, 22, 0, 8),
    ("RECESS", 40, 16, 0, 8), ("RIM", 48, 22, 0, 8),
    ("P7", 68, 22, 0, 8), ("P8", 76, 21, 0, 8), ("P9", 85, 21, 0, 8),
]
STRIP_TWO: List[Tuple[str, int, int, int, int]] = [
    ("Q0", 0, 0, 40, 8), ("Q1", 8, 3, 40, 8), ("Q2", 16, 5, 40, 8),
]
OPENING_X = (56 * S, 68 * S)
CRACK_X = (84 * S, 85 * S)
RECESS_X = (40 * S, 48 * S)
ANNOTATIONS: Dict[str, Dict] = {"RECESS": {"tags": ["recess"]}}


def build_fixture_object(strip_two_heights: Dict[str, int] | None = None) -> VoxelObject:
    """Return the fixture VoxelObject. ``strip_two_heights`` overrides the
    y origin of Q pieces (used to prove regions do not influence each other)."""
    f = float(FINE_SUBDIVISION)
    obj = VoxelObject(object_id="filler_cream_fixture", name="filler_cream_fixture", created_at=0.0)
    overrides = dict(strip_two_heights or {})
    for pid, x, y, z, s in STRIP_ONE + STRIP_TWO:
        y = overrides.get(pid, y)
        x, y, z, s = x * S, y * S, z * S, s * S
        obj.add_primitive(VoxelPrimitive(primitive_id=pid, shape=VoxelShape.CUBE, size=s / f,
                                         position=(x / f, y / f, z / f)))
    return obj


def fixture_annotations(recess_tagged: bool = True) -> Dict[str, Dict]:
    return dict(ANNOTATIONS) if recess_tagged else {}





def finger_pieces(marked: bool = True):
    """Fingertip profile along x (fine units, +y up), one row z 0..8:
    skin tops 20/21/22/22, a drop onto the nail (21/21/20), the nail's free
    edge at x=56, then the fingertip below it (17/16). With ``marked`` the
    nail is its own surface, so cream never crosses skin<->nail."""
    from .filler_cream import SurfacePiece
    rows = [("S0", 0, 20, "skin"), ("S1", 8, 21, "skin"), ("S2", 16, 22, "skin"), ("S3", 24, 22, "skin"),
            ("N0", 32, 21, "nail"), ("N1", 40, 21, "nail"), ("N2", 48, 20, "nail"),
            ("T0", 56, 17, "skin"), ("T1", 64, 16, "skin")]
    return [SurfacePiece(pid, (x * S, (top - 8) * S, 0), (8 * S, 8 * S, 8 * S), surface_id=(surf if marked else "finger"))
            for pid, x, top, surf in rows]


def curve_pieces(width: int = 2 * S, length: int = 96 * S):
    """A smooth bridge-like curve approximated by fine blocks sitting under
    it (block tops = floor of the true curve at each block centre)."""
    import math
    from .filler_cream import SurfacePiece
    out = []
    for i in range(length // width):
        cx = i * width + width / 2
        top = S * int(math.floor(true_curve(cx) / S))   # blocks stay 1/64 steps, as designed
        out.append(SurfacePiece(f"C{i}", (i * width, top - width, 0), (width, width, width)))
    return out


def true_curve(x: float) -> float:
    """The intended curve, in internal fine units (designed in 1/64 units)."""
    import math
    return S * (10.0 + 14.0 * math.sin(math.pi * (x / S) / 96.0) ** 2)





def lip_and_lid_pieces(step: int):
    """A lip edge and an eyelid crease, built from blocks ``step`` internal
    units wide (1 = 1/128 block, about 2 mm; 2 = 1/64, about 4 mm).
    Profile along x, one row 8 units deep (fine units, +y up):
      skin above the lip  x 0..12   surface "skin"
      upper lip           x 12..32  surface "lip_upper", rolling out from a
                                    designed border at x = 12
      eyelid              x 40..60  surface "lid"
      crease              x 60..62  tagged "edge" (the designed fold)
      brow skin           x 62..82  surface "brow"
    Block tops are the true curve rounded down to whole blocks."""
    import math
    from .filler_cream import SurfacePiece
    pieces = []

    def run(prefix, x0, x1, surface, curve, tags=frozenset()):
        for x in range(x0, x1, step):
            top = step * int(math.floor(curve(x + step / 2.0) / step))
            pieces.append(SurfacePiece(f"{prefix}{x}", (x, top - 8, 0), (step, 8, 8), surface_id=surface, tags=tags))

    run("skin", 0, 12, "skin", lip_true_curve)
    run("lip", 12, 32, "lip_upper", lip_true_curve)
    run("lid", 40, 60, "lid", lip_true_curve)
    run("crease", 60, 62, "lid", lip_true_curve, frozenset({"edge"}))
    run("brow", 62, 82, "brow", lip_true_curve)
    return pieces


def lip_true_curve(x: float) -> float:
    """The designed profile (fine units) for lip_and_lid_pieces."""
    import math
    if x < 12:
        return 20.0 + 0.25 * x
    if x < 32:
        return 25.0 + 4.0 * math.sin(math.pi * (x - 12) / 20.0)
    if x < 60:
        return 22.0 + 3.0 * math.sin(math.pi * (x - 40) / 40.0)
    if x < 62:
        return 21.0
    return 21.0 + 0.2 * (x - 62)


__all__ = ["ANNOTATIONS", "CRACK_X", "OPENING_X", "RECESS_X", "STRIP_ONE", "STRIP_TWO",
           "build_fixture_object", "lip_and_lid_pieces", "lip_true_curve", "curve_pieces", "finger_pieces", "fixture_annotations", "true_curve"]
