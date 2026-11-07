# PubCast AI — filler_cream.py
# Copyright © 2024–2026 Josie Curtsey Cobbley · Rearview Foresight
# Feic Mo Chroí™ — See My Heart
"""Filler Cream — bounded local filling between neighbouring surface pieces.

The voxel blueprint sets the shape. Filler Cream only finishes the surface
between neighbouring surface pieces inside a selected region, from the base
of those pieces up to (never beyond) the local contour they define.

Units
-----
Existing PubCast terminology (verified in modules/voxel_set_contract.py and
modules/voxel_studio.py): one PubBlock is 10 inches (0.254 m); subdivisions
are full = 1, half = 2, quarter = 4. VoxelStudio sizes are floats in block
units (1.0 / 0.5 / 0.25). The experimental fine resolution used here is
1/64 of a block edge: FINE_SUBDIVISION = 64, one fine unit = 0.15625 inch
= 3.96875 mm. All core geometry is integer fine units. The canonical voxel
set contract still rejects subdivision 64; this module does not change it.

Design rule (Josie, 2026-11-06)
-------------------------------
The blueprint describes the real (or stylised) object; voxels are always an
approximation of it. So every voxel step is treated as approximation and
smoothed, unless the blueprint marks it as designed: a keep tag (preserve,
recess, protrusion, edge, opening), a different surface_id (skin vs nail,
upper vs lower eyelid) or an explicit barrier pair. Step size alone never
protects or exposes anything (max_step exists only as an explicit override).

Local best-fit rule (documented limits in docs/FILLER_CREAM.md)
----------------------------------------------------------------
Work is done on one exposed face orientation at a time (``+y`` = tops).
The selection is rasterised into columns; each column has an owner (the
outermost piece over it) and a surface height H.

1. Fit. For a column c, gather the columns reachable from c without
   crossing a marked edge, within the fidelity radius R (half the fidelity
   span). Fit a weighted least-squares plane to their heights (weight falls
   off linearly with distance, so neighbouring fits blend with no creases)
   and read it at c. The cream target is that value, capped at the highest
   height in the neighbourhood. Cream fills from H(c) up to the target.
   Where the fit runs below a block corner the corner stays: removing it is
   sanding, not filling.
2. Crack. An empty run of columns between two eligible pieces no wider
   than max_gap fine units is filled from the shell base (max of the two
   pieces' bases) up to the straight line between the two surfaces. Wider
   empty runs are openings and stay empty.

Fidelity is tied to real size through the PubBlock: very_high 3/64 block,
high 1/8, medium 1/4, low 1/2, very_low 1 block, or any span in mm. Each
blueprint part may carry a fidelity; the selection (applicator) may
override it for one application. Short spans follow fine features (nose);
long spans give broad, even curves (belly, floor).

Each filler value depends only on columns within R of it, reached without
crossing a marked edge, so the nose tip cannot affect the eye corner. A
larger selection means more local fits, never wider ones.

The original pieces are never modified. Filler lives in a separate
FillerLayer that is computed from the original pieces only (it never reads
existing filler), so regeneration is deterministic and cannot accumulate.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .voxel_set_contract import PUB_BLOCK_INCHES, PUB_BLOCK_METERS  # the block's real size lives there

FINE_SUBDIVISION = 64
FINE_UNIT_INCHES = PUB_BLOCK_INCHES / FINE_SUBDIVISION   # 0.15625 for the 10 in block
FINE_UNIT_MM = PUB_BLOCK_METERS * 1000.0 / FINE_SUBDIVISION  # 3.96875
# Fidelity stops as fractions of one PubBlock edge (span of one best fit).
FIDELITY_STOPS: Dict[str, float] = {
    "very_high": 3 / 64, "high": 1 / 8, "medium": 1 / 4, "low": 1 / 2, "very_low": 1.0,
}
DEFAULT_FIDELITY = "medium"

FACES: Dict[str, Tuple[int, int]] = {
    "+x": (0, 1), "-x": (0, -1),
    "+y": (1, 1), "-y": (1, -1),
    "+z": (2, 1), "-z": (2, -1),
}
SUPPORTED_SHAPES = {"cube", "wedge"}
WEDGE_HIGH_SIDES = {"-x", "+x", "-z", "+z"}
KEEP_TAGS = frozenset({"preserve", "recess", "protrusion", "edge", "opening"})
_EPS = 1e-9
_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class FillerCreamError(ValueError):
    """Raised when pieces or a selection cannot be processed safely."""


def fidelity_span_fine(fidelity: Any) -> float:
    """Span of one best fit in fine units. Accepts a stop name or mm."""
    if fidelity is None:
        fidelity = DEFAULT_FIDELITY
    if isinstance(fidelity, str):
        if fidelity not in FIDELITY_STOPS:
            raise FillerCreamError(f"fidelity must be one of {sorted(FIDELITY_STOPS)} or a span in mm")
        return FIDELITY_STOPS[fidelity] * FINE_SUBDIVISION
    if isinstance(fidelity, bool) or not isinstance(fidelity, (int, float)) or fidelity <= 0:
        raise FillerCreamError("fidelity span in mm must be a positive number")
    return float(fidelity) / FINE_UNIT_MM


# ══════════════════════════════════════════════════════════════════════════
# INPUT MODEL
# ══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SurfacePiece:
    """One surface voxel piece as an axis-aligned box in integer fine units.

    shape "cube": flat-faced box. shape "wedge": +y top slopes linearly from
    full height on ``wedge_high_side`` down to the piece's bottom on the
    opposite side (VoxelStudio's wedge). Any other shape is kept as an
    occluder only: it owns columns but never receives or anchors filler.
    """

    piece_id: str
    origin: Tuple[int, int, int]
    size: Tuple[int, int, int]
    shape: str = "cube"
    wedge_high_side: Optional[str] = None
    surface_id: str = "default"
    tags: frozenset = frozenset()
    fidelity: Any = None   # stop name or span in mm; None = DEFAULT_FIDELITY

    def __post_init__(self) -> None:
        fidelity_span_fine(self.fidelity)  # validate early
        if not isinstance(self.piece_id, str) or not self.piece_id:
            raise FillerCreamError("piece_id must be a non-empty string")
        for name, vec in (("origin", self.origin), ("size", self.size)):
            if len(vec) != 3 or any(isinstance(v, bool) or int(v) != v for v in vec):
                raise FillerCreamError(f"{self.piece_id}: {name} must be three integers (fine units)")
        if any(int(v) <= 0 for v in self.size):
            raise FillerCreamError(f"{self.piece_id}: size must be positive")
        if self.shape == "wedge" and self.wedge_high_side not in WEDGE_HIGH_SIDES:
            raise FillerCreamError(f"{self.piece_id}: wedge needs wedge_high_side in {sorted(WEDGE_HIGH_SIDES)}")
        object.__setattr__(self, "origin", tuple(int(v) for v in self.origin))
        object.__setattr__(self, "size", tuple(int(v) for v in self.size))
        object.__setattr__(self, "tags", frozenset(str(t) for t in self.tags))

    def supports(self, face: str) -> bool:
        if self.shape == "cube":
            return True
        if self.shape == "wedge":
            return face == "+y"
        return False

    def keep(self) -> bool:
        return bool(self.tags & KEEP_TAGS)

    def outward_span(self, up: int, sign: int) -> Tuple[float, float]:
        """(base, top) along the face normal in outward coordinates."""
        lo = self.origin[up]
        hi = lo + self.size[up]
        return (float(lo), float(hi)) if sign > 0 else (float(-hi), float(-lo))

    def top_at(self, up: int, sign: int, point: Mapping[int, float]) -> float:
        """Outward surface height at an in-plane point (fine units)."""
        base, top = self.outward_span(up, sign)
        if self.shape != "wedge" or not (up == 1 and sign > 0):
            return top
        side = self.wedge_high_side
        axis = 0 if side.endswith("x") else 2
        frac = (point[axis] - self.origin[axis]) / self.size[axis]
        frac = min(1.0, max(0.0, frac))
        rise = (1.0 - frac) if side.startswith("-") else frac
        return base + self.size[1] * rise


@dataclass(frozen=True)
class FillerSelection:
    """The application region and its rules.

    piece_ids  — selected surface pieces (one face, one voxel, or a group).
    face       — exposed face orientation the cream is applied to.
    barriers   — explicit do-not-bridge pairs of piece ids.
    fidelity   — applicator override (stop name or mm) for this application;
                 None = each piece's own fidelity.
    max_step   — optional explicit override: steps taller than this (fine
                 units) are not crossed. None (default) = the blueprint marks
                 decide, not step size.
    max_gap    — widest lateral crack (fine units) that is filled; wider
                 empty runs are openings.
    ramp_samples — minimum columns across the smallest piece when choosing
                 the working grid.
    """

    piece_ids: frozenset
    face: str = "+y"
    barriers: frozenset = frozenset()
    max_step: Optional[int] = None
    max_gap: int = 2
    ramp_samples: int = 8
    fidelity: Any = None

    def __post_init__(self) -> None:
        if self.fidelity is not None:
            fidelity_span_fine(self.fidelity)
        if self.face not in FACES:
            raise FillerCreamError(f"face must be one of {sorted(FACES)}")
        object.__setattr__(self, "piece_ids", frozenset(str(p) for p in self.piece_ids))
        object.__setattr__(self, "barriers", frozenset(frozenset(str(x) for x in pair) for pair in self.barriers))
        if not self.piece_ids:
            raise FillerCreamError("selection is empty")
        if self.max_step is not None and int(self.max_step) <= 0:
            raise FillerCreamError("max_step must be positive")
        if int(self.max_gap) < 0 or int(self.ramp_samples) < 1:
            raise FillerCreamError("max_gap must be >= 0 and ramp_samples >= 1")

    def key(self) -> str:
        payload = {
            "piece_ids": sorted(self.piece_ids), "face": self.face,
            "barriers": sorted(sorted(p) for p in self.barriers),
            "max_step": self.max_step, "max_gap": int(self.max_gap),
            "ramp_samples": int(self.ramp_samples), "fidelity": self.fidelity,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════════════════
# OUTPUT MODEL
# ══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FillerCell:
    column: Tuple[int, int]
    base: float          # outward fine units
    top: float           # outward fine units, > base
    sources: Tuple[str, ...]   # pieces whose heights shaped this cell
    kind: str                  # "fit" | "crack"


@dataclass(frozen=True)
class FillerLayer:
    """Removable, regenerable filler. Never merged into the voxel source."""

    face: str
    grid_unit: int
    cells: Tuple[FillerCell, ...]
    selection_key: str

    def boxes(self) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
        """Axis-aligned filler boxes (min, max) in fine units, real axes."""
        up, sign = FACES[self.face]
        a, b = _plane_axes(up)
        g = self.grid_unit
        out = []
        for cell in self.cells:
            i, j = cell.column
            lo = [0.0, 0.0, 0.0]
            hi = [0.0, 0.0, 0.0]
            lo[a], hi[a] = float(i * g), float((i + 1) * g)
            lo[b], hi[b] = float(j * g), float((j + 1) * g)
            if sign > 0:
                lo[up], hi[up] = cell.base, cell.top
            else:
                lo[up], hi[up] = -cell.top, -cell.base
            out.append((tuple(lo), tuple(hi)))
        return out

    def volume(self) -> float:
        g2 = float(self.grid_unit * self.grid_unit)
        return sum((c.top - c.base) * g2 for c in self.cells)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "filler_cream_layer", "version": 1,
            "face": self.face, "grid_unit": self.grid_unit,
            "fine_subdivision": FINE_SUBDIVISION, "selection_key": self.selection_key,
            "cells": [
                {"column": list(c.column), "base": round(c.base, 9), "top": round(c.top, 9),
                 "sources": list(c.sources), "kind": c.kind}
                for c in self.cells
            ],
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "FillerLayer":
        if d.get("kind") != "filler_cream_layer" or int(d.get("version", 0)) != 1:
            raise FillerCreamError("not a filler_cream_layer v1 payload")
        cells = tuple(
            FillerCell(tuple(c["column"]), float(c["base"]), float(c["top"]), tuple(c["sources"]), str(c["kind"]))
            for c in d["cells"]
        )
        return cls(str(d["face"]), int(d["grid_unit"]), cells, str(d["selection_key"]))

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()


# ══════════════════════════════════════════════════════════════════════════
# CORE OPERATION
# ══════════════════════════════════════════════════════════════════════════

def _plane_axes(up: int) -> Tuple[int, int]:
    a, b = [ax for ax in (0, 1, 2) if ax != up]
    return a, b


def compute_filler(pieces: Iterable[SurfacePiece], selection: FillerSelection) -> FillerLayer:
    """Generate bounded filler for one selection. Pure and deterministic.

    ``pieces`` is the whole construction (selected and unselected); only
    pieces near the selection are rasterised. Pieces are never modified.
    """
    by_id: Dict[str, SurfacePiece] = {}
    for p in pieces:
        if p.piece_id in by_id:
            raise FillerCreamError(f"duplicate piece_id {p.piece_id!r}")
        by_id[p.piece_id] = p
    missing = sorted(selection.piece_ids - set(by_id))
    if missing:
        raise FillerCreamError(f"selected pieces not found: {missing[:5]}")

    face = selection.face
    up, sign = FACES[face]
    a, b = _plane_axes(up)
    max_gap = int(selection.max_gap)

    # ── 1. candidate pieces: selection bbox expanded by max_gap ───────────
    sel = [by_id[pid] for pid in sorted(selection.piece_ids)]
    a0 = min(p.origin[a] for p in sel) - max_gap - 1
    a1 = max(p.origin[a] + p.size[a] for p in sel) + max_gap + 1
    b0 = min(p.origin[b] for p in sel) - max_gap - 1
    b1 = max(p.origin[b] + p.size[b] for p in sel) + max_gap + 1
    cands = [
        p for pid, p in sorted(by_id.items())
        if p.origin[a] < a1 and p.origin[a] + p.size[a] > a0
        and p.origin[b] < b1 and p.origin[b] + p.size[b] > b0
    ]

    # ── 2. fidelity radius per piece, then the working grid ──────────────
    def radius(p: SurfacePiece) -> float:
        span = fidelity_span_fine(selection.fidelity if selection.fidelity is not None else p.fidelity)
        return span / 2.0

    g = 0
    for p in cands:
        for v in (p.origin[a], p.size[a], p.origin[b], p.size[b]):
            g = math.gcd(g, abs(v))
    min_plane = min(min(p.size[a], p.size[b]) for p in sel)
    min_radius = min(radius(p) for p in sel)
    g = math.gcd(g, max(1, min_plane // int(selection.ramp_samples))) if g else 1
    g = math.gcd(g, max(1, int(min_radius)))  # at least ~2 columns across the finest fit
    g = max(1, g)

    # ── 3. rasterise: outermost piece owns each column ───────────────────
    owner: Dict[Tuple[int, int], str] = {}
    height: Dict[Tuple[int, int], float] = {}
    for p in cands:
        for i in range(p.origin[a] // g, (p.origin[a] + p.size[a]) // g):
            for j in range(p.origin[b] // g, (p.origin[b] + p.size[b]) // g):
                pt = {a: (i + 0.5) * g, b: (j + 0.5) * g}
                h = p.top_at(up, sign, pt)
                col = (i, j)
                cur = owner.get(col)
                if cur is None or h > height[col] + _EPS or (abs(h - height[col]) <= _EPS and p.piece_id < cur):
                    owner[col] = p.piece_id
                    height[col] = h

    selected = selection.piece_ids

    def eligible(pa: str, pb: str) -> bool:
        if pa == pb or pa not in selected or pb not in selected:
            return False
        A, B = by_id[pa], by_id[pb]
        if not (A.supports(face) and B.supports(face)) or A.keep() or B.keep():
            return False
        if A.surface_id != B.surface_id:
            return False
        return frozenset((pa, pb)) not in selection.barriers

    def fillable(pid: str) -> bool:
        P = by_id[pid]
        return pid in selected and P.supports(face) and not P.keep()

    def connected(x: Tuple[int, int], y: Tuple[int, int]) -> bool:
        """May a fit reach from column x to its 4-neighbour y?"""
        py = owner.get(y)
        if py is None or not fillable(py):
            return False
        px = owner[x]
        if px != py and not eligible(px, py):
            return False
        if selection.max_step is not None and abs(height[y] - height[x]) > selection.max_step + _EPS:
            return False
        return True

    best: Dict[Tuple[int, int], FillerCell] = {}

    def offer(col: Tuple[int, int], base: float, top: float, src: Tuple[str, ...], kind: str) -> None:
        if top <= base + _EPS:
            return
        prev = best.get(col)
        if prev is None or top > prev.top + _EPS:
            best[col] = FillerCell(col, base, top, src, kind)

    # ── 4. candidates: columns within reach of a higher connected neighbour
    #       (a level surface does no work at all) ─────────────────────────
    frontier: List[Tuple[Tuple[int, int], float]] = []
    for col in sorted(owner):
        if not fillable(owner[col]):
            continue
        for d in _DIRS:
            nb = (col[0] + d[0], col[1] + d[1])
            if connected(col, nb) and height[nb] > height[col] + _EPS:
                frontier.append((col, radius(by_id[owner[col]])))
                break
    candidates: Dict[Tuple[int, int], None] = {}
    for src_col, r in frontier:
        reach = r + g
        seen = {src_col}
        stack = [src_col]
        while stack:
            x = stack.pop()
            candidates[x] = None
            for d in _DIRS:
                y = (x[0] + d[0], x[1] + d[1])
                if y in seen or not connected(x, y):
                    continue
                if math.hypot((y[0] - src_col[0]) * g, (y[1] - src_col[1]) * g) > reach:
                    continue
                seen.add(y)
                stack.append(y)

    # ── 5. local weighted best fit at each candidate column ──────────────
    import numpy as np

    for col in sorted(candidates):
        r = radius(by_id[owner[col]])
        reach = r + 0.5 * g
        seen = {col}
        stack = [col]
        pts: List[Tuple[float, float, float, float]] = []
        srcs = set()
        while stack:
            x = stack.pop()
            du, dv = (x[0] - col[0]) * g, (x[1] - col[1]) * g
            w = 1.0 - math.hypot(du, dv) / (reach + g)
            pts.append((du, dv, height[x], w))
            srcs.add(owner[x])
            for d in _DIRS:
                y = (x[0] + d[0], x[1] + d[1])
                if y in seen or not connected(x, y):
                    continue
                if math.hypot((y[0] - col[0]) * g, (y[1] - col[1]) * g) > reach:
                    continue
                seen.add(y)
                stack.append(y)
        if len(pts) < 2:
            continue
        arr = np.array(sorted(pts), dtype=float)
        sw = np.sqrt(arr[:, 3])
        design = np.column_stack([np.ones(len(arr)), arr[:, 0], arr[:, 1]]) * sw[:, None]
        coef, *_ = np.linalg.lstsq(design, arr[:, 2] * sw, rcond=None)
        target = min(float(coef[0]), float(arr[:, 2].max()))
        offer(col, height[col], target, tuple(sorted(srcs)), "fit")

    # ── 6. cracks: short empty runs between two eligible pieces ──────────
    max_cols = max_gap // g
    if max_cols >= 1:
        for col in sorted(owner):
            pa = owner[col]
            if pa not in selected:
                continue
            for d in ((1, 0), (0, 1)):
                first = (col[0] + d[0], col[1] + d[1])
                if first in owner:
                    continue
                k, far = 1, None
                while k <= max_cols + 1:
                    probe = (col[0] + d[0] * k, col[1] + d[1] * k)
                    if probe in owner:
                        far = probe
                        break
                    k += 1
                if far is None:
                    continue
                gap_cols = k - 1
                if gap_cols < 1 or gap_cols > max_cols:
                    continue
                pb = owner[far]
                if not eligible(pa, pb):
                    continue
                ha, hb = height[col], height[far]
                if selection.max_step is not None and abs(hb - ha) > selection.max_step + _EPS:
                    continue
                base = max(by_id[pa].outward_span(up, sign)[0], by_id[pb].outward_span(up, sign)[0])
                src = (pa, pb) if pa < pb else (pb, pa)
                for s in range(1, gap_cols + 1):
                    gc = (col[0] + d[0] * s, col[1] + d[1] * s)
                    offer(gc, base, ha + (hb - ha) * s / (gap_cols + 1), src, "crack")

    cells = tuple(best[c] for c in sorted(best))
    return FillerLayer(face, g, cells, selection.key())


class FillerCreamLayers:
    """Named filler layers kept apart from the voxel source record.

    apply() replaces a layer (never adds to it); remove() drops it. Because
    compute_filler reads only the original pieces, re-applying is idempotent.
    """

    def __init__(self) -> None:
        self._layers: Dict[str, FillerLayer] = {}

    def apply(self, name: str, pieces: Iterable[SurfacePiece], selection: FillerSelection) -> FillerLayer:
        layer = compute_filler(pieces, selection)
        self._layers[str(name)] = layer
        return layer

    def remove(self, name: str) -> bool:
        return self._layers.pop(str(name), None) is not None

    def clear(self) -> None:
        self._layers.clear()

    def layers(self) -> List[FillerLayer]:
        return [self._layers[k] for k in sorted(self._layers)]

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "filler_cream_layers", "version": 1,
                "layers": {k: v.to_dict() for k, v in sorted(self._layers.items())}}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "FillerCreamLayers":
        out = cls()
        for k, v in dict(d.get("layers") or {}).items():
            out._layers[str(k)] = FillerLayer.from_dict(v)
        return out


# ══════════════════════════════════════════════════════════════════════════
# ADAPTERS — existing PubCast voxel representations → SurfacePiece
# ══════════════════════════════════════════════════════════════════════════

def _to_fine(value: float, what: str) -> int:
    scaled = float(value) * FINE_SUBDIVISION
    rounded = round(scaled)
    if abs(scaled - rounded) > 1e-6:
        raise FillerCreamError(f"{what}={value} is not a multiple of 1/{FINE_SUBDIVISION} block")
    return int(rounded)


def pieces_from_voxel_object(obj: Any, annotations: Optional[Mapping[str, Mapping[str, Any]]] = None
                             ) -> Tuple[List[SurfacePiece], List[str]]:
    """Convert a voxel_studio.VoxelObject into SurfacePieces.

    Positions/sizes are block units (1.0 = 10 in). Supported: cubes at 90°
    rotations, wedges rotated only about Y in 90° steps. Corner cuts and
    other rotations become occluders (never filled, never anchor filler).
    ``annotations`` maps primitive_id → {"surface_id": str, "tags": [...],
    "fidelity": stop name or mm};
    the default surface_id is the primitive's pivot group or "body".
    Returns (pieces, notes).
    """
    notes: List[str] = []
    ann = dict(annotations or {})
    pieces: List[SurfacePiece] = []
    wedge_sides = {0: "-x", 90: "+z", 180: "+x", 270: "-z"}  # matches build_primitive_geometry rot_y
    for prim in obj.primitives:
        shape = getattr(prim.shape, "value", prim.shape)
        s = _to_fine(prim.size, f"{prim.primitive_id}.size")
        origin = tuple(_to_fine(v, f"{prim.primitive_id}.position") for v in prim.position)
        quarter_turns = [float(r) / 90.0 for r in prim.rotation_deg]
        right_angles = all(abs(q - round(q)) < 1e-6 for q in quarter_turns)
        rot = [int(round(q)) % 4 * 90 for q in quarter_turns]
        meta = dict(ann.get(prim.primitive_id) or {})
        surface_id = str(meta.get("surface_id") or prim.group or "body")
        tags = frozenset(meta.get("tags") or ())
        kind, high = "occluder", None
        if shape == "cube" and right_angles:
            kind = "cube"
        elif shape == "wedge" and right_angles and rot[0] == 0 and rot[2] == 0:
            kind, high = "wedge", wedge_sides[rot[1]]
        if kind == "occluder":
            notes.append(f"{prim.primitive_id}: {shape} rot={list(prim.rotation_deg)} kept as occluder (not filled)")
        pieces.append(SurfacePiece(prim.primitive_id, origin, (s, s, s), kind, high, surface_id, tags,
                                   meta.get("fidelity")))
    return pieces, notes


def pieces_from_voxel_set(voxel_set: Mapping[str, Any]) -> List[SurfacePiece]:
    """Convert a canonical voxel set (voxel_set_contract) into SurfacePieces.

    Block metadata: ``surface_id`` (else ``part``, else "default") and
    ``filler_tags`` (list) or ``filler: "preserve"``, and ``fidelity``.
    """
    from .voxel_set_contract import normalize_voxel_set

    normalized = normalize_voxel_set(voxel_set)
    sub = int(normalized["measurement"]["subdivision"])
    if FINE_SUBDIVISION % sub:
        raise FillerCreamError(f"subdivision {sub} does not divide {FINE_SUBDIVISION}")
    k = FINE_SUBDIVISION // sub
    out = []
    for blk in normalized["blocks"]:
        meta = blk.get("metadata") or {}
        tags = set(meta.get("filler_tags") or ())
        if meta.get("filler") == "preserve":
            tags.add("preserve")
        out.append(SurfacePiece(
            f"b:{blk['x']},{blk['y']},{blk['z']}",
            (blk["x"] * k, blk["y"] * k, blk["z"] * k), (k, k, k), "cube", None,
            str(meta.get("surface_id") or meta.get("part") or "default"), frozenset(tags),
            meta.get("fidelity"),
        ))
    return out


# ══════════════════════════════════════════════════════════════════════════
# MESH — feed filler into the existing VoxelStudio GLB pipeline
# ══════════════════════════════════════════════════════════════════════════

def filler_mesh_arrays(layers: Sequence[FillerLayer], world_position=(0.0, 0.0, 0.0)):
    """(verts, normals, faces) for filler boxes in block units, built with
    voxel_studio's own cube table and flat-normal routine."""
    import numpy as np
    from .voxel_studio import VoxelShape, _compute_normals, _shape_verts_faces

    unit_v, unit_f = _shape_verts_faces(VoxelShape.CUBE)
    scale = 1.0 / FINE_SUBDIVISION
    wp = np.array(world_position, dtype=float)
    verts, faces, n = [], [], 0
    for layer in layers:
        for lo, hi in layer.boxes():
            lo_b = np.array(lo) * scale
            ext = (np.array(hi) - np.array(lo)) * scale
            verts.append(unit_v * ext + lo_b + wp)
            faces.append(unit_f + n)
            n += len(unit_v)
    if not verts:
        return (np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32), np.zeros((0, 3), np.uint32))
    return _compute_normals(np.concatenate(verts), np.concatenate(faces))


