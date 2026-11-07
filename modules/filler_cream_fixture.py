# PubCast AI — filler_cream_fixture.py
# Copyright © 2024–2026 Josie Curtsey Cobbley · Rearview Foresight
# Feic Mo Chroí™ — See My Heart
"""Inspectable Filler Cream proof fixtures at 1/64 linear resolution.

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
OPENING_X = (56, 68)
CRACK_X = (84, 85)
RECESS_X = (40, 48)
ANNOTATIONS: Dict[str, Dict] = {"RECESS": {"tags": ["recess"]}}


def build_fixture_object(strip_two_heights: Dict[str, int] | None = None) -> VoxelObject:
    """Return the fixture VoxelObject. ``strip_two_heights`` overrides the
    y origin of Q pieces (used to prove regions do not influence each other)."""
    f = float(FINE_SUBDIVISION)
    obj = VoxelObject(object_id="filler_cream_fixture", name="filler_cream_fixture", created_at=0.0)
    overrides = dict(strip_two_heights or {})
    for pid, x, y, z, s in STRIP_ONE + STRIP_TWO:
        y = overrides.get(pid, y)
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
    return [SurfacePiece(pid, (x, top - 8, 0), (8, 8, 8), surface_id=(surf if marked else "finger"))
            for pid, x, top, surf in rows]


def curve_pieces(width: int = 2, length: int = 96):
    """A smooth bridge-like curve approximated by fine blocks sitting under
    it (block tops = floor of the true curve at each block centre)."""
    import math
    from .filler_cream import SurfacePiece
    out = []
    for i in range(length // width):
        cx = i * width + width / 2
        top = int(math.floor(true_curve(cx)))
        out.append(SurfacePiece(f"C{i}", (i * width, top - width, 0), (width, width, width)))
    return out


def true_curve(x: float) -> float:
    import math
    return 10.0 + 14.0 * math.sin(math.pi * x / 96.0) ** 2


__all__ = ["ANNOTATIONS", "CRACK_X", "OPENING_X", "RECESS_X", "STRIP_ONE", "STRIP_TWO",
           "build_fixture_object", "curve_pieces", "finger_pieces", "fixture_annotations", "true_curve"]
