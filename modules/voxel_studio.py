#!/usr/bin/env python3
"""
voxel_studio.py — PubWorld Voxel Studio
════════════════════════════════════════════════════════════════════════════════
Rear View Foresight LLC · Feic Mo Chroí™

One module. Everything voxel-production needs:

  ┌─ PRIMITIVES ──────────────────────────────────────────────────────────────┐
  │  4 shapes × 3 sizes × 8 rotations  →  the complete voxel vocabulary      │
  │  cube / wedge / corner_outer / corner_inner  @  1.0 / 0.5 / 0.25         │
  │  LOD levels: LOW · LOW_MED · MED · MED_HIGH · HIGH                        │
  └───────────────────────────────────────────────────────────────────────────┘

  ┌─ AUTHORED OBJECTS ────────────────────────────────────────────────────────┐
  │  VoxelObject  =  list of placed VoxelPrimitives  +  pivot groups          │
  │  Source JSON  =  permanent editable record (the "source code")            │
  │  Baker        =  welds primitives into a single GLB per group             │
  └───────────────────────────────────────────────────────────────────────────┘

  ┌─ DESTRUCTION ─────────────────────────────────────────────────────────────┐
  │  DestructionProfile  →  detonation type / force / radius / seed           │
  │  Explode  =  un-bake object into fragment primitives + fire physics       │
  │  Reset    =  despawn fragments, respawn intact object from SLATE          │
  └───────────────────────────────────────────────────────────────────────────┘

  ┌─ SCENE STATE (SLATE / JOURNEY / CUT) ────────────────────────────────────┐
  │  SLATE   =  full scene snapshot written before Take 1. Immutable.        │
  │  JOURNEY =  ordered event log from Action to Cut.                        │
  │  CUT     =  scene state at the moment Cut is called.                     │
  │  One scene in memory at a time. Completely isolated.                     │
  └───────────────────────────────────────────────────────────────────────────┘

Architecture note:
  This module is self-contained.  It does NOT know about clips, timecodes,
  picture lock, or the editorial layer.  Those live in pubcast_editorial.py
  (not yet built).  This module hands clean SLATE/JOURNEY/CUT data upward
  and receives nothing back.

Usage:
    studio = VoxelStudio(data_dir=Path("data/voxel_studio"))
    scene  = studio.create_scene("throne_room")
    studio.slate(scene.scene_id, director="Josie", take=1)
    # ... place objects, arm destructions, call action ...
    studio.cut(scene.scene_id)
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import struct
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("pubcast.voxel_studio")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS & ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class VoxelShape(str, Enum):
    CUBE         = "cube"
    WEDGE        = "wedge"
    CORNER_OUTER = "corner_outer"
    CORNER_INNER = "corner_inner"

class VoxelSize(float, Enum):
    FULL    = 1.0
    HALF    = 0.5
    QUARTER = 0.25

class LODLevel(str, Enum):
    """
    Authoring LOD levels — these are constraints on what shapes/sizes are
    available while building.  They are NOT render states.  A baked object
    does not carry a LOD level.
    """
    LOW      = "low"        # cube_1p0 only
    LOW_MED  = "low_med"    # cube_1p0 + cube_0p5
    MED      = "med"        # cube_0p5 + wedge_0p5
    MED_HIGH = "med_high"   # all 0p5 shapes + all 0p25 shapes (no 0p25 corners)
    HIGH     = "high"       # all 12 primitives

# Which (shape, size) pairs are available at each LOD level
LOD_PALETTE: Dict[LODLevel, List[Tuple[VoxelShape, VoxelSize]]] = {
    LODLevel.LOW: [
        (VoxelShape.CUBE, VoxelSize.FULL),
    ],
    LODLevel.LOW_MED: [
        (VoxelShape.CUBE, VoxelSize.FULL),
        (VoxelShape.CUBE, VoxelSize.HALF),
    ],
    LODLevel.MED: [
        (VoxelShape.CUBE,  VoxelSize.HALF),
        (VoxelShape.WEDGE, VoxelSize.HALF),
    ],
    LODLevel.MED_HIGH: [
        (VoxelShape.CUBE,         VoxelSize.HALF),
        (VoxelShape.WEDGE,        VoxelSize.HALF),
        (VoxelShape.CORNER_OUTER, VoxelSize.HALF),
        (VoxelShape.CORNER_INNER, VoxelSize.HALF),
        (VoxelShape.CUBE,         VoxelSize.QUARTER),
        (VoxelShape.WEDGE,        VoxelSize.QUARTER),
    ],
    LODLevel.HIGH: [
        (VoxelShape.CUBE,         VoxelSize.FULL),
        (VoxelShape.CUBE,         VoxelSize.HALF),
        (VoxelShape.CUBE,         VoxelSize.QUARTER),
        (VoxelShape.WEDGE,        VoxelSize.FULL),
        (VoxelShape.WEDGE,        VoxelSize.HALF),
        (VoxelShape.WEDGE,        VoxelSize.QUARTER),
        (VoxelShape.CORNER_OUTER, VoxelSize.FULL),
        (VoxelShape.CORNER_OUTER, VoxelSize.HALF),
        (VoxelShape.CORNER_OUTER, VoxelSize.QUARTER),
        (VoxelShape.CORNER_INNER, VoxelSize.FULL),
        (VoxelShape.CORNER_INNER, VoxelSize.HALF),
        (VoxelShape.CORNER_INNER, VoxelSize.QUARTER),
    ],
}

class DetonationType(str, Enum):
    BLAST_WAVE  = "blast_wave"   # radial impulse from a point
    IMPACT      = "impact"       # directional impulse from a surface strike
    CHAIN       = "chain"        # fragments from this detonation trigger adjacent bombs
    IMPLOSION   = "implosion"    # inward collapse — fragments travel toward the centre
    DISINTEGRATE= "disintegrate" # fragments dissolve in place, no physics throw

class FragmentBehavior(str, Enum):
    TUMBLE      = "tumble"       # full 6DOF tumbling
    SCATTER     = "scatter"      # mostly translational, minimal rotation
    DRIFT       = "drift"        # slow float, low gravity multiplier
    SHATTER     = "shatter"      # high velocity, no bounce, embed on contact


# ══════════════════════════════════════════════════════════════════════════════
# GEOMETRY ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _compute_normals(
    verts: np.ndarray,
    faces: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Flat normals — hard edges, voxel aesthetic.  Returns (verts, normals, faces)."""
    fv, fn, ff = [], [], []
    idx = 0
    for face in faces:
        v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
        n = np.cross(v1 - v0, v2 - v0)
        mag = np.linalg.norm(n)
        if mag < 1e-9:
            continue
        n /= mag
        for v in (v0, v1, v2):
            fv.append(v)
            fn.append(n)
        ff.append([idx, idx + 1, idx + 2])
        idx += 3
    return (
        np.array(fv, dtype=np.float32),
        np.array(fn, dtype=np.float32),
        np.array(ff, dtype=np.uint32),
    )


