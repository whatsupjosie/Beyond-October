# PubCast AI — filler_cream_fixture.py
# Copyright © 2024–2026 Josie Curtsey Cobbley · Rearview Foresight
# Feic Mo Chroí™ — See My Heart
"""Inspectable Filler Cream proof fixture at 1/64 linear resolution.

Built as a real voxel_studio.VoxelObject so it runs through the existing
baker. Every position and size is a whole number of 1/64-block fine units
(one fine unit = 0.15625 in = 3.97 mm). Layout, fine units, +y = up:

Strip one (z 0..8), left to right along x:
  P0..P3   x 0..32    stepped contour, tops 8 / 10 / 12 / 14 (2-unit steps)
  PROT     x 32..40   protrusion, top 30 (16 above P3: a designed edge);
                      PROT_LOW under it is hidden by it
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


__all__ = ["ANNOTATIONS", "CRACK_X", "OPENING_X", "RECESS_X", "STRIP_ONE", "STRIP_TWO",
           "build_fixture_object", "fixture_annotations"]