def parse_glb(data: bytes):
    """Read POSITION/NORMAL/indices back out of a VoxelStudio GLB."""
    import numpy as np

    magic, version, total = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2:
        raise FillerCreamError("not a glTF 2.0 binary")
    jlen, _ = struct.unpack_from("<II", data, 12)
    # voxel_studio.pack_glb pads the JSON chunk with NUL bytes (spec: spaces)
    gltf = json.loads(data[20:20 + jlen].rstrip(b"\x00 ").decode())
    blen, _ = struct.unpack_from("<II", data, 20 + jlen)
    bin_data = data[28 + jlen:28 + jlen + blen]
    prim = gltf["meshes"][0]["primitives"][0]

    def read(acc_idx, dtype, width):
        acc = gltf["accessors"][acc_idx]
        view = gltf["bufferViews"][acc["bufferView"]]
        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        count = acc["count"] * width
        arr = np.frombuffer(bin_data, dtype=dtype, count=count, offset=start)
        return arr.reshape(-1, width) if width > 1 else arr

    verts = read(prim["attributes"]["POSITION"], np.float32, 3)
    normals = read(prim["attributes"]["NORMAL"], np.float32, 3)
    faces = read(prim["indices"], np.uint32, 1).reshape(-1, 3)
    return verts.copy(), normals.copy(), faces.copy()