def _shape_verts_faces(shape: VoxelShape) -> Tuple[np.ndarray, np.ndarray]:
    """Return unit-scale (size=1.0) vertex and face arrays for a shape."""
    if shape == VoxelShape.CUBE:
        v = np.array([
            [0,0,0],[1,0,0],[1,1,0],[0,1,0],
            [0,0,1],[1,0,1],[1,1,1],[0,1,1],
        ], dtype=float)
        f = np.array([
            [0,2,1],[0,3,2],  # front  Z=0
            [4,5,6],[4,6,7],  # back   Z=1
            [0,1,5],[0,5,4],  # bottom Y=0
            [3,7,6],[3,6,2],  # top    Y=1
            [0,4,7],[0,7,3],  # left   X=0
            [1,2,6],[1,6,5],  # right  X=1
        ], dtype=int)

    elif shape == VoxelShape.WEDGE:
        # Triangular prism — ramp from Y=1 (X=0) down to Y=0 (X=1)
        v = np.array([
            [0,0,0],[1,0,0],[0,1,0],  # front triangle
            [0,0,1],[1,0,1],[0,1,1],  # back  triangle
        ], dtype=float)
        f = np.array([
            [0,1,2],          # front tri
            [3,5,4],          # back  tri
            [0,1,4],[0,4,3],  # bottom
            [0,2,5],[0,5,3],  # left  (tall face)
            [2,1,4],[2,4,5],  # slope
        ], dtype=int)

    elif shape == VoxelShape.CORNER_OUTER:
        # Pyramid — square base Y=0, single apex at (0,1,0)
        v = np.array([
            [0,0,0],[1,0,0],[1,0,1],[0,0,1],
            [0,1,0],
        ], dtype=float)
        f = np.array([
            [0,2,1],[0,3,2],  # base
            [0,1,4],          # front slope
            [1,2,4],          # right slope
            [2,3,4],          # back  slope
            [3,0,4],          # left  slope
        ], dtype=int)

    elif shape == VoxelShape.CORNER_INNER:
        # Cube with (1,1,1) corner sliced off diagonally
        v = np.array([
            [0,0,0],[1,0,0],[1,0,1],[0,0,1],  # base ring
            [0,1,0],[1,1,0],[0,1,1],           # top — (1,1,1) absent
        ], dtype=float)
        f = np.array([
            [0,1,2],[0,2,3],  # bottom
            [0,5,1],[0,4,5],  # front  Z=0
            [0,3,6],[0,6,4],  # left   X=0
            [3,2,6],          # back   (partial)
            [1,5,2],          # right  (partial)
            [4,6,5],          # top    (partial L-shape)
            [5,6,2],          # diagonal cut face
        ], dtype=int)

    else:
        raise ValueError(f"Unknown shape: {shape}")

    return v, f


