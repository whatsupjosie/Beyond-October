# PubCast AI — avatar_imports.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""Imported avatars: any 3D character, stored as a canonical-height GLB.

The browser importer (static/js/avatar/avatar_import.js) reads GLB, glTF, OBJ
or FBX, normalises orientation and scale, and exports one GLB. This module is
the storage side, and it does not trust the browser: every upload is parsed,
its standing height is measured from the file itself, and it is refused unless
that height matches the canonical height declared for it.

Units: one glTF unit is one metre. A 5'8" character must measure 1.727 m tall.
Every room then sizes avatars from one pixels-per-metre scale, so the cast and
anything imported stay in proportion instead of filling the screen.
"""
from __future__ import annotations

import json
import os
import re
import struct
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from .route_security import current_identity

INCH_M = 0.0254
MAX_GLB_BYTES = 200 * 1024 * 1024
MIN_HEIGHT_IN = 6.0          # a small pet or prop character
MAX_HEIGHT_IN = 240.0        # 20 ft: tall creatures allowed, nothing city-sized
HEIGHT_TOLERANCE = 0.03      # measured height may differ from declared by 3 %
_GLB_MAGIC = 0x46546C67      # b"glTF"
_CHUNK_JSON = 0x4E4F534A
_CHUNK_BIN = 0x004E4942
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_COMPONENT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_TYPE_SIZE = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}

DEFAULT_HEIGHTS: Dict[str, Any] = {
    "unit": "inches",
    "note": ("Canonical standing heights. Every avatar in the world is sized from these, "
             "so the cast stays in proportion in every room. Edit a number here to change it."),
    "cast": {
        "sir_purfluous": {"name": "Sir Purfluous", "height_in": 74},
        "pete": {"name": "Pete", "height_in": 68},
        "repete": {"name": "RePete", "height_in": 70},
    },
    "default_adult_in": 68,
}


class GLBError(ValueError):
    """The file is not a well-formed, measurable glTF 2.0 binary."""


# ── GLB parsing and measurement ────────────────────────────────────────────

def parse_glb(data: bytes) -> Tuple[Dict[str, Any], bytes]:
    if len(data) < 20:
        raise GLBError("file is too small to be a GLB")
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != _GLB_MAGIC:
        raise GLBError("not a GLB file (missing glTF header)")
    if version != 2:
        raise GLBError(f"unsupported GLB version {version}; glTF 2.0 is required")
    if length != len(data):
        raise GLBError("GLB length header does not match the file size (truncated or padded)")
    offset, gltf, binary = 12, None, b""
    while offset + 8 <= length:
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        start, end = offset + 8, offset + 8 + chunk_len
        if end > length:
            raise GLBError("GLB chunk runs past the end of the file")
        if chunk_type == _CHUNK_JSON and gltf is None:
            try:
                gltf = json.loads(data[start:end].decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise GLBError(f"GLB JSON chunk is not valid JSON: {exc}") from None
        elif chunk_type == _CHUNK_BIN and not binary:
            binary = data[start:end]
        offset = end
    if not isinstance(gltf, dict):
        raise GLBError("GLB has no JSON chunk")
    if str(gltf.get("asset", {}).get("version", "")) != "2.0":
        raise GLBError("glTF asset.version must be 2.0")
    return gltf, binary


def _node_local(node: Dict[str, Any]) -> np.ndarray:
    if "matrix" in node:
        return np.array(node["matrix"], dtype=float).reshape(4, 4).T  # glTF is column-major
    t = np.array(node.get("translation", [0, 0, 0]), dtype=float)
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    s = np.array(node.get("scale", [1, 1, 1]), dtype=float)
    r = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
    m = np.eye(4)
    m[:3, :3] = r * s
    m[:3, 3] = t
    return m


def _world_matrices(gltf: Dict[str, Any]) -> Dict[int, np.ndarray]:
    nodes = gltf.get("nodes", [])
    scene_index = gltf.get("scene", 0)
    scenes = gltf.get("scenes", [])
    roots = scenes[scene_index].get("nodes", []) if scenes else list(range(len(nodes)))
    world: Dict[int, np.ndarray] = {}
    stack = [(i, np.eye(4)) for i in roots]
    while stack:
        index, parent = stack.pop()
        if index in world or not 0 <= index < len(nodes):
            continue
        world[index] = parent @ _node_local(nodes[index])
        stack.extend((child, world[index]) for child in nodes[index].get("children", []))
    return world


def _accessor_matrix(gltf: Dict[str, Any], binary: bytes, accessor_index: int) -> Optional[np.ndarray]:
    """First matrix of a MAT4 accessor (a skin's first inverse bind matrix)."""
    try:
        acc = gltf["accessors"][accessor_index]
        view = gltf["bufferViews"][acc["bufferView"]]
        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        values = struct.unpack_from("<16f", binary, start)
    except (KeyError, IndexError, struct.error, TypeError):
        return None
    return np.array(values, dtype=float).reshape(4, 4).T


def measure_glb(data: bytes) -> Dict[str, Any]:
    """Stand-up bounding box of the default scene, in glTF units (metres).

    Uses the POSITION accessor bounds the glTF specification requires. For a
    skinned mesh the node transform is ignored by the spec; the rest pose is the
    first joint's world matrix times its inverse bind matrix.
    """
    gltf, binary = parse_glb(data)
    world = _world_matrices(gltf)
    nodes, meshes = gltf.get("nodes", []), gltf.get("meshes", [])
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    measured = 0
    for index, matrix in world.items():
        node = nodes[index]
        if "mesh" not in node:
            continue
        effective = matrix
        if "skin" in node:
            skin = gltf.get("skins", [])[node["skin"]]
            joints = skin.get("joints", [])
            ibm = _accessor_matrix(gltf, binary, skin["inverseBindMatrices"]) if "inverseBindMatrices" in skin else np.eye(4)
            if joints and joints[0] in world and ibm is not None:
                effective = world[joints[0]] @ ibm
        for primitive in meshes[node["mesh"]].get("primitives", []):
            pos = primitive.get("attributes", {}).get("POSITION")
            if pos is None:
                continue
            acc = gltf["accessors"][pos]
            if "min" not in acc or "max" not in acc:
                raise GLBError("a mesh is missing its POSITION bounds; re-export the file")
            mn, mx = acc["min"], acc["max"]
            corners = np.array([[x, y, z, 1.0] for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])])
            pts = (effective @ corners.T).T[:, :3]
            lo, hi = np.minimum(lo, pts.min(axis=0)), np.maximum(hi, pts.max(axis=0))
            measured += 1
    if not measured:
        raise GLBError("the file contains no mesh geometry")
    size = hi - lo
    skins = gltf.get("skins", [])
    return {
        "height_m": float(size[1]), "width_m": float(size[0]), "depth_m": float(size[2]),
        "min_y_m": float(lo[1]), "primitives": measured,
        "skinned": bool(skins), "joints": sum(len(s.get("joints", [])) for s in skins),
        "animations": [a.get("name") or f"clip_{i}" for i, a in enumerate(gltf.get("animations", []))],
        "generator": str(gltf.get("asset", {}).get("generator", ""))[:120],
    }