def bake_with_filler(obj: Any, layers: Sequence[FillerLayer], world_position=(0.0, 0.0, 0.0)) -> bytes:
    """Bake obj with the existing VoxelBaker, then append filler geometry.

    With no filler cells this returns exactly VoxelBaker().bake(obj) bytes.
    The VoxelObject is never modified.
    """
    import numpy as np
    from .voxel_studio import VoxelBaker, pack_glb

    base = VoxelBaker().bake(obj, world_position)
    fv, fn, ff = filler_mesh_arrays(layers, world_position)
    if len(ff) == 0:
        return base
    bv, bn, bf = parse_glb(base)
    verts = np.concatenate([bv, fv]).astype(np.float32)
    normals = np.concatenate([bn, fn]).astype(np.float32)
    faces = np.concatenate([bf, ff + len(bv)]).astype(np.uint32)
    return pack_glb(verts, normals, faces, obj.name)


__all__ = [
    "DEFAULT_FIDELITY", "FACES", "FIDELITY_STOPS", "FINE_SUBDIVISION", "fidelity_span_fine", "FINE_UNIT_INCHES", "FINE_UNIT_MM", "KEEP_TAGS",
    "FillerCell", "FillerCreamError", "FillerCreamLayers", "FillerLayer", "FillerSelection",
    "SurfacePiece", "bake_with_filler", "compute_filler", "filler_mesh_arrays", "parse_glb",
    "pieces_from_voxel_object", "pieces_from_voxel_set",
]
