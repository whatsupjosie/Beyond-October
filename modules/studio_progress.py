"""Bella Faux Pas Studio progress: where each person is in the walkable world, kept on the Reach host.

One record per signed-in owner, so it survives a browser wipe, a restart and a change of device:

    room, view, pos          the picture you were in and the floor spot you stood on (source-picture pixels)
    char                     who you walk as (pete, repeat = RePete, sir_purfluous)
    avatars                  {character: avatar_id} from the avatar library (modules/avatar_imports.py)
    hologram                 the glowing look on or off
    tune, cans               your size tuning and reference cans, per picture (the same shape the walker keeps)

The walker (static/world_walk.html) reads it on start and writes it as you move. Writes are validated, bounded in
size, revisioned, and replaced atomically (temp file then os.replace), so a crash never leaves half a file.
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from .route_security import current_identity

MAX_BYTES = 256 * 1024                       # tune and cans for every picture fit comfortably in far less
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_OWNER_SAFE = re.compile(r"[^A-Za-z0-9_.@-]")
CHARACTERS = ("pete", "repeat", "sir_purfluous")   # the ids world.json and the walker use (repeat = RePete)


def _owner(identity: Dict[str, Any]) -> str:
    return str(identity.get("user_id") or identity.get("sub") or "local").strip() or "local"


def _finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate(body: Any) -> Dict[str, Any]:
    """Return the cleaned progress record, or raise ValueError saying what is wrong."""
    if not isinstance(body, dict):
        raise ValueError("progress must be an object")
    out: Dict[str, Any] = {}
    for key in ("room", "view"):
        v = body.get(key)
        if v is not None:
            if not isinstance(v, str) or not _ID.match(v):
                raise ValueError(f"{key} must be a short id")
            out[key] = v
    pos = body.get("pos")
    if pos is not None:
        if not (isinstance(pos, list) and len(pos) == 2 and all(_finite(p) and -1e5 < p < 1e5 for p in pos)):
            raise ValueError("pos must be two finite numbers")
        out["pos"] = [round(float(pos[0]), 2), round(float(pos[1]), 2)]
    char = body.get("char")
    if char is not None:
        if char not in CHARACTERS:
            raise ValueError(f"char must be one of {', '.join(CHARACTERS)}")
        out["char"] = char
    avatars = body.get("avatars")
    if avatars is not None:
        if not isinstance(avatars, dict) or any(k not in CHARACTERS or not (v is None or (isinstance(v, str) and _ID.match(v)))
                                                for k, v in avatars.items()):
            raise ValueError("avatars maps a character to an avatar id from the library")
        out["avatars"] = {k: v for k, v in avatars.items() if v}
    if "hologram" in body:
        if not isinstance(body["hologram"], bool):
            raise ValueError("hologram must be true or false")
        out["hologram"] = body["hologram"]
    for key in ("tune", "cans"):
        v = body.get(key)
        if v is not None:
            if not isinstance(v, dict) or not all(isinstance(k, str) and len(k) <= 120 for k in v):
                raise ValueError(f"{key} must be an object keyed by picture")
            out[key] = v
    if len(json.dumps(out)) > MAX_BYTES:
        raise ValueError("progress is too large")
    return out


class StudioProgressStore:
    """One JSON record per owner in data_dir/<folder>/, revisioned and replaced atomically. Also used for the Counter
    layout (modules/counter_layout.py)."""
    def __init__(self, data_dir: Path, folder: str = "studio_progress"):
        self.root = Path(data_dir) / folder
        self._lock = threading.Lock()

    def path_for(self, owner: str) -> Path:
        safe = _OWNER_SAFE.sub("_", owner)[:120] or "local"
        return self.root / f"{safe}.json"

    def get(self, owner: str) -> Optional[Dict[str, Any]]:
        p = self.path_for(owner)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return None                      # unreadable: treat as no progress rather than break the studio
        return data if isinstance(data, dict) else None

    def put(self, owner: str, progress: Dict[str, Any], expected_revision: Optional[int] = None,
            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            current = self.get(owner) or {}
            revision = int(current.get("revision") or 0)
            if expected_revision is not None and expected_revision != revision:
                raise RevisionConflict(revision)
            record = {"owner": owner, "revision": revision + 1, "saved_at": time.time(), "progress": progress}
            if extra:
                record.update({k: v for k, v in extra.items() if k not in record})
            self.root.mkdir(parents=True, exist_ok=True)
            p = self.path_for(owner)
            tmp = p.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, p)
            return record


class RevisionConflict(Exception):
    def __init__(self, revision: int):
        super().__init__(f"progress changed elsewhere (now revision {revision})")
        self.revision = revision


def create_studio_progress_router(data_dir: Path) -> APIRouter:
    store = StudioProgressStore(data_dir)
    router = APIRouter(prefix="/api/studio/progress", tags=["bella-faux-pas"])
    router.store = store  # type: ignore[attr-defined]

    @router.get("")
    async def read_progress(identity: Dict[str, Any] = Depends(current_identity)):
        record = store.get(_owner(identity))
        if not record:
            return {"ok": True, "revision": 0, "progress": None}
        return {"ok": True, "revision": record.get("revision", 0), "saved_at": record.get("saved_at"), "progress": record.get("progress")}

    @router.put("")
    async def write_progress(request: Request, identity: Dict[str, Any] = Depends(current_identity)):
        raw = await request.body()
        if len(raw) > MAX_BYTES + 1024:
            raise HTTPException(413, "progress is too large")
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            raise HTTPException(400, "progress must be JSON") from None
        expected = body.get("expected_revision") if isinstance(body, dict) else None
        if expected is not None and (not isinstance(expected, int) or isinstance(expected, bool) or expected < 0):
            raise HTTPException(400, "expected_revision must be a whole number")
        try:
            progress = validate(body.get("progress") if isinstance(body, dict) else None)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        try:
            record = store.put(_owner(identity), progress, expected)
        except RevisionConflict as exc:
            raise HTTPException(409, {"message": str(exc), "revision": exc.revision}) from None
        return {"ok": True, "revision": record["revision"], "saved_at": record["saved_at"]}

    return router


__all__ = ["create_studio_progress_router", "StudioProgressStore", "validate", "RevisionConflict", "CHARACTERS"]
