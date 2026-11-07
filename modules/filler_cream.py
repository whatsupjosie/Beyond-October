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

Local interpolation rule (documented limits in docs/FILLER_CREAM.md)
----------------------------------------------------------------------
Work is done on one exposed face orientation at a time (``+y`` = tops).
The selection is rasterised into columns on that face. Each column has an
owner (the outermost piece over it) and a surface height H.

1. Ramp (step fill). For a column c of piece A, look along each of the four
   in-plane directions. Walk to the last column of A in that row (edge e);
   the next column n belongs to piece B. If B is an eligible neighbour and
   B is higher by a step D = H(n) - H(e) with 0 < D <= max_step, the cream
   target at c is H(c) + D * (1 - d / w), where d is the distance from c to
   the shared edge and w is half of A's run length in that row. The ramp
   fades out at A's mid-run, is capped at max(H(c), H(n)), and only ever
   adds material. The highest candidate over the four directions wins.
2. Crack (lateral gap). An empty run of columns between two eligible pieces
   no wider than max_gap fine units is filled from the shell base
   (max of the two pieces' bases) up to the straight line between the two
   bordering surface heights. Wider empty runs are openings and stay empty.

Eligible neighbour: both pieces selected, both supported shapes for this
face, neither carries a keep tag, same surface_id, not an explicit barrier
pair, and the step fits max_step (default: the thinner piece's thickness
along the face normal). Spatial closeness alone never qualifies: pieces
must touch column-to-column or sit across a crack no wider than max_gap.

Each filler value depends only on piece A's own run and the single column
across its edge, so influence never reaches past one piece width. A larger
selection means more of these local fills, never deeper ones.

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

FINE_SUBDIVISION = 64
PUB_BLOCK_INCHES = 10.0
FINE_UNIT_INCHES = PUB_BLOCK_INCHES / FINE_SUBDIVISION  # 0.15625
FINE_UNIT_MM = FINE_UNIT_INCHES * 25.4                   # 3.96875

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

    def __post_init__(self) -> None:
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
    max_step   — largest step (fine units) treated as a gap; None = the
                 thinner piece's thickness along the face normal.
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

    def __post_init__(self) -> None:
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
            "ramp_samples": int(self.ramp_samples),
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
    sources: Tuple[str, str]
    kind: str            # "ramp" | "crack"


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

    # ── 2. working grid: largest unit that keeps every edge on the grid ───
    g = 0
    for p in cands:
        for v in (p.origin[a], p.size[a], p.origin[b], p.size[b]):
            g = math.gcd(g, abs(v))
    min_plane = min(min(p.size[a], p.size[b]) for p in sel)
    g = math.gcd(g, max(1, min_plane // int(selection.ramp_samples))) if g else 1
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

    def thickness(p: SurfacePiece) -> int:
        return p.size[up]

    def eligible(pa: str, pb: str) -> bool:
        if pa == pb or pa not in selected or pb not in selected:
            return False
        A, B = by_id[pa], by_id[pb]
        if not (A.supports(face) and B.supports(face)) or A.keep() or B.keep():
            return False
        if A.surface_id != B.surface_id:
            return False
        return frozenset((pa, pb)) not in selection.barriers

    def step_limit(pa: str, pb: str) -> float:
        if selection.max_step is not None:
            return float(selection.max_step)
        return float(min(thickness(by_id[pa]), thickness(by_id[pb])))

    # ── 4. run lengths within each piece along the four directions ───────
    runs: Dict[Tuple[int, int], Dict[Tuple[int, int], int]] = {}
    for d in _DIRS:
        dist: Dict[Tuple[int, int], int] = {}
        for col in sorted(owner, key=lambda c: -(c[0] * d[0] + c[1] * d[1])):
            nxt = (col[0] + d[0], col[1] + d[1])
            dist[col] = dist[nxt] + 1 if owner.get(nxt) == owner[col] else 0
        runs[d] = dist

    best: Dict[Tuple[int, int], FillerCell] = {}

    def offer(col: Tuple[int, int], base: float, top: float, src: Tuple[str, str], kind: str) -> None:
        if top <= base + _EPS:
            return
        prev = best.get(col)
        if prev is None or top > prev.top + _EPS:
            best[col] = FillerCell(col, base, top, src, kind)

    # ── 5. ramps on owned columns of selected pieces ──────────────────────
    for col in sorted(owner):
        pa = owner[col]
        if pa not in selected:
            continue
        hc = height[col]
        for d in _DIRS:
            fwd = runs[d][col]
            back = runs[(-d[0], -d[1])][col]
            edge = (col[0] + d[0] * fwd, col[1] + d[1] * fwd)
            nb = (edge[0] + d[0], edge[1] + d[1])
            pb = owner.get(nb)
            if pb is None or not eligible(pa, pb):
                continue
            step = height[nb] - height[edge]
            if step <= _EPS or step > step_limit(pa, pb) + _EPS:
                continue
            dist_edge = fwd + 0.5
            half_run = (fwd + back + 1) / 2.0
            if dist_edge >= half_run:
                continue
            target = hc + step * (1.0 - dist_edge / half_run)
            target = min(target, max(hc, height[nb]))
            offer(col, hc, target, (pa, pb), "ramp")

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
                if abs(hb - ha) > step_limit(pa, pb) + _EPS:
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
    ``annotations`` maps primitive_id → {"surface_id": str, "tags": [...]};
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
        pieces.append(SurfacePiece(prim.primitive_id, origin, (s, s, s), kind, high, surface_id, tags))
    return pieces, notes


def pieces_from_voxel_set(voxel_set: Mapping[str, Any]) -> List[SurfacePiece]:
    """Convert a canonical voxel set (voxel_set_contract) into SurfacePieces.

    Block metadata: ``surface_id`` (else ``part``, else "default") and
    ``filler_tags`` (list) or ``filler: "preserve"``.
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
    "FACES", "FINE_SUBDIVISION", "FINE_UNIT_INCHES", "FINE_UNIT_MM", "KEEP_TAGS",
    "FillerCell", "FillerCreamError", "FillerCreamLayers", "FillerLayer", "FillerSelection",
    "SurfacePiece", "bake_with_filler", "compute_filler", "filler_mesh_arrays", "parse_glb",
    "pieces_from_voxel_object", "pieces_from_voxel_set",
]
