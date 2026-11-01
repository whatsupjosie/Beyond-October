"""Key assignments, kept on the host per signed-in person (static/keymap.js decides what they mean).

    GET /api/keymap   -> {"ok": true, "revision": n, "keymap": {station: {action: KeyCode | null}} | null}
    PUT /api/keymap   <- {"keymap": {...}, "expected_revision": n (optional)}

A key is a KeyboardEvent.code (the physical key). null means the person cleared it on purpose, so the default does not come
back. The same limits the browser applies are applied here, so a hand-made request cannot store Esc, a browser key, a
modifier, or two actions on one key at a station.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from .route_security import current_identity
from .studio_progress import RevisionConflict, StudioProgressStore, _owner

MAX_BYTES = 64 * 1024
RESERVED = frozenset({"Escape", "F5", "F11", "F12", "Tab"})      # same list as RESERVED in static/keymap.js (Up and Down are kept per station by the browser, which knows which have faders)
_MODIFIER = re.compile(r"^(Shift|Control|Alt|Meta|OS)(Left|Right)?$|^(CapsLock|NumLock|ScrollLock|ContextMenu|Fn)$")
_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,23}$")
_ID = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def validate(keymap: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(keymap, dict) or len(keymap) > 32:
        raise ValueError("keymap must be an object of at most 32 stations")
    out: Dict[str, Dict[str, Any]] = {}
    for station, actions in keymap.items():
        if not isinstance(station, str) or not _ID.match(station):
            raise ValueError("a station id must be lower-case letters, digits and underscores")
        if not isinstance(actions, dict) or len(actions) > 64:
            raise ValueError(f"{station}: actions must be an object of at most 64 entries")
        seen: Dict[str, str] = {}
        clean: Dict[str, Any] = {}
        for action, code in actions.items():
            if not isinstance(action, str) or not _ID.match(action):
                raise ValueError(f"{station}: an action id must be lower-case letters, digits and underscores")
            if code is not None:
                if not isinstance(code, str) or not _CODE.match(code):
                    raise ValueError(f"{station}.{action}: not a key code")
                if code in RESERVED or _MODIFIER.match(code):
                    raise ValueError(f"{station}.{action}: {code} cannot be assigned")
                if code in seen:
                    raise ValueError(f"{station}: {code} is used by both {seen[code]} and {action}")
                seen[code] = action
            clean[action] = code
        out[station] = clean
    return out


def create_keymap_router(data_dir: Path) -> APIRouter:
    store = StudioProgressStore(data_dir, folder="keymaps")
    router = APIRouter(prefix="/api/keymap", tags=["keymap"])
    router.store = store  # type: ignore[attr-defined]

    @router.get("")
    async def read_keymap(identity: Dict[str, Any] = Depends(current_identity)):
        record = store.get(_owner(identity))
        if not record:
            return {"ok": True, "revision": 0, "keymap": None}
        return {"ok": True, "revision": record.get("revision", 0), "keymap": record.get("progress")}

    @router.put("")
    async def write_keymap(request: Request, identity: Dict[str, Any] = Depends(current_identity)):
        raw = await request.body()
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "keymap is too large")
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            raise HTTPException(400, "keymap must be JSON") from None
        if not isinstance(body, dict):
            raise HTTPException(400, "body must be an object")
        expected = body.get("expected_revision")
        if expected is not None and (not isinstance(expected, int) or isinstance(expected, bool) or expected < 0):
            raise HTTPException(400, "expected_revision must be a whole number")
        try:
            keymap = validate(body.get("keymap"))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        try:
            record = store.put(_owner(identity), keymap, expected)
        except RevisionConflict as exc:
            raise HTTPException(409, {"message": str(exc), "revision": exc.revision}) from None
        return {"ok": True, "revision": record["revision"]}

    return router


__all__ = ["create_keymap_router", "validate", "RESERVED"]