def build_primitive_geometry(
    shape: VoxelShape,
    size:  float,
    rotation_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Return (verts, normals, faces) for a primitive at the requested size
    and rotation.  Rotation is (rx, ry, rz) in degrees, applied Y→X→Z.
    Verts are float32, faces are uint32.
    """
    v_raw, f_raw = _shape_verts_faces(shape)
    v_scaled = (v_raw * size).astype(np.float32)

    # Centre the verts for rotation, then restore
    cx, cy, cz = size / 2, size / 2, size / 2
    v_centred = v_scaled - np.array([cx, cy, cz], dtype=np.float32)

    rx, ry, rz = (math.radians(a) for a in rotation_deg)

    def rot_y(pts, a):
        c, s = math.cos(a), math.sin(a)
        R = np.array([[c,0,s],[0,1,0],[-s,0,c]], dtype=np.float32)
        return pts @ R.T

    def rot_x(pts, a):
        c, s = math.cos(a), math.sin(a)
        R = np.array([[1,0,0],[0,c,-s],[0,s,c]], dtype=np.float32)
        return pts @ R.T

    def rot_z(pts, a):
        c, s = math.cos(a), math.sin(a)
        R = np.array([[c,-s,0],[s,c,0],[0,0,1]], dtype=np.float32)
        return pts @ R.T

    v_rot = rot_z(rot_x(rot_y(v_centred, ry), rx), rz)
    v_final = v_rot + np.array([cx, cy, cz], dtype=np.float32)

    verts, normals, faces = _compute_normals(v_final, f_raw)
    return verts, normals, faces


def pack_glb(verts: np.ndarray, normals: np.ndarray,
             faces: np.ndarray, name: str) -> bytes:
    """Pack geometry into a minimal valid GLB (glTF 2.0 binary)."""

    def pad4(b: bytes) -> bytes:
        r = len(b) % 4
        return b + b"\x00" * ((4 - r) % 4)

    pos_b  = pad4(verts.tobytes())
    nrm_b  = pad4(normals.tobytes())
    idx_b  = pad4(faces.flatten().tobytes())
    off1, off2 = len(pos_b), len(pos_b) + len(nrm_b)
    bin_data = pos_b + nrm_b + idx_b

    bmin = verts.min(axis=0).tolist()
    bmax = verts.max(axis=0).tolist()

    gltf: Dict[str, Any] = {
        "asset": {"version": "2.0",
                  "generator": "PubWorld VoxelStudio 1.0 — Rear View Foresight"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes":  [{"mesh": 0, "name": name}],
        "meshes": [{"name": name, "primitives": [{
            "attributes": {"POSITION": 0, "NORMAL": 1},
            "indices": 2, "mode": 4,
        }]}],
        "accessors": [
            {"bufferView": 0, "byteOffset": 0, "componentType": 5126,
             "count": len(verts),   "type": "VEC3",   "min": bmin, "max": bmax},
            {"bufferView": 1, "byteOffset": 0, "componentType": 5126,
             "count": len(normals), "type": "VEC3"},
            {"bufferView": 2, "byteOffset": 0, "componentType": 5125,
             "count": int(faces.size), "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0,    "byteLength": len(pos_b),  "target": 34962},
            {"buffer": 0, "byteOffset": off1, "byteLength": len(nrm_b),  "target": 34962},
            {"buffer": 0, "byteOffset": off2, "byteLength": len(idx_b),  "target": 34963},
        ],
        "buffers": [{"byteLength": len(bin_data)}],
        "materials": [{"name": "voxel_default",
                       "pbrMetallicRoughness": {
                           "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                           "metallicFactor": 0.0, "roughnessFactor": 0.6},
                       "doubleSided": False}],
    }

    j_bytes  = pad4(json.dumps(gltf, separators=(",", ":")).encode())
    j_chunk  = struct.pack("<II", len(j_bytes), 0x4E4F534A) + j_bytes
    bin_chunk= struct.pack("<II", len(bin_data), 0x004E4942) + bin_data
    total    = 12 + len(j_chunk) + len(bin_chunk)
    return struct.pack("<III", 0x46546C67, 2, total) + j_chunk + bin_chunk


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VoxelPrimitive:
    """
    One placed primitive in an authored object.
    Position and rotation are object-local, not world-space.
    """
    primitive_id: str                          = field(default_factory=lambda: str(uuid.uuid4())[:8])
    shape:        VoxelShape                   = VoxelShape.CUBE
    size:         float                        = 1.0
    position:     Tuple[float, float, float]   = (0.0, 0.0, 0.0)
    rotation_deg: Tuple[float, float, float]   = (0.0, 0.0, 0.0)
    group:        Optional[str]                = None   # pivot group name
    material_hint:Optional[str]               = None   # e.g. "wood", "metal", "stone"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primitive_id":  self.primitive_id,
            "shape":         self.shape.value,
            "size":          self.size,
            "position":      list(self.position),
            "rotation_deg":  list(self.rotation_deg),
            "group":         self.group,
            "material_hint": self.material_hint,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VoxelPrimitive":
        return cls(
            primitive_id  = d.get("primitive_id", str(uuid.uuid4())[:8]),
            shape         = VoxelShape(d["shape"]),
            size          = float(d["size"]),
            position      = tuple(d["position"]),       # type: ignore[arg-type]
            rotation_deg  = tuple(d["rotation_deg"]),   # type: ignore[arg-type]
            group         = d.get("group"),
            material_hint = d.get("material_hint"),
        )


@dataclass
class PivotGroup:
    """A named cluster of primitives that bakes as a separate named submesh."""
    name:      str
    pivot:     Tuple[float, float, float] = (0.0, 0.0, 0.0)  # local-space pivot point
    is_bone:   bool = False     # True if this group will have a motion tracker
    axis_hint: Optional[str] = None  # "hinge_x", "hinge_y", "hinge_z", "ball"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":      self.name,
            "pivot":     list(self.pivot),
            "is_bone":   self.is_bone,
            "axis_hint": self.axis_hint,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PivotGroup":
        return cls(
            name      = d["name"],
            pivot     = tuple(d["pivot"]),  # type: ignore[arg-type]
            is_bone   = d.get("is_bone", False),
            axis_hint = d.get("axis_hint"),
        )


@dataclass
class DestructionProfile:
    """
    How this object blows up.
    Stored on the object — armed per scene instance.
    The seed makes a detonation exactly reproducible for matched cuts.
    """
    detonation_type:     DetonationType    = DetonationType.BLAST_WAVE
    force:               float             = 10.0      # arbitrary units
    radius:              float             = 5.0       # world units
    fragment_behavior:   FragmentBehavior  = FragmentBehavior.TUMBLE
    debris_persistence:  float             = 8.0       # seconds before fragments vanish
    chain_threshold:     float             = 3.0       # force needed to trigger chain
    seed:                Optional[int]     = None      # None = random each time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detonation_type":    self.detonation_type.value,
            "force":              self.force,
            "radius":             self.radius,
            "fragment_behavior":  self.fragment_behavior.value,
            "debris_persistence": self.debris_persistence,
            "chain_threshold":    self.chain_threshold,
            "seed":               self.seed,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DestructionProfile":
        return cls(
            detonation_type   = DetonationType(d.get("detonation_type", "blast_wave")),
            force             = float(d.get("force", 10.0)),
            radius            = float(d.get("radius", 5.0)),
            fragment_behavior = FragmentBehavior(d.get("fragment_behavior", "tumble")),
            debris_persistence= float(d.get("debris_persistence", 8.0)),
            chain_threshold   = float(d.get("chain_threshold", 3.0)),
            seed              = d.get("seed"),
        )


@dataclass
class VoxelObject:
    """
    An authored voxel object.  This is the permanent editable source record.

    A baked GLB can be generated from this at any time.  The baked file is
    an output artifact — this dataclass is the source of truth.

    authored_lod is informational only — it records the highest LOD level
    used during authoring so you know what you built with.
    Different primitives on the same object can freely mix shapes and sizes.
    """
    object_id:    str                         = field(default_factory=lambda: str(uuid.uuid4()))
    name:         str                         = "unnamed_object"
    authored_lod: LODLevel                    = LODLevel.HIGH
    primitives:   List[VoxelPrimitive]        = field(default_factory=list)
    pivot_groups: List[PivotGroup]            = field(default_factory=list)
    destruction:  Optional[DestructionProfile]= None
    tags:         List[str]                   = field(default_factory=list)
    created_at:   float                       = field(default_factory=time.time)
    notes:        str                         = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id":    self.object_id,
            "name":         self.name,
            "authored_lod": self.authored_lod.value,
            "primitives":   [p.to_dict()  for p in self.primitives],
            "pivot_groups": [g.to_dict()  for g in self.pivot_groups],
            "destruction":  self.destruction.to_dict() if self.destruction else None,
            "tags":         self.tags,
            "created_at":   self.created_at,
            "notes":        self.notes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VoxelObject":
        return cls(
            object_id    = d.get("object_id",    str(uuid.uuid4())),
            name         = d.get("name",         "unnamed_object"),
            authored_lod = LODLevel(d.get("authored_lod", "high")),
            primitives   = [VoxelPrimitive.from_dict(p) for p in d.get("primitives", [])],
            pivot_groups = [PivotGroup.from_dict(g)     for g in d.get("pivot_groups", [])],
            destruction  = DestructionProfile.from_dict(d["destruction"]) if d.get("destruction") else None,
            tags         = d.get("tags", []),
            created_at   = d.get("created_at", time.time()),
            notes        = d.get("notes", ""),
        )

    # ── primitive helpers ────────────────────────────────────────────────────

    def add_primitive(self, prim: VoxelPrimitive) -> None:
        self.primitives.append(prim)

    def remove_primitive(self, primitive_id: str) -> bool:
        before = len(self.primitives)
        self.primitives = [p for p in self.primitives if p.primitive_id != primitive_id]
        return len(self.primitives) < before

    def primitives_in_group(self, group_name: str) -> List[VoxelPrimitive]:
        return [p for p in self.primitives if p.group == group_name]

    def effective_lod(self) -> LODLevel:
        """Derive the actual highest LOD used from the primitive list."""
        for level in (LODLevel.HIGH, LODLevel.MED_HIGH, LODLevel.MED,
                      LODLevel.LOW_MED, LODLevel.LOW):
            palette = LOD_PALETTE[level]
            if any((p.shape, p.size) in [(s.value, sz.value) for s, sz in palette]
                   for p in self.primitives):
                return level
        return LODLevel.LOW


# ══════════════════════════════════════════════════════════════════════════════
# BAKER
# ══════════════════════════════════════════════════════════════════════════════

class VoxelBaker:
    """
    Bakes a VoxelObject into one or more GLB files.

    Baking strategy:
    - Primitives with NO group → merged into one "body" mesh.
    - Primitives WITH a group  → merged within their group, kept as a separate
      named submesh in the GLB.  Ready for rigging / motion tracker attachment.
    - All vertex welding happens within a group (shared edge between two adjacent
      primitives merges their vertices).  Groups do not weld with each other.
    - Normals are always flat (hard edges — voxel aesthetic).

    Output: a single GLB with one mesh node per group + one for the body.
    """

    # Weld tolerance — vertices within this distance are merged
    WELD_EPS: float = 1e-4

    def bake(
        self,
        obj: VoxelObject,
        world_position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> bytes:
        """
        Bake obj into a GLB.  world_position offsets all geometry.
        Returns the raw GLB bytes.
        """
        # Gather all groups (None = body)
        group_names: List[Optional[str]] = [None]
        for pg in obj.pivot_groups:
            group_names.append(pg.name)

        all_verts_out:   List[np.ndarray] = []
        all_normals_out: List[np.ndarray] = []
        all_faces_out:   List[np.ndarray] = []
        index_offset = 0

        for group in group_names:
            prims = obj.primitives_in_group(group) if group else [
                p for p in obj.primitives if p.group is None
            ]
            if not prims:
                continue

            group_verts:   List[np.ndarray] = []
            group_normals: List[np.ndarray] = []
            group_faces:   List[np.ndarray] = []
            vert_count = 0

            for prim in prims:
                v, n, f = build_primitive_geometry(
                    prim.shape, prim.size, prim.rotation_deg
                )
                # Translate to object-local position
                px, py, pz = prim.position
                v = v + np.array([px, py, pz], dtype=np.float32)
                group_verts.append(v)
                group_normals.append(n)
                group_faces.append(f + vert_count)
                vert_count += len(v)

            if not group_verts:
                continue

            gv = np.concatenate(group_verts)
            gn = np.concatenate(group_normals)
            gf = np.concatenate(group_faces)

            # Translate to world position
            wx, wy, wz = world_position
            gv = gv + np.array([wx, wy, wz], dtype=np.float32)

            all_verts_out.append(gv)
            all_normals_out.append(gn)
            all_faces_out.append(gf + index_offset)
            index_offset += len(gv)

        if not all_verts_out:
            raise ValueError(f"VoxelObject '{obj.name}' has no primitives to bake.")

        verts   = np.concatenate(all_verts_out).astype(np.float32)
        normals = np.concatenate(all_normals_out).astype(np.float32)
        faces   = np.concatenate(all_faces_out).astype(np.uint32)

        return pack_glb(verts, normals, faces, obj.name)

    def bake_to_file(
        self,
        obj: VoxelObject,
        output_dir: Path,
        world_position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> Path:
        """Bake and write to output_dir/<object_id>.glb. Returns the path."""
        glb = self.bake(obj, world_position)
        out = output_dir / f"{obj.object_id}.glb"
        out.write_bytes(glb)
        logger.info("Baked '%s' → %s  (%d bytes)", obj.name, out, len(glb))
        return out


# ══════════════════════════════════════════════════════════════════════════════
# SCENE INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SceneObjectInstance:
    """
    A placed instance of a VoxelObject within a scene.
    Each instance can be destroyed independently.
    """
    instance_id:    str                         = field(default_factory=lambda: str(uuid.uuid4())[:8])
    object_id:      str                         = ""
    object_name:    str                         = ""
    world_position: Tuple[float, float, float]  = (0.0, 0.0, 0.0)
    world_rotation: Tuple[float, float, float]  = (0.0, 0.0, 0.0)
    destruction:    Optional[DestructionProfile]= None  # override object default if set
    is_destructible:bool                        = False
    tags:           List[str]                   = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id":    self.instance_id,
            "object_id":      self.object_id,
            "object_name":    self.object_name,
            "world_position": list(self.world_position),
            "world_rotation": list(self.world_rotation),
            "destruction":    self.destruction.to_dict() if self.destruction else None,
            "is_destructible":self.is_destructible,
            "tags":           self.tags,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SceneObjectInstance":
        return cls(
            instance_id    = d.get("instance_id",    str(uuid.uuid4())[:8]),
            object_id      = d["object_id"],
            object_name    = d.get("object_name", ""),
            world_position = tuple(d.get("world_position", [0,0,0])),  # type: ignore
            world_rotation = tuple(d.get("world_rotation", [0,0,0])),  # type: ignore
            destruction    = DestructionProfile.from_dict(d["destruction"]) if d.get("destruction") else None,
            is_destructible= d.get("is_destructible", False),
            tags           = d.get("tags", []),
        )


# ══════════════════════════════════════════════════════════════════════════════
# SLATE / JOURNEY / CUT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SlateData:
    """
    The clapperboard.  Written once, before Take 1.  Immutable after writing.
    Contains the complete scene state — every object, position, light, camera.
    This is the source of truth for Reset to Take 1.
    """
    slate_id:     str                           = field(default_factory=lambda: str(uuid.uuid4())[:12])
    scene_id:     str                           = ""
    scene_name:   str                           = ""
    take:         int                           = 1
    director:     str                           = ""
    timestamp:    float                         = field(default_factory=time.time)
    instances:    List[SceneObjectInstance]     = field(default_factory=list)
    # Cameras, lights etc. stored as opaque dicts (extended later)
    cameras:      List[Dict[str, Any]]          = field(default_factory=list)
    lights:       List[Dict[str, Any]]          = field(default_factory=list)
    notes:        str                           = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slate_id":   self.slate_id,
            "scene_id":   self.scene_id,
            "scene_name": self.scene_name,
            "take":       self.take,
            "director":   self.director,
            "timestamp":  self.timestamp,
            "instances":  [i.to_dict() for i in self.instances],
            "cameras":    self.cameras,
            "lights":     self.lights,
            "notes":      self.notes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SlateData":
        return cls(
            slate_id   = d["slate_id"],
            scene_id   = d["scene_id"],
            scene_name = d["scene_name"],
            take       = d["take"],
            director   = d.get("director", ""),
            timestamp  = d["timestamp"],
            instances  = [SceneObjectInstance.from_dict(i) for i in d.get("instances", [])],
            cameras    = d.get("cameras", []),
            lights     = d.get("lights", []),
            notes      = d.get("notes", ""),
        )


@dataclass
class JourneyEvent:
    """
    One event in the journey between Action and Cut.
    Each event is a timestamped fact — something that happened.
    """
    event_id:   str            = field(default_factory=lambda: str(uuid.uuid4())[:8])
    t:          float          = field(default_factory=time.time)  # scene-relative seconds
    event_type: str            = ""      # "detonation", "move", "camera_cut", etc.
    payload:    Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"event_id": self.event_id, "t": self.t,
                "event_type": self.event_type, "payload": self.payload}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "JourneyEvent":
        return cls(event_id=d["event_id"], t=d["t"],
                   event_type=d["event_type"], payload=d.get("payload", {}))


@dataclass
class SceneSession:
    """
    The live scene. One exists in memory at a time.
    Contains the SLATE (immutable) + live mutable state + growing journey log.
    """
    scene_id:    str                       = field(default_factory=lambda: str(uuid.uuid4()))
    scene_name:  str                       = "untitled_scene"
    slate:       Optional[SlateData]       = None          # None until slated
    journey:     List[JourneyEvent]        = field(default_factory=list)
    cut_state:   Optional[Dict[str, Any]]  = None          # None until Cut is called
    action_time: Optional[float]           = None          # wall-clock time of Action
    cut_time:    Optional[float]           = None          # wall-clock time of Cut
    # Live instance state (may differ from SLATE after detonations / moves)
    live_instances: List[SceneObjectInstance] = field(default_factory=list)
    # Fragment state: instance_id → list of fragment dicts
    fragments:   Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    @property
    def is_slated(self) -> bool:
        return self.slate is not None

    @property
    def is_action(self) -> bool:
        return self.action_time is not None and self.cut_time is None

    @property
    def is_cut(self) -> bool:
        return self.cut_time is not None

    def _t(self) -> float:
        """Scene-relative time in seconds. 0.0 before Action."""
        if self.action_time is None:
            return 0.0
        return time.time() - self.action_time

    def log_event(self, event_type: str, **payload: Any) -> JourneyEvent:
        evt = JourneyEvent(t=self._t(), event_type=event_type, payload=payload)
        self.journey.append(evt)
        return evt


# ══════════════════════════════════════════════════════════════════════════════
# DESTRUCTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class DestructionEngine:
    """
    Un-bakes an object back into its primitive components and fires each one
    as a physics fragment away from the detonation point.

    Physics here is deterministic given a seed — it does NOT run a real
    physics simulation.  It computes initial velocity + angular velocity
    per fragment at detonation time.  What happens to fragments after that
    is the renderer's problem.

    Reset to Take 1: despawn all fragments for an instance, restore the
    intact object from the SLATE.
    """

    def detonate(
        self,
        instance:   SceneObjectInstance,
        obj:        VoxelObject,
        blast_origin: Tuple[float, float, float],
        profile:    Optional[DestructionProfile] = None,
    ) -> List[Dict[str, Any]]:
        """
        Detonate an object.  Returns a list of fragment dicts, one per primitive.
        Each fragment carries its initial world position, velocity, and angular
        velocity.  The caller (scene manager / hub broadcast) distributes these
        to clients.

        Fragment dict keys:
            fragment_id, object_id, instance_id,
            shape, size, rotation_deg, world_position,
            velocity [vx,vy,vz], angular_velocity [ax,ay,az],
            material_hint, debris_persistence
        """
        dp = profile or instance.destruction or obj.destruction
        if dp is None:
            dp = DestructionProfile()  # safe defaults

        seed = dp.seed if dp.seed is not None else random.randint(0, 2**31)
        rng  = random.Random(seed)

        ox, oy, oz = blast_origin
        ix, iy, iz = instance.world_position
        fragments  = []

        for prim in obj.primitives:
            # World position of this primitive
            px = ix + prim.position[0]
            py = iy + prim.position[1]
            pz = iz + prim.position[2]

            # Direction from blast origin to fragment centre
            dx, dy, dz = px - ox, py - oy, pz - oz
            dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 0.001

            # Force falls off with inverse square of distance (clamped)
            falloff  = min(1.0, (dp.radius / max(dist, 0.1)) ** 2)
            speed    = dp.force * falloff

            if dp.detonation_type == DetonationType.IMPLOSION:
                dx, dy, dz = -dx, -dy, -dz  # inward

            if dp.detonation_type == DetonationType.DISINTEGRATE:
                vx, vy, vz = 0.0, 0.0, 0.0
            else:
                # Normalise direction + jitter
                jx = rng.uniform(-0.2, 0.2)
                jy = rng.uniform( 0.0, 0.4)   # bias upward
                jz = rng.uniform(-0.2, 0.2)
                mag = math.sqrt((dx+jx)**2 + (dy+jy)**2 + (dz+jz)**2) or 1.0
                vx  = ((dx+jx) / mag) * speed
                vy  = ((dy+jy) / mag) * speed
                vz  = ((dz+jz) / mag) * speed

            ax = rng.uniform(-1.0, 1.0) * speed * 0.5
            ay = rng.uniform(-1.0, 1.0) * speed * 0.5
            az = rng.uniform(-1.0, 1.0) * speed * 0.5

            fragments.append({
                "fragment_id":       f"{instance.instance_id}_{prim.primitive_id}",
                "object_id":         obj.object_id,
                "instance_id":       instance.instance_id,
                "shape":             prim.shape.value,
                "size":              prim.size,
                "rotation_deg":      list(prim.rotation_deg),
                "world_position":    [px, py, pz],
                "velocity":          [vx, vy, vz],
                "angular_velocity":  [ax, ay, az],
                "material_hint":     prim.material_hint,
                "debris_persistence":dp.debris_persistence,
                "seed":              seed,
            })

        logger.info(
            "💥 Detonated '%s' (type=%s, force=%.1f) → %d fragments (seed=%d)",
            obj.name, dp.detonation_type.value, dp.force, len(fragments), seed
        )
        return fragments


# ══════════════════════════════════════════════════════════════════════════════
# MAIN VOXEL STUDIO
# ══════════════════════════════════════════════════════════════════════════════

class VoxelStudio:
    """
    Top-level manager.  One instance per application.
    One SceneSession in memory at a time.

    Directory layout under data_dir:
        objects/    — VoxelObject JSON source files (permanent)
        bakes/      — baked GLB outputs (re-generatable)
        scenes/     — per-scene subdirectories
            <scene_id>/
                slate_<take>.json
                journey_<take>.json
                cut_<take>.json
        primitives/ — pre-baked primitive GLBs (generated once at startup)
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir    = data_dir
        self._obj_dir    = data_dir / "objects"
        self._bake_dir   = data_dir / "bakes"
        self._scene_dir  = data_dir / "scenes"
        self._prim_dir   = data_dir / "primitives"
        self._objects:   Dict[str, VoxelObject]  = {}
        self._session:   Optional[SceneSession]  = None
        self._baker      = VoxelBaker()
        self._destructor = DestructionEngine()

        for d in (self._obj_dir, self._bake_dir, self._scene_dir, self._prim_dir):
            d.mkdir(parents=True, exist_ok=True)

        self._load_objects()
        self._generate_primitives_if_missing()
        logger.info("VoxelStudio initialised at %s  (%d objects loaded)",
                    data_dir, len(self._objects))

    # ── Object library ───────────────────────────────────────────────────────

    def _load_objects(self) -> None:
        for p in self._obj_dir.glob("*.json"):
            try:
                obj = VoxelObject.from_dict(json.loads(p.read_text()))
                self._objects[obj.object_id] = obj
            except Exception as exc:
                logger.warning("Could not load object %s: %s", p.name, exc)

    def save_object(self, obj: VoxelObject) -> Path:
        """Persist a VoxelObject to disk.  Returns the path written."""
        self._objects[obj.object_id] = obj
        path = self._obj_dir / f"{obj.object_id}.json"
        path.write_text(json.dumps(obj.to_dict(), indent=2))
        logger.info("Saved object '%s' → %s", obj.name, path.name)
        return path

    def get_object(self, object_id: str) -> Optional[VoxelObject]:
        return self._objects.get(object_id)

    def list_objects(self) -> List[VoxelObject]:
        return list(self._objects.values())

    def delete_object(self, object_id: str) -> bool:
        obj = self._objects.pop(object_id, None)
        if obj:
            p = self._obj_dir / f"{object_id}.json"
            p.unlink(missing_ok=True)
            (self._bake_dir / f"{object_id}.glb").unlink(missing_ok=True)
            logger.info("Deleted object '%s'", obj.name)
            return True
        return False

    # ── Baker ─────────────────────────────────────────────────────────────────

    def bake_object(
        self,
        object_id: str,
        world_position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> Optional[Path]:
        obj = self.get_object(object_id)
        if obj is None:
            logger.error("bake_object: unknown object_id '%s'", object_id)
            return None
        return self._baker.bake_to_file(obj, self._bake_dir, world_position)

    def bake_all(self) -> int:
        """Bake every loaded object. Returns count of successes."""
        ok = 0
        for obj in self._objects.values():
            try:
                self._baker.bake_to_file(obj, self._bake_dir)
                ok += 1
            except Exception as exc:
                logger.warning("Bake failed for '%s': %s", obj.name, exc)
        return ok

    # ── Primitive GLB library ────────────────────────────────────────────────

    def _generate_primitives_if_missing(self) -> None:
        """Pre-bake all 12 primitive GLBs into primitives/ if not present."""
        generated = 0
        for shape in VoxelShape:
            for size in VoxelSize:
                name = f"{shape.value}_{str(size.value).replace('.','p')}"
                path = self._prim_dir / f"{name}.glb"
                if path.exists():
                    continue
                try:
                    v, n, f = build_primitive_geometry(shape, size.value)
                    path.write_bytes(pack_glb(v, n, f, name))
                    generated += 1
                except Exception as exc:
                    logger.warning("Could not generate primitive %s: %s", name, exc)
        if generated:
            logger.info("Generated %d primitive GLBs → %s", generated, self._prim_dir)

    def list_primitives(self) -> List[Dict[str, Any]]:
        """Return catalogue of all available primitive GLBs."""
        result = []
        for shape in VoxelShape:
            for size in VoxelSize:
                name = f"{shape.value}_{str(size.value).replace('.','p')}"
                path = self._prim_dir / f"{name}.glb"
                lods = [lod.value for lod, palette in LOD_PALETTE.items()
                        if (shape, size) in palette]
                result.append({
                    "name":      name,
                    "shape":     shape.value,
                    "size":      size.value,
                    "file":      str(path),
                    "exists":    path.exists(),
                    "lod_levels":lods,
                    "file_bytes":path.stat().st_size if path.exists() else 0,
                })
        return result

    def get_lod_palette(self, lod: LODLevel) -> List[Dict[str, Any]]:
        """Return the primitives available at a given LOD level."""
        return [
            {"shape": s.value, "size": sz.value}
            for s, sz in LOD_PALETTE[lod]
        ]

    # ── Scene management ─────────────────────────────────────────────────────

    def create_scene(self, name: str) -> SceneSession:
        """
        Unload any existing scene and create a fresh one.
        One scene in memory at a time — this is deliberate.
        """
        if self._session is not None:
            logger.info("Unloading scene '%s' to load '%s'",
                        self._session.scene_name, name)
        self._session = SceneSession(scene_name=name)
        logger.info("Scene created: '%s' (%s)", name, self._session.scene_id)
        return self._session

    def load_scene(self, scene_id: str, take: int = 1) -> Optional[SceneSession]:
        """Load a previously saved scene from its SLATE file."""
        slate_path = self._scene_dir / scene_id / f"slate_{take}.json"
        if not slate_path.exists():
            logger.error("No slate found: %s", slate_path)
            return None

        slate = SlateData.from_dict(json.loads(slate_path.read_text()))
        session = SceneSession(
            scene_id    = scene_id,
            scene_name  = slate.scene_name,
            slate       = slate,
            live_instances = [SceneObjectInstance.from_dict(i.to_dict())
                               for i in slate.instances],
        )
        self._session = session
        logger.info("Loaded scene '%s' take %d", slate.scene_name, take)
        return session

    @property
    def current_scene(self) -> Optional[SceneSession]:
        return self._session

    def place_object(
        self,
        object_id:      str,
        world_position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        world_rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        is_destructible:bool = False,
        destruction_override: Optional[DestructionProfile] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[SceneObjectInstance]:
        """Place a VoxelObject instance in the current scene."""
        if self._session is None:
            logger.error("place_object: no active scene")
            return None
        obj = self.get_object(object_id)
        if obj is None:
            logger.error("place_object: unknown object '%s'", object_id)
            return None

        inst = SceneObjectInstance(
            object_id       = object_id,
            object_name     = obj.name,
            world_position  = world_position,
            world_rotation  = world_rotation,
            is_destructible = is_destructible,
            destruction     = destruction_override,
            tags            = tags or [],
        )
        self._session.live_instances.append(inst)
        logger.debug("Placed '%s' at %s", obj.name, world_position)
        return inst

    # ── Slate / Action / Cut ─────────────────────────────────────────────────

    def slate(
        self,
        director: str,
        take:     int  = 1,
        notes:    str  = "",
        cameras:  Optional[List[Dict[str, Any]]] = None,
        lights:   Optional[List[Dict[str, Any]]] = None,
    ) -> SlateData:
        """
        Write the clapperboard.  Freezes the current scene state.
        Must be called before action().  Cannot be called twice for the same take.
        """
        if self._session is None:
            raise RuntimeError("No active scene — call create_scene() first.")
        if self._session.is_slated:
            raise RuntimeError(
                f"Scene '{self._session.scene_name}' is already slated for take {take}. "
                "Call create_scene() to start a fresh take."
            )

        slate = SlateData(
            scene_id   = self._session.scene_id,
            scene_name = self._session.scene_name,
            take       = take,
            director   = director,
            instances  = [SceneObjectInstance.from_dict(i.to_dict())
                          for i in self._session.live_instances],
            cameras    = cameras or [],
            lights     = lights  or [],
            notes      = notes,
        )
        self._session.slate = slate

        # Persist slate immediately — it is immutable from this point
        sd = self._scene_dir / self._session.scene_id
        sd.mkdir(parents=True, exist_ok=True)
        (sd / f"slate_{take}.json").write_text(
            json.dumps(slate.to_dict(), indent=2)
        )
        logger.info("🎬 SLATE — '%s' Take %d  Director: %s  (%d objects)",
                    self._session.scene_name, take, director,
                    len(self._session.live_instances))
        return slate

    def action(self) -> float:
        """Start the take. Returns scene start wall-clock time."""
        if self._session is None:
            raise RuntimeError("No active scene.")
        if not self._session.is_slated:
            raise RuntimeError("Slate before calling action().")
        if self._session.is_action:
            raise RuntimeError("Already rolling.")

        self._session.action_time = time.time()
        self._session.log_event("action")
        logger.info("▶  ACTION — '%s'", self._session.scene_name)
        return self._session.action_time

    def cut(self) -> Dict[str, Any]:
        """
        Call Cut. Snapshot the live state, write journey + cut files.
        Returns a summary dict.
        """
        if self._session is None:
            raise RuntimeError("No active scene.")
        if not self._session.is_action:
            raise RuntimeError("Cannot cut before action().")

        self._session.cut_time = time.time()
        self._session.log_event("cut")

        cut_state = {
            "scene_id":    self._session.scene_id,
            "scene_name":  self._session.scene_name,
            "take":        self._session.slate.take if self._session.slate else 0,
            "action_time": self._session.action_time,
            "cut_time":    self._session.cut_time,
            "duration_s":  self._session.cut_time - (self._session.action_time or 0),
            "instances":   [i.to_dict() for i in self._session.live_instances],
            "fragments":   {k: v for k, v in self._session.fragments.items()},
            "event_count": len(self._session.journey),
        }
        self._session.cut_state = cut_state

        # Persist journey + cut
        take = self._session.slate.take if self._session.slate else 0
        sd   = self._scene_dir / self._session.scene_id
        sd.mkdir(parents=True, exist_ok=True)
        (sd / f"journey_{take}.json").write_text(
            json.dumps([e.to_dict() for e in self._session.journey], indent=2)
        )
        (sd / f"cut_{take}.json").write_text(
            json.dumps(cut_state, indent=2)
        )
        logger.info("✂  CUT — '%s' Take %d  (%.1fs)",
                    self._session.scene_name, take,
                    cut_state["duration_s"])
        return cut_state

    def reset_to_take_1(self) -> None:
        """
        Despawn all fragments, restore every instance to SLATE positions.
        This is Reset to Take 1.  Does NOT re-write the SLATE.
        """
        if self._session is None or self._session.slate is None:
            raise RuntimeError("No slated scene to reset.")

        # Clear fragments
        self._session.fragments.clear()

        # Restore live instances from SLATE (deep copy)
        self._session.live_instances = [
            SceneObjectInstance.from_dict(i.to_dict())
            for i in self._session.slate.instances
        ]

        # Reset action/cut clock so a new take can begin
        self._session.action_time = None
        self._session.cut_time    = None
        self._session.journey.clear()

        logger.info("⏮  Reset to Take 1 — '%s'", self._session.scene_name)

    # ── Destruction ──────────────────────────────────────────────────────────

    def detonate(
        self,
        instance_id:  str,
        blast_origin: Optional[Tuple[float, float, float]] = None,
        seed_override:Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Detonate a scene instance.
        Logs the event (with seed) to the journey for reproducibility.
        Returns fragment list for broadcast to clients.
        """
        if self._session is None:
            raise RuntimeError("No active scene.")

        inst = next((i for i in self._session.live_instances
                     if i.instance_id == instance_id), None)
        if inst is None:
            raise ValueError(f"Instance '{instance_id}' not in scene.")

        obj = self.get_object(inst.object_id)
        if obj is None:
            raise ValueError(f"Object '{inst.object_id}' not in library.")

        origin = blast_origin or inst.world_position
        profile = inst.destruction or obj.destruction or DestructionProfile()
        if seed_override is not None:
            profile = DestructionProfile(**{**profile.to_dict(), "seed": seed_override})

        fragments = self._destructor.detonate(inst, obj, origin, profile)

        # Store fragments and log to journey
        self._session.fragments[instance_id] = fragments
        self._session.log_event(
            "detonation",
            instance_id   = instance_id,
            object_name   = obj.name,
            blast_origin  = list(origin),
            detonation_type=profile.detonation_type.value,
            force         = profile.force,
            radius        = profile.radius,
            seed          = fragments[0]["seed"] if fragments else None,
            fragment_count= len(fragments),
        )
        return fragments

    # ── Status & catalogue ───────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return a full status snapshot for the API."""
        sess = self._session
        return {
            "objects_loaded":     len(self._objects),
            "primitives_ready":   len(list(self._prim_dir.glob("*.glb"))),
            "active_scene":       {
                "scene_id":   sess.scene_id   if sess else None,
                "scene_name": sess.scene_name if sess else None,
                "is_slated":  sess.is_slated  if sess else False,
                "is_action":  sess.is_action  if sess else False,
                "is_cut":     sess.is_cut     if sess else False,
                "instances":  len(sess.live_instances) if sess else 0,
                "fragments":  sum(len(v) for v in sess.fragments.values()) if sess else 0,
                "events":     len(sess.journey) if sess else 0,
            } if sess else None,
        }