def check_canonical_height(measurement: Dict[str, Any], height_in: float) -> None:
    expected = height_in * INCH_M
    actual = measurement["height_m"]
    if expected <= 0 or abs(actual - expected) > HEIGHT_TOLERANCE * expected:
        raise GLBError(
            f"avatar measures {actual:.3f} m tall but its canonical height is {height_in:g} in "
            f"({expected:.3f} m); re-import so it is scaled to its canonical height")
    if abs(measurement["min_y_m"]) > 0.05 * expected:
        raise GLBError(f"avatar's feet are {measurement['min_y_m']:.3f} m off the floor; re-import to stand it on the floor")


# ── storage ────────────────────────────────────────────────────────────────

class AvatarImportStore:
    def __init__(self, data_dir: Path):
        self.root = Path(data_dir) / "avatars" / "imported"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self.heights_path = Path(data_dir) / "avatars" / "canonical_heights.json"
        self._lock = threading.Lock()

    def heights(self) -> Dict[str, Any]:
        if self.heights_path.exists():
            try:
                data = json.loads(self.heights_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("cast"), dict):
                    return data
            except (OSError, json.JSONDecodeError):
                pass
        return json.loads(json.dumps(DEFAULT_HEIGHTS))

    def _read(self) -> List[Dict[str, Any]]:
        if not self.index_path.exists():
            return []
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"imported avatar index is unreadable: {exc}") from None
        if not isinstance(data, list):
            raise RuntimeError("imported avatar index is not a list")
        return data

    def _write(self, entries: List[Dict[str, Any]]) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".index.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(entries, handle, indent=1)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.index_path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return self._read()

    def get(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        return next((e for e in self.list() if e["id"] == avatar_id), None)

    def path_for(self, avatar_id: str) -> Path:
        if not _ID_RE.match(avatar_id):
            raise ValueError("invalid avatar id")
        return self.root / f"{avatar_id}.glb"

    def add(self, data: bytes, *, name: str, height_in: float, owner: str,
            source_format: str, source_name: str, character_id: str = "") -> Dict[str, Any]:
        if len(data) > MAX_GLB_BYTES:
            raise GLBError(f"avatar is larger than {MAX_GLB_BYTES // (1024 * 1024)} MB")
        if not MIN_HEIGHT_IN <= height_in <= MAX_HEIGHT_IN:
            raise GLBError(f"canonical height must be between {MIN_HEIGHT_IN:g} and {MAX_HEIGHT_IN:g} inches")
        measurement = measure_glb(data)
        check_canonical_height(measurement, height_in)
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "avatar"
        avatar_id = f"{slug}-{uuid.uuid4().hex[:8]}"
        final = self.path_for(avatar_id)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".upload.", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, final)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        entry = {
            "id": avatar_id, "name": name[:80], "character_id": character_id[:64],
            "canonical_height_in": round(float(height_in), 2),
            "canonical_height_m": round(height_in * INCH_M, 4),
            "measured": measurement, "bytes": len(data),
            "source_format": source_format[:12], "source_name": source_name[:200],
            "owner": owner, "imported_at": time.time(),
            "url": f"/api/avatars/imports/{avatar_id}/model.glb",
        }
        with self._lock:
            entries = self._read()
            entries.append(entry)
            try:
                self._write(entries)
            except BaseException:
                final.unlink(missing_ok=True)
                raise
        return entry

    def remove(self, avatar_id: str) -> bool:
        with self._lock:
            entries = self._read()
            kept = [e for e in entries if e["id"] != avatar_id]
            if len(kept) == len(entries):
                return False
            self._write(kept)
        self.path_for(avatar_id).unlink(missing_ok=True)
        return True

    def manifest_pack(self) -> Dict[str, Any]:
        return {
            "pack_id": "imported", "name": "Imported Avatars",
            "description": "Avatars imported from GLB, glTF, OBJ or FBX, each scaled to its canonical height.",
            "refreshed_at": time.time(),
            "assets": [{
                "id": e["id"], "character_id": e.get("character_id") or e["id"], "name": e["name"],
                "display_name": e["name"], "type": "glb", "asset_type": "glb", "url": e["url"],
                "performer_asset": True, "imported": True,
                "canonical_height_m": e["canonical_height_m"], "canonical_height_in": e["canonical_height_in"],
                "skeleton_version": "skinned" if e["measured"]["skinned"] else "static-mesh",
                "animations": e["measured"]["animations"], "status": "present",
            } for e in self.list()],
        }


