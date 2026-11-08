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
units (1.0 / 0.5 / 0.25). The internal unit is 1/128 of a block edge (FINE_SUBDIVISION = 128, one fine
unit = 0.078125 inch = 1.984 mm; it was 1/64 until 2026-11-08). 1/64 work uses
even numbers. All core geometry is integer fine units. The canonical voxel
set contract accepts 64 and 128 since 2026-11-08.

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
   then lift it, keeping its slope, until it rests on the outermost block
   point in the neighbourhood (the voxel points set the surface; cream is
   wiped flush with them, like wood filler). Read it at c, capped at the
   highest height in the neighbourhood. Cream fills from H(c) up to that.
   Sanding (a separate tool, not built) removes material for finer angles.
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

# Internal unit: 1/128 block (about 2 mm), so Primp faces and close-ups can use
# 1/128 pieces (Josie, 2026-11-08). 1/64 work is unchanged: it simply uses even
# numbers internally. Was 1/64 until 2026-11-08.
FINE_SUBDIVISION = 128
LEGACY_FINE_SUBDIVISION = 64                               # unit of payloads saved before 2026-11-08
FINE_UNIT_INCHES = PUB_BLOCK_INCHES / FINE_SUBDIVISION     # 0.078125 for the 10 in block
FINE_UNIT_MM = PUB_BLOCK_METERS * 1000.0 / FINE_SUBDIVISION  # 1.984375
DEFAULT_MAX_GAP = FINE_SUBDIVISION // 32                   # 1/32 block, about 8 mm (unchanged in real size)
# Fidelity stops as fractions of one PubBlock edge (span of one best fit).
FIDELITY_STOPS: Dict[str, float] = {
    "very_high": 3 / 64, "high": 1 / 8, "medium": 1 / 4, "low": 1 / 2, "very_low": 1.0,
}
DEFAULT_FIDELITY = "medium"
# Bump whenever the cream rule changes, so saved layers made under an older
# rule are reported stale instead of looking current.
ENGINE_VERSION = "filler-cream/6 outer-points-fade, ceiling-cap, local-claim, diagonal-cracks, unit-1/128, real-size-grid"
MAX_SOURCES_PER_CELL = 16

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
                 empty runs are openings. Default 1/32 block (about 8 mm).
    grid_samples — minimum columns across the smallest piece when choosing
                 the working grid.
    """

    piece_ids: frozenset
    face: str = "+y"
    barriers: frozenset = frozenset()
    max_step: Optional[int] = None
    max_gap: int = DEFAULT_MAX_GAP
    grid_samples: int = 8
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
        if int(self.max_gap) < 0 or int(self.grid_samples) < 1:
            raise FillerCreamError("max_gap must be >= 0 and grid_samples >= 1")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "piece_ids": sorted(self.piece_ids), "face": self.face,
            "barriers": sorted(sorted(p) for p in self.barriers),
            "max_step": self.max_step, "max_gap": int(self.max_gap),
            "grid_samples": int(self.grid_samples), "fidelity": self.fidelity,
            "fine_subdivision": FINE_SUBDIVISION,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "FillerSelection":
        """Lengths saved in another unit (payloads from before 2026-11-08 were
        1/64 and carry no unit) are converted, so they keep their real size."""
        saved_fine = int(d.get("fine_subdivision", LEGACY_FINE_SUBDIVISION))
        k = FINE_SUBDIVISION / saved_fine

        def length(v, default):
            return default if v is None else max(0, int(round(float(v) * k)))

        max_step = d.get("max_step")
        return cls(frozenset(d["piece_ids"]), str(d.get("face", "+y")),
                   frozenset(frozenset(p) for p in d.get("barriers") or ()),
                   None if max_step is None else max(1, length(max_step, None)),
                   length(d.get("max_gap"), DEFAULT_MAX_GAP),
                   int(d.get("grid_samples", d.get("ramp_samples", 8))), d.get("fidelity"))

    def key(self) -> str:
        payload = {
            "piece_ids": sorted(self.piece_ids), "face": self.face,
            "barriers": sorted(sorted(p) for p in self.barriers),
            "max_step": self.max_step, "max_gap": int(self.max_gap),
            "grid_samples": int(self.grid_samples), "fidelity": self.fidelity,
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
    selection_json: str = ""        # full application settings, for regeneration
    source_fingerprint: str = ""    # hash of every piece that could affect the result

    def selection(self) -> "FillerSelection":
        if not self.selection_json:
            raise FillerCreamError("layer has no saved settings (v1 layer); it cannot be regenerated")
        return FillerSelection.from_dict(json.loads(self.selection_json))

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
            "kind": "filler_cream_layer", "version": 2,
            "face": self.face, "grid_unit": self.grid_unit,
            "fine_subdivision": FINE_SUBDIVISION, "block_meters": PUB_BLOCK_METERS, "engine": ENGINE_VERSION,
            "selection_key": self.selection_key,
            "selection": json.loads(self.selection_json) if self.selection_json else None,
            "source_fingerprint": self.source_fingerprint,
            "cells": [
                {"column": list(c.column), "base": round(c.base, 9), "top": round(c.top, 9),
                 "sources": list(c.sources), "kind": c.kind}
                for c in self.cells
            ],
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "FillerLayer":
        if d.get("kind") != "filler_cream_layer" or int(d.get("version", 0)) not in (1, 2):
            raise FillerCreamError("not a filler_cream_layer v1/v2 payload")
        cells = tuple(
            FillerCell(tuple(c["column"]), float(c["base"]), float(c["top"]), tuple(c["sources"]), str(c["kind"]))
            for c in d["cells"]
        )
        sel = d.get("selection")
        return cls(str(d["face"]), int(d["grid_unit"]), cells, str(d["selection_key"]),
                   json.dumps(sel, sort_keys=True) if sel else "", str(d.get("source_fingerprint") or ""))

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()


# ══════════════════════════════════════════════════════════════════════════
# CORE OPERATION
# ══════════════════════════════════════════════════════════════════════════

def _plane_axes(up: int) -> Tuple[int, int]:
    a, b = [ax for ax in (0, 1, 2) if ax != up]
    return a, b


def _candidates(by_id: Mapping[str, SurfacePiece], selection: FillerSelection) -> List[SurfacePiece]:
    """Every piece that can influence this selection's cream (the selection's
    footprint grown by max_gap). This is also what the source fingerprint covers."""
    up, _ = FACES[selection.face]
    a, b = _plane_axes(up)
    m = int(selection.max_gap) + 1
    chosen = [by_id[pid] for pid in sorted(selection.piece_ids)]
    a0 = min(p.origin[a] for p in chosen) - m
    a1 = max(p.origin[a] + p.size[a] for p in chosen) + m
    b0 = min(p.origin[b] for p in chosen) - m
    b1 = max(p.origin[b] + p.size[b] for p in chosen) + m
    return [p for _, p in sorted(by_id.items())
            if p.origin[a] < a1 and p.origin[a] + p.size[a] > a0
            and p.origin[b] < b1 and p.origin[b] + p.size[b] > b0]


def source_fingerprint(pieces: Iterable[SurfacePiece], selection: FillerSelection) -> str:
    """Hash of every piece that can influence this selection's cream, plus the
    block size. Changes whenever regenerating could give a different result."""
    by_id: Dict[str, SurfacePiece] = {}
    for p in pieces:
        if p.piece_id in by_id:
            raise FillerCreamError(f"duplicate piece_id {p.piece_id!r}")
        by_id[p.piece_id] = p
    if selection.piece_ids - set(by_id):
        return "missing-pieces"
    return _fingerprint_of(_candidates(by_id, selection))


def _fingerprint_of(cands: Sequence[SurfacePiece]) -> str:
    recs = [[p.piece_id, list(p.origin), list(p.size), p.shape, p.wedge_high_side, p.surface_id,
             sorted(p.tags), p.fidelity] for p in cands]
    payload = {"engine": ENGINE_VERSION, "block_m": PUB_BLOCK_METERS, "fine": FINE_SUBDIVISION, "pieces": recs}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


FAST_PATH_BATCH = 4096   # columns per batch in the fast path; caps peak memory


def compute_filler(pieces: Iterable[SurfacePiece], selection: FillerSelection,
                   _exhaustive: bool = False, _careful_only: bool = False) -> FillerLayer:
    """Generate bounded filler for one selection. Pure and deterministic.

    ``pieces`` is the whole construction (selected and unselected); only
    pieces near the selection are rasterised. Pieces are never modified.
    ``_exhaustive`` (tests only) fits every column instead of using the
    candidate shortcut, to prove the shortcut never skips a column.
    ``_careful_only`` (tests only) disables the moment-sum fast path, to prove
    it gives the same cream as the per-column search.
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
    cands = _candidates(by_id, selection)

    def radius(p: SurfacePiece) -> float:
        span = fidelity_span_fine(selection.fidelity if selection.fidelity is not None else p.fidelity)
        return span / 2.0

    # Working grid: the widest column that (1) divides every piece edge, so
    # rasterising is exact, and (2) is no wider than the sampling cap (about
    # grid_samples columns across the smallest piece, and no wider than the
    # finest fit radius). Sampling alone never refines past 1/64 block; only
    # finer pieces (1/128, Primp and close-ups) make the grid finer. So
    # 1/64 work costs and behaves the same as before the unit became 1/128.
    geo = 0
    for p in cands:
        for v in (p.origin[a], p.size[a], p.origin[b], p.size[b]):
            geo = math.gcd(geo, abs(v))
    geo = geo or 1
    min_plane = min(min(p.size[a], p.size[b]) for p in sel)
    min_radius = min(radius(p) for p in sel)
    sample_floor = max(1, FINE_SUBDIVISION // LEGACY_FINE_SUBDIVISION)
    cap = max(sample_floor, min(min_plane // int(selection.grid_samples), int(min_radius)))
    g = max(d for d in range(1, min(geo, cap) + 1) if geo % d == 0)

    # ── 3. rasterise: outermost piece owns each column ───────────────────
    # Selected pieces are rasterised first (outermost selected piece per
    # column). An unselected piece covers a selected column only where it
    # touches or buries that surface (its base is at or below it), so a
    # ceiling or any slab separated by air never blocks the floor beneath.
    # An empty column is claimed by an unselected piece only when that piece
    # starts at or below the highest selected surface (it can block a crack
    # at surface level, but not from far above).
    owner: Dict[Tuple[int, int], str] = {}
    height: Dict[Tuple[int, int], float] = {}

    _col_cache: Dict[str, List[Tuple[Tuple[int, int], float]]] = {}

    def _columns(p: SurfacePiece) -> List[Tuple[Tuple[int, int], float]]:
        """Each piece's columns and surface heights, computed once."""
        hit = _col_cache.get(p.piece_id)
        if hit is None:
            hit = _col_cache[p.piece_id] = [
                ((i, j), p.top_at(up, sign, {a: (i + 0.5) * g, b: (j + 0.5) * g}))
                for i in range(p.origin[a] // g, (p.origin[a] + p.size[a]) // g)
                for j in range(p.origin[b] // g, (p.origin[b] + p.size[b]) // g)]
        return hit

    for p in (q for q in cands if q.piece_id in selection.piece_ids):
        for col, h in _columns(p):
            cur = owner.get(col)
            if cur is None or h > height[col] + _EPS or (abs(h - height[col]) <= _EPS and p.piece_id < cur):
                owner[col] = p.piece_id
                height[col] = h
    max_cols = max_gap // g
    # Every candidate piece's base per column: cream is capped below the base
    # of anything hanging over the surface across an air gap (a protected
    # slab, a ceiling, a tabletop), so it can never penetrate solid material.
    bases_by_col: Dict[Tuple[int, int], List[float]] = {}
    for p in cands:
        p_base = p.outward_span(up, sign)[0]
        for col, _h in _columns(p):
            bases_by_col.setdefault(col, []).append(p_base)
    claims: Dict[Tuple[int, int], Tuple[float, str]] = {}
    for p in (q for q in cands if q.piece_id not in selection.piece_ids):
        p_base = p.outward_span(up, sign)[0]
        for col, h in _columns(p):
            if col in owner:
                if not (p_base <= height[col] + _EPS and h > height[col] + _EPS):
                    continue
            else:
                # An empty column only matters as a possible crack, so judge the
                # piece against the selected surface right beside it (within
                # crack reach), not the selection's highest point anywhere.
                if max_cols < 1:
                    continue
                k = max_cols + 1
                near = [height[(col[0] + di, col[1] + dj)]
                        for di in range(-k, k + 1) for dj in range(-k, k + 1)
                        if (col[0] + di, col[1] + dj) in height]
                if not near or p_base > max(near) + _EPS:
                    continue
            prev = claims.get(col)
            if prev is None or h > prev[0] + _EPS or (abs(h - prev[0]) <= _EPS and p.piece_id < prev[1]):
                claims[col] = (h, p.piece_id)
    for col, (h, pid) in sorted(claims.items()):
        owner[col] = pid
        height[col] = h

    selected = selection.piece_ids

    _elig_cache: Dict[Tuple[str, str], bool] = {}

    def eligible(pa: str, pb: str) -> bool:
        key = (pa, pb) if pa < pb else (pb, pa)
        hit = _elig_cache.get(key)
        if hit is None:
            hit = _elig_cache[key] = _eligible(*key)
        return hit

    def _eligible(pa: str, pb: str) -> bool:
        if pa == pb or pa not in selected or pb not in selected:
            return False
        A, B = by_id[pa], by_id[pb]
        if not (A.supports(face) and B.supports(face)) or A.keep() or B.keep():
            return False
        if A.surface_id != B.surface_id:
            return False
        return frozenset((pa, pb)) not in selection.barriers

    _fill_cache: Dict[str, bool] = {}

    def fillable(pid: str) -> bool:
        hit = _fill_cache.get(pid)
        if hit is None:
            P = by_id[pid]
            hit = _fill_cache[pid] = pid in selected and P.supports(face) and not P.keep()
        return hit

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

    # Every allowed step between neighbouring columns, worked out once. The
    # searches below only walk this table (profiling showed the old per-step
    # checks were over half the runtime).
    adj: Dict[Tuple[int, int], Tuple[Tuple[int, int], ...]] = {}
    for col in sorted(owner):
        if fillable(owner[col]):
            adj[col] = tuple(y for y in ((col[0] + d[0], col[1] + d[1]) for d in _DIRS) if connected(col, y))

    _discs: Dict[float, frozenset] = {}

    def disc(reach: float) -> frozenset:
        """Column offsets whose centres lie within ``reach`` fine units."""
        hit = _discs.get(reach)
        if hit is None:
            n = int(reach // g) + 1
            hit = _discs[reach] = frozenset((di, dj) for di in range(-n, n + 1) for dj in range(-n, n + 1)
                                            if math.hypot(di * g, dj * g) <= reach)
        return hit

    best: Dict[Tuple[int, int], FillerCell] = {}

    def offer(col: Tuple[int, int], base: float, top: float, src: Tuple[str, ...], kind: str) -> None:
        above = [bb for bb in bases_by_col.get(col, ()) if bb >= base - _EPS]
        if above:
            top = min(top, min(above))
        if top <= base + _EPS:
            return
        prev = best.get(col)
        if prev is None or top > prev.top + _EPS:
            best[col] = FillerCell(col, base, top, src, kind)

    # ── 4. candidates: columns within reach of a higher connected neighbour
    #       (a level surface does no work at all) ─────────────────────────
    frontier: List[Tuple[Tuple[int, int], float]] = []
    for col in sorted(adj):
        if any(height[nb] > height[col] + _EPS for nb in adj[col]):
            frontier.append((col, radius(by_id[owner[col]])))
    # A column can only gain cream if a higher column lies inside its own fit
    # window (radius r_c + g/2). The step just before that higher column is a
    # frontier column within that window, so every node of the window path is
    # within 2 * (r_max + g/2) of it. Searching that far from each frontier
    # column is therefore conservative for any mix of per-piece fidelities.
    r_max = max(radius(by_id[pid]) for pid in selected)
    candidates: Dict[Tuple[int, int], None] = {}
    if _exhaustive:
        candidates = {c: None for c in sorted(owner) if fillable(owner[c])}
        frontier = []
    import numpy as np

    # Grid view of the owned columns, padded so window shifts never wrap.
    pad = int((2.0 * (r_max + 0.5 * g)) // g) + 2
    ci0 = min(c[0] for c in owner) - pad if owner else 0
    cj0 = min(c[1] for c in owner) - pad if owner else 0
    ni = (max(c[0] for c in owner) - ci0 + pad + 1) if owner else 1
    nj = (max(c[1] for c in owner) - cj0 + pad + 1) if owner else 1
    fill_mask = np.zeros((ni, nj), dtype=bool)
    for col in adj:
        fill_mask[col[0] - ci0, col[1] - cj0] = True

    def dilate(mask: "np.ndarray", offsets) -> "np.ndarray":
        out = np.zeros_like(mask)
        for di, dj in offsets:
            out[max(0, di):ni + min(0, di), max(0, dj):nj + min(0, dj)] |= \
                mask[max(0, -di):ni + min(0, -di), max(0, -dj):nj + min(0, -dj)]
        return out

    if not _exhaustive and frontier:
        # Every column within reach of a frontier column, as one grid dilation.
        # This is a superset of the old per-frontier search (it ignores marks),
        # which is safe: a column with no higher column in its own window
        # caps at its own height and gains nothing.
        fmask = np.zeros((ni, nj), dtype=bool)
        for col, _r in frontier:
            fmask[col[0] - ci0, col[1] - cj0] = True
        near = dilate(fmask, disc(2.0 * (r_max + 0.5 * g))) & fill_mask
        candidates = {(int(i) + ci0, int(j) + cj0): None for i, j in zip(*np.nonzero(near))}

    # ── fast path: windows that are a full, unmarked disc ────────────────────
    # A column whose whole disc is owned by fillable pieces with every step
    # between neighbours allowed has the full disc as its window, so its
    # weighted plane comes from moment sums over the grid (the normal matrix
    # is the same for every such column and is inverted once). Same rule and
    # weights as the per-column search below, without walking it.
    H_grid = np.zeros((ni, nj))
    O_grid = np.full((ni, nj), -1, dtype=np.int64)
    names = sorted(by_id)
    name_ix = {n: k for k, n in enumerate(names)}
    for col, h in height.items():
        H_grid[col[0] - ci0, col[1] - cj0] = h
        O_grid[col[0] - ci0, col[1] - cj0] = name_ix[owner[col]]
    unclean = ~fill_mask.copy()
    for col, nbrs in adj.items():
        if len(nbrs) < 4:
            unclean[col[0] - ci0, col[1] - cj0] = True
    slow: List[Tuple[int, int]] = []
    groups: Dict[float, List[Tuple[int, int]]] = {}
    for col in sorted(candidates):
        groups.setdefault(radius(by_id[owner[col]]), []).append(col)
    for r, cols in sorted(groups.items()):
        reach = r + 0.5 * g
        offs = sorted(disc(reach))
        if len(offs) < 3 or _careful_only:
            slow.extend(cols)
            continue
        blocked = dilate(unclean, offs)
        I = np.array([c[0] - ci0 for c in cols])
        J = np.array([c[1] - cj0 for c in cols])
        fast = ~blocked[I, J]
        slow.extend(c for c, f in zip(cols, fast) if not f)
        if not fast.any():
            continue
        I_all, J_all = I[fast], J[fast]
        du = np.array([o[0] * g for o in offs], dtype=float)
        dv = np.array([o[1] * g for o in offs], dtype=float)
        w = 1.0 - np.hypot(du, dv) / (reach + g)
        M = np.array([[w.sum(), (w * du).sum(), (w * dv).sum()],
                      [(w * du).sum(), (w * du * du).sum(), (w * du * dv).sum()],
                      [(w * dv).sum(), (w * du * dv).sum(), (w * dv * dv).sum()]])
        Minv = np.linalg.inv(M)
        # Batches bound memory at about K x FAST_PATH_BATCH values per array.
        for start in range(0, len(I_all), FAST_PATH_BATCH):
            I = I_all[start:start + FAST_PATH_BATCH]
            J = J_all[start:start + FAST_PATH_BATCH]
            Hk = np.stack([H_grid[I + o[0], J + o[1]] for o in offs])          # (K, n)
            rhs = np.stack([w @ Hk, (w * du) @ Hk, (w * dv) @ Hk])            # (3, n)
            c0, c1, c2 = Minv @ rhs
            fitted = c0[None, :] + du[:, None] * c1[None, :] + dv[:, None] * c2[None, :]
            lift = np.maximum(0.0, ((Hk - fitted) * w[:, None]).max(0))
            target = np.minimum(c0 + lift, Hk.max(0))
            del fitted
            gain = np.nonzero(target > H_grid[I, J] + _EPS)[0]
            if not len(gain):
                continue
            ids = np.sort(np.stack([O_grid[I[gain] + o[0], J[gain] + o[1]] for o in offs], axis=1), axis=1)
            for row, k in enumerate(gain):
                uniq = ids[row][np.concatenate(([True], ids[row][1:] != ids[row][:-1]))]
                srcs_sorted = [names[x] for x in uniq]
                if len(srcs_sorted) > MAX_SOURCES_PER_CELL:
                    srcs_sorted = srcs_sorted[:MAX_SOURCES_PER_CELL - 1] + [f"+{len(srcs_sorted) - MAX_SOURCES_PER_CELL + 1} more"]
                col = (int(I[k]) + ci0, int(J[k]) + cj0)
                offer(col, height[col], float(target[k]), tuple(srcs_sorted), "fit")

    # ── careful path: windows touched by a mark, an edge or a hole ──────────
    for col in slow:
        r = radius(by_id[owner[col]])
        reach = r + 0.5 * g
        seen = {col}
        stack = [col]
        pts: List[Tuple[float, float, float, float]] = []
        srcs = set()
        window = disc(reach)
        while stack:
            x = stack.pop()
            du, dv = (x[0] - col[0]) * g, (x[1] - col[1]) * g
            w = 1.0 - math.hypot(du, dv) / (reach + g)
            pts.append((du, dv, height[x], w))
            srcs.add(owner[x])
            for y in adj[x]:
                if y in seen or (y[0] - col[0], y[1] - col[1]) not in window:
                    continue
                seen.add(y)
                stack.append(y)
        if len(pts) < 2:
            continue
        arr = np.array(sorted(pts), dtype=float)
        sw = np.sqrt(arr[:, 3])
        design = np.column_stack([np.ones(len(arr)), arr[:, 0], arr[:, 1]]) * sw[:, None]
        coef, *_ = np.linalg.lstsq(design, arr[:, 2] * sw, rcond=None)
        # Outer-points rule: keep the best-fit slope, lift the plane until it
        # rests on the outermost block point in the neighbourhood (wood filler
        # wiped flush with the surrounding surface), never above the highest one.
        # Each point's pull on the lift fades linearly with its distance from
        # c, so the surface stays continuous as columns move along, and a
        # one-sided window (the open end of a run) cannot raise a lip.
        fitted = coef[0] + coef[1] * arr[:, 0] + coef[2] * arr[:, 1]
        fade = np.clip(1.0 - np.hypot(arr[:, 0], arr[:, 1]) / (reach + g), 0.0, 1.0)
        lift = max(0.0, float(((arr[:, 2] - fitted) * fade).max()))
        target = min(float(coef[0]) + lift, float(arr[:, 2].max()))
        names = sorted(srcs)
        if len(names) > MAX_SOURCES_PER_CELL:  # keep saved layers small on broad areas
            names = names[:MAX_SOURCES_PER_CELL - 1] + [f"+{len(names) - MAX_SOURCES_PER_CELL + 1} more"]
        offer(col, height[col], target, tuple(names), "fit")

    # ── 6. cracks: short empty runs between two eligible pieces ──────────
    # Cracks: every empty column near the selection looks both ways along
    # four lines (two straight, two diagonal). If the nearest column each way
    # is an eligible selected piece and the empty run between them is no
    # wider than max_gap (diagonals measured at their true length), it fills
    # from the shell base to the straight line between the two surfaces.
    if max_cols >= 1:
        k = max_cols + 1
        # Only owned columns on an edge (an empty 8-neighbour) can have an empty
        # column within reach along a straight or diagonal line.
        edge = [c for c in owner if owner[c] in selected and any(
            (c[0] + di, c[1] + dj) not in owner for di in (-1, 0, 1) for dj in (-1, 0, 1))]
        empties = sorted({(c[0] + di, c[1] + dj) for c in edge
                          for di in range(-k, k + 1) for dj in range(-k, k + 1)} - set(owner))
        for e in empties:
            for d in ((1, 0), (0, 1), (1, 1), (1, -1)):
                ends = []
                for sgn in (-1, 1):
                    found = None
                    for step in range(1, k + 1):
                        probe = (e[0] + sgn * d[0] * step, e[1] + sgn * d[1] * step)
                        if probe in owner:
                            found = (probe, step)
                            break
                    ends.append(found)
                if ends[0] is None or ends[1] is None:
                    continue
                (ca, ka), (cb, kb) = ends
                run = ka + kb - 1
                if run * g * math.hypot(d[0], d[1]) > max_gap + _EPS:
                    continue
                pa, pb = owner[ca], owner[cb]
                if not eligible(pa, pb):
                    continue
                ha, hb = height[ca], height[cb]
                if selection.max_step is not None and abs(hb - ha) > selection.max_step + _EPS:
                    continue
                base = max(by_id[pa].outward_span(up, sign)[0], by_id[pb].outward_span(up, sign)[0])
                offer(e, base, ha + (hb - ha) * ka / (ka + kb), (pa, pb) if pa < pb else (pb, pa), "crack")

    cells = tuple(best[c] for c in sorted(best))
    return FillerLayer(face, g, cells, selection.key(),
                       json.dumps(selection.to_dict(), sort_keys=True), _fingerprint_of(cands))


def layer_is_stale(layer: FillerLayer, pieces: Iterable[SurfacePiece]) -> bool:
    """True when the voxels under this layer changed since it was made (or the
    layer predates saved settings): its cream no longer matches the blueprint."""
    if not layer.selection_json or not layer.source_fingerprint:
        return True
    return source_fingerprint(pieces, layer.selection()) != layer.source_fingerprint


def regenerate(layer: FillerLayer, pieces: Iterable[SurfacePiece]) -> FillerLayer:
    """Recompute a layer from its saved settings against the current voxels.
    Raises FillerCreamError if a selected piece no longer exists."""
    return compute_filler(pieces, layer.selection())


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

    def stale(self, pieces: Iterable[SurfacePiece]) -> List[str]:
        plist = list(pieces)
        return [k for k in sorted(self._layers) if layer_is_stale(self._layers[k], plist)]

    def refresh(self, pieces: Iterable[SurfacePiece]) -> Dict[str, str]:
        """Regenerate every stale layer. Returns {name: "regenerated" | reason}.
        A layer whose selected pieces are gone is kept and reported, never guessed."""
        plist = list(pieces)
        out: Dict[str, str] = {}
        for name in self.stale(plist):
            try:
                self._layers[name] = regenerate(self._layers[name], plist)
                out[name] = "regenerated"
            except FillerCreamError as exc:
                out[name] = f"needs attention: {exc}"
        return out

    def bake_layers(self, pieces: Iterable[SurfacePiece]) -> List[FillerLayer]:
        """Layers ready to bake. Raises if any layer is stale (for example
        one whose refresh failed); remove or fix it first."""
        plist = list(pieces)
        bad = self.stale(plist)
        if bad:
            raise FillerCreamError(f"stale cream layers block the bake: {bad}")
        return self.layers()

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
        size3 = (s, s, s)
        if kind == "occluder":
            notes.append(f"{prim.primitive_id}: {shape} rot={list(prim.rotation_deg)} kept as occluder (not filled)")
            if not right_angles:
                # A turned shape pokes out past its unturned box; occlude with the
                # full axis-aligned box it actually fills, so cream can't enter it.
                from .voxel_studio import build_primitive_geometry
                verts, _, _ = build_primitive_geometry(prim.shape, prim.size, tuple(prim.rotation_deg))
                lo = [math.floor((prim.position[k] + float(verts[:, k].min())) * FINE_SUBDIVISION + 1e-9) for k in range(3)]
                hi = [math.ceil((prim.position[k] + float(verts[:, k].max())) * FINE_SUBDIVISION - 1e-9) for k in range(3)]
                origin, size3 = tuple(lo), tuple(max(1, hi[k] - lo[k]) for k in range(3))
        pieces.append(SurfacePiece(prim.primitive_id, origin, size3, kind, high, surface_id, tags,
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

def _flat_normals(verts, faces):
    """Vectorised equivalent of voxel_studio._compute_normals: flat normals,
    three vertices per triangle, degenerate triangles dropped, same order and
    dtypes. The original loops per triangle in Python and is left unchanged."""
    import numpy as np
    v = np.asarray(verts, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    v0, v1, v2 = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    mag = np.linalg.norm(n, axis=1)
    keep = mag >= 1e-9
    n = n[keep] / mag[keep][:, None]
    tri = np.stack([v0[keep], v1[keep], v2[keep]], axis=1)          # (T, 3, 3)
    out_v = tri.reshape(-1, 3).astype(np.float32)
    out_n = np.repeat(n, 3, axis=0).astype(np.float32)
    out_f = np.arange(len(out_v), dtype=np.uint32).reshape(-1, 3)
    return out_v, out_n, out_f


def filler_mesh_arrays(layers: Sequence[FillerLayer], world_position=(0.0, 0.0, 0.0)):
    """(verts, normals, faces) for filler boxes in block units, built with
    voxel_studio's own cube table and flat-normal routine."""
    import numpy as np
    from .voxel_studio import VoxelShape, _shape_verts_faces

    unit_v, unit_f = _shape_verts_faces(VoxelShape.CUBE)
    boxes = [bx for layer in layers for bx in layer.boxes()]
    if not boxes:
        return (np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32), np.zeros((0, 3), np.uint32))
    scale = 1.0 / FINE_SUBDIVISION
    lo = np.array([bx[0] for bx in boxes], dtype=np.float64) * scale            # (N, 3)
    ext = np.array([bx[1] for bx in boxes], dtype=np.float64) * scale - lo     # (N, 3)
    verts = unit_v[None, :, :] * ext[:, None, :] + lo[:, None, :] + np.asarray(world_position, dtype=float)
    faces = unit_f[None, :, :] + (np.arange(len(boxes)) * len(unit_v))[:, None, None]
    return _flat_normals(verts.reshape(-1, 3), faces.reshape(-1, 3))


def _require_fresh(layers: Sequence[FillerLayer], pieces: Optional[Iterable[SurfacePiece]], unchecked: bool) -> None:
    if not layers or unchecked:
        return
    if pieces is None:
        raise FillerCreamError("pass the current pieces so stale cream can be refused (or unchecked=True)")
    plist = list(pieces)
    stale = [lay.selection_key for lay in layers if layer_is_stale(lay, plist)]
    if stale:
        raise FillerCreamError(f"refusing to bake {len(stale)} stale cream layer(s): {stale[:5]}; "
                               "refresh them or remove them first")


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
    if len(gltf.get("meshes", [])) != 1 or len(gltf["meshes"][0]["primitives"]) != 1:
        raise FillerCreamError("expected exactly one mesh with one primitive; refusing to drop geometry")
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


def bake_with_filler(obj: Any, layers: Sequence[FillerLayer], world_position=(0.0, 0.0, 0.0), *,
                     pieces: Optional[Iterable[SurfacePiece]] = None, unchecked: bool = False) -> bytes:
    """Bake obj with the existing VoxelBaker, then append filler geometry.

    Every layer is checked against ``pieces`` (the current pieces, built with
    the same annotations used to make the layers) and the bake is refused if
    any layer is stale: stale cream can never silently enter a bake.
    ``unchecked=True`` skips the check explicitly (tests and tools only).
    With no filler cells this returns exactly VoxelBaker().bake(obj) bytes.
    The VoxelObject is never modified.
    """
    _require_fresh(layers, pieces, unchecked)
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


def pieces_from_generated_blocks(blocks: Sequence[Mapping[str, Any]], prefix: str = "g") -> Tuple[List[SurfacePiece], List[str]]:
    """Convert voxel_llm_adapter output (``position`` [x, y, z] in blocks,
    ``scale`` [sx, sy, sz], ``rotation``, ``material``, ``tags``) into pieces.
    Each block's material becomes its surface name, so cream never blends a
    wooden seat into a metal leg unless they share a material. Rotated blocks
    become occluders. Returns (pieces, notes)."""
    pieces: List[SurfacePiece] = []
    notes: List[str] = []
    for n, blk in enumerate(blocks):
        pid = f"{prefix}{n}"
        pos = blk.get("position") or [blk.get("x", 0), blk.get("y", 0), blk.get("z", 0)]
        scale = blk.get("scale") or [1, 1, 1]
        origin = tuple(_to_fine(v, f"{pid}.position") for v in pos)
        size = tuple(_to_fine(v, f"{pid}.scale") for v in scale)
        rotated = any(float(r) % 360 for r in (blk.get("rotation") or [0, 0, 0]))
        if rotated:
            # The generator's rotation convention isn't defined, so occlude
            # conservatively: a box around the block's centre big enough for
            # any turn (its full diagonal), so cream can never enter it.
            half = math.ceil(math.sqrt(sum(sv * sv for sv in size)) / 2.0)
            centre = [origin[k] + size[k] / 2.0 for k in range(3)]
            origin = tuple(math.floor(centre[k] - half) for k in range(3))
            size = (2 * half, 2 * half, 2 * half)
        shape = "occluder" if rotated or blk.get("type", "cube") != "cube" else "cube"
        if shape == "occluder":
            notes.append(f"{pid}: {blk.get('type', 'cube')} rot={blk.get('rotation')} kept as occluder")
        tags = frozenset(t for t in (blk.get("tags") or ()) if t in KEEP_TAGS)
        pieces.append(SurfacePiece(pid, origin, size, shape, None, str(blk.get("material") or "default"), tags,
                                   blk.get("fidelity")))
    return pieces, notes


def box_uvs(verts, normals, repeat_per_block: float = 1.0):
    """Box-projection texture coordinates: each vertex takes the two axes
    across its face (by dominant normal). One texture repeat per block by
    default, so wood grain or tile stays the same real size on every object."""
    import numpy as np
    v = np.asarray(verts, dtype=np.float64)
    n = np.abs(np.asarray(normals, dtype=np.float64))
    axis = n.argmax(axis=1)
    uv = np.empty((len(v), 2), dtype=np.float32)
    uv[axis == 0] = v[axis == 0][:, [2, 1]]
    uv[axis == 1] = v[axis == 1][:, [0, 2]]
    uv[axis == 2] = v[axis == 2][:, [0, 1]]
    return (uv * float(repeat_per_block)).astype(np.float32)


def pack_glb_uv(verts, normals, faces, uvs, name: str) -> bytes:
    """glTF 2.0 binary with POSITION, NORMAL, TEXCOORD_0 and indices.
    JSON padded with spaces as the spec requires (voxel_studio.pack_glb is
    left unchanged)."""
    import numpy as np
    def _shaped(name, arr, cols):
        a = np.asarray(arr)
        if a.ndim != 2 or a.shape[1] != cols:
            raise FillerCreamError(f"{name} must be shaped (N, {cols}); got {a.shape}")
        return a

    v_in, n_in, uv_in = _shaped("positions", verts, 3), _shaped("normals", normals, 3), _shaped("uvs", uvs, 2)
    f_in = _shaped("triangle indices", faces, 3)
    for name, a in (("positions", v_in), ("normals", n_in), ("uvs", uv_in)):
        if not np.issubdtype(a.dtype, np.number) or not np.all(np.isfinite(a)):
            raise FillerCreamError(f"{name} must be finite numbers")
    if len(v_in) == 0 or len(f_in) == 0:
        raise FillerCreamError("nothing to bake: the mesh is empty")
    if not (len(v_in) == len(n_in) == len(uv_in)):
        raise FillerCreamError("positions, normals and uvs must have the same number of rows")
    if np.issubdtype(f_in.dtype, np.integer):
        f_int = f_in.astype(np.int64)
    elif np.issubdtype(f_in.dtype, np.floating) and np.all(np.isfinite(f_in)) and np.all(f_in == np.round(f_in)):
        f_int = f_in.astype(np.int64)
    else:
        raise FillerCreamError("triangle indices must be whole numbers")
    if int(f_int.min()) < 0 or int(f_int.max()) >= len(v_in):
        raise FillerCreamError("triangle indices out of range")
    v = np.ascontiguousarray(v_in, dtype=np.float32)
    nm = np.ascontiguousarray(n_in, dtype=np.float32)
    uv = np.ascontiguousarray(uv_in, dtype=np.float32)
    ix = np.ascontiguousarray(f_int, dtype=np.uint32).reshape(-1)

    def pad(b: bytes, fill: bytes = b"\x00") -> bytes:
        return b + fill * ((4 - len(b) % 4) % 4)

    chunks = [pad(v.tobytes()), pad(nm.tobytes()), pad(uv.tobytes()), pad(ix.tobytes())]
    offsets, off = [], 0
    for c in chunks:
        offsets.append(off)
        off += len(c)
    views = [{"buffer": 0, "byteOffset": offsets[k], "byteLength": len(chunks[k]),
              **({"target": 34963} if k == 3 else {"target": 34962})} for k in range(4)]
    acc = [
        {"bufferView": 0, "componentType": 5126, "count": len(v), "type": "VEC3",
         "min": v.min(axis=0).tolist() if len(v) else [0, 0, 0], "max": v.max(axis=0).tolist() if len(v) else [0, 0, 0]},
        {"bufferView": 1, "componentType": 5126, "count": len(nm), "type": "VEC3"},
        {"bufferView": 2, "componentType": 5126, "count": len(uv), "type": "VEC2"},
        {"bufferView": 3, "componentType": 5125, "count": len(ix), "type": "SCALAR"},
    ]
    gltf = {"asset": {"version": "2.0", "generator": "PubCast filler_cream"},
            "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": name}],
            "meshes": [{"name": name, "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                                                       "indices": 3, "material": 0}]}],
            "materials": [{"name": "paintable", "pbrMetallicRoughness": {
                "baseColorFactor": [0.8, 0.8, 0.8, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.8}}],
            "accessors": acc, "bufferViews": views, "buffers": [{"byteLength": off}]}
    js = pad(json.dumps(gltf, separators=(",", ":")).encode(), b" ")
    binary = b"".join(chunks)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(binary), 0x004E4942) + binary)


def bake_textured(obj: Any, layers: Sequence[FillerLayer] = (), world_position=(0.0, 0.0, 0.0),
                  repeat_per_block: float = 1.0, *, pieces: Optional[Iterable[SurfacePiece]] = None,
                  unchecked: bool = False) -> bytes:
    """Bake blocks + cream into one mesh WITH texture coordinates, ready to
    paint or take an image texture. Same geometry as bake_with_filler."""
    v, n, f = parse_glb(bake_with_filler(obj, layers, world_position, pieces=pieces, unchecked=unchecked))
    return pack_glb_uv(v, n, f, box_uvs(v, n, repeat_per_block), obj.name)


__all__ = [
    "DEFAULT_FIDELITY", "ENGINE_VERSION", "FACES", "FIDELITY_STOPS", "FINE_SUBDIVISION", "fidelity_span_fine", "FINE_UNIT_INCHES", "FINE_UNIT_MM", "KEEP_TAGS",
    "FillerCell", "FillerCreamError", "FillerCreamLayers", "FillerLayer", "FillerSelection",
    "SurfacePiece", "bake_textured", "bake_with_filler", "box_uvs", "pack_glb_uv", "pieces_from_generated_blocks", "compute_filler", "layer_is_stale", "regenerate", "source_fingerprint", "filler_mesh_arrays", "parse_glb",
    "pieces_from_voxel_object", "pieces_from_voxel_set",
]
