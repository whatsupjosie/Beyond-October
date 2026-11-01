"""Saved camera moves, kept on the host per signed-in person (static/camera_rig.js records and replays them).

    data/camera_moves/<person>/<name>.json     one recorded move

    GET    /api/camera-moves            -> {"moves": [{name, camera, seconds, saved_at}]}
    PUT    /api/camera-moves/{name}     <- the recording (version 1, see camera_rig.js stopRecording)
    GET    /api/camera-moves/{name}     -> the recording
    DELETE /api/camera-moves/{name}

A move is the pose that resulted, sampled at a fixed rate, so it replays exactly. Everything in it is checked before it is
written: the channel list must be exactly the rig's, every number finite and in range, the length and size capped, so a hand-made
request cannot store anything the rig could not have recorded.
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from .route_security import current_identity
from .studio_progress import _OWNER_SAFE, _owner

CHANNELS = ["x", "y", "z", "pan", "tilt", "roll", "fov", "focus"]          # the order in static/camera_rig.js
RANGE = {"x": 1e4, "y": 1e4, "z": 1e4, "pan": 7.0, "tilt": 1.6, "roll": 1.6, "fov": 3.2, "focus": 1000.0}     # absolute limits; angles in radians
MAX_BYTES = 3_000_000
MAX_SAMPLES = 36_000                                                        # twenty minutes at 30 a second
MAX_MOVES = 200
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,59}$")


def _num(v: Any, limit: float) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and abs(v) <= limit


def validate(rec: Any) -> Dict[str, Any]:
    if not isinstance(rec, dict) or rec.get("version") != 1:
        raise ValueError("a recording must be an object with version 1")
    rate = rec.get("rate")
    if not _num(rate, 240) or rate < 1:
        raise ValueError("rate must be between 1 and 240")
    if rec.get("channels") != CHANNELS:
        raise ValueError("channels must be exactly " + ", ".join(CHANNELS))
    start = rec.get("start")
    if not isinstance(start, dict) or not all(_num(start.get(c), RANGE[c]) for c in CHANNELS):
        raise ValueError("start must hold a number for every channel")
    samples = rec.get("samples")
    if not isinstance(samples, list) or not samples or len(samples) > MAX_SAMPLES:
        raise ValueError(f"samples must be a list of 1 to {MAX_SAMPLES}")
    for row in samples:
        if not (isinstance(row, list) and len(row) == len(CHANNELS) and all(_num(v, RANGE[c]) for v, c in zip(row, CHANNELS))):
            raise ValueError("every sample must hold one finite number per channel")
    camera = rec.get("camera", "")
    if not isinstance(camera, str) or len(camera) > 80:
        raise ValueError("camera must be short text")
    return {"version": 1, "rate": float(rate), "channels": CHANNELS, "start": {c: float(start[c]) for c in CHANNELS},
            "samples": [[float(v) for v in row] for row in samples], "camera": camera}


def _clean_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME.match(name) or name.endswith((".", " ")):
        raise HTTPException(400, "a move name is letters, digits, spaces, dots, dashes and underscores, up to 60 characters")
    return name


def create_camera_moves_router(data_dir: Path) -> APIRouter:
    root = Path(data_dir) / "camera_moves"
    lock = threading.Lock()
    router = APIRouter(prefix="/api/camera-moves", tags=["camera-moves"])

    def folder(identity: Dict[str, Any]) -> Path:
        return root / (_OWNER_SAFE.sub("_", _owner(identity))[:120] or "local")

    def path_for(identity: Dict[str, Any], name: str) -> Path:
        return folder(identity) / (_clean_name(name) + ".json")

    @router.get("")
    async def list_moves(identity: Dict[str, Any] = Depends(current_identity)):
        out = []
        d = folder(identity)
        for p in sorted(d.glob("*.json")) if d.exists() else []:
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
                out.append({"name": p.stem, "camera": rec.get("camera", ""), "seconds": round(len(rec["samples"]) / rec["rate"], 2),
                            "saved_at": p.stat().st_mtime})
            except (OSError, ValueError, KeyError, ZeroDivisionError, TypeError):
                continue                                              # an unreadable file is skipped, not a failure for the rest
        return {"ok": True, "moves": out}

    @router.put("/{name}")
    async def save_move(name: str, request: Request, identity: Dict[str, Any] = Depends(current_identity)):
        p = path_for(identity, name)
        raw = await request.body()
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "that move is too large")
        try:
            rec = validate(json.loads(raw or b"{}"))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        with lock:
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists() and len(list(p.parent.glob("*.json"))) >= MAX_MOVES:
                raise HTTPException(409, f"at most {MAX_MOVES} saved moves")
            tmp = p.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(rec, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, p)
        return {"ok": True, "name": p.stem, "seconds": round(len(rec["samples"]) / rec["rate"], 2), "saved_at": time.time()}

    @router.get("/{name}")
    async def read_move(name: str, identity: Dict[str, Any] = Depends(current_identity)):
        p = path_for(identity, name)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise HTTPException(404, "no such move") from None
        except (OSError, ValueError):
            raise HTTPException(500, "that move could not be read") from None

    @router.delete("/{name}")
    async def delete_move(name: str, identity: Dict[str, Any] = Depends(current_identity)):
        p = path_for(identity, name)
        with lock:
            try:
                p.unlink()
            except FileNotFoundError:
                raise HTTPException(404, "no such move") from None
        return {"ok": True}

    return router


__all__ = ["create_camera_moves_router", "validate", "CHANNELS"]