# ── routes ─────────────────────────────────────────────────────────────────

def _owner(identity: Dict[str, Any]) -> str:
    return str(identity.get("user_id") or identity.get("sub") or "local")


def create_avatar_import_router(data_dir: Path) -> APIRouter:
    store = AvatarImportStore(data_dir)
    router = APIRouter(prefix="/api/avatars", tags=["avatar-import"])
    router.store = store  # type: ignore[attr-defined]

    @router.get("/canonical-heights")
    async def canonical_heights():
        return store.heights()

    @router.get("/imports")
    async def list_imports():
        return {"ok": True, "avatars": store.list()}

    @router.post("/imports", status_code=201)
    async def import_avatar(request: Request, identity: Dict[str, Any] = Depends(current_identity)):
        q = request.query_params
        name = (q.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "name is required")
        try:
            height_in = float(q.get("height_in", ""))
        except ValueError:
            raise HTTPException(400, "height_in (canonical height in inches) is required") from None
        if request.headers.get("content-type", "").split(";")[0].strip() not in ("model/gltf-binary", "application/octet-stream"):
            raise HTTPException(415, "send the avatar as model/gltf-binary")
        data = await request.body()
        try:
            entry = store.add(data, name=name, height_in=height_in, owner=_owner(identity),
                              source_format=q.get("source_format", "glb"), source_name=q.get("source_name", ""),
                              character_id=q.get("character_id", ""))
        except GLBError as exc:
            raise HTTPException(422, str(exc)) from None
        return {"ok": True, "avatar": entry}

    @router.get("/imports/{avatar_id}/model.glb")
    async def avatar_file(avatar_id: str):
        try:
            path = store.path_for(avatar_id)
        except ValueError:
            raise HTTPException(400, "invalid avatar id") from None
        if store.get(avatar_id) is None or not path.is_file():
            raise HTTPException(404, "avatar not found")
        return FileResponse(path, media_type="model/gltf-binary")

    @router.delete("/imports/{avatar_id}")
    async def delete_import(avatar_id: str, identity: Dict[str, Any] = Depends(current_identity)):
        entry = store.get(avatar_id) if _ID_RE.match(avatar_id) else None
        if entry is None:
            raise HTTPException(404, "avatar not found")
        from .auth import role_gte
        if entry["owner"] != _owner(identity) and not role_gte(identity.get("role", "guest"), "mod"):
            raise HTTPException(403, "only the importer or a moderator can delete this avatar")
        store.remove(avatar_id)
        return {"ok": True}

    return router


__all__ = [
    "AvatarImportStore", "GLBError", "create_avatar_import_router", "measure_glb", "parse_glb",
    "check_canonical_height", "DEFAULT_HEIGHTS", "INCH_M",
]
