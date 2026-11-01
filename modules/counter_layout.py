"""The Foresight Counter layout, kept on the Reach host per owner.

The Counter already keeps its layout in the browser (localStorage ``foresight.counter.v3:<owner>``). That copy is lost
when the browser's site data is cleared or when the owner signs in from another browser or machine. This keeps the same
serialized layout on the host too (``data/counter_layout/<owner>.json``), revisioned and replaced atomically; the
Counter page restores whichever copy is newer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from .route_security import current_identity
from .studio_progress import RevisionConflict, StudioProgressStore, _owner

MAX_BYTES = 2 * 1024 * 1024       # five trays and their program state; file bytes live in the file workspace, not here
MAX_TRAYS = 64


def validate(layout: Any) -> Dict[str, Any]:
    if not isinstance(layout, dict):
        raise ValueError("layout must be an object")
    if layout.get("v") != 3:
        raise ValueError("layout must be a version 3 Counter layout")
    trays = layout.get("trays")
    if not isinstance(trays, list) or len(trays) > MAX_TRAYS or not all(isinstance(t, dict) for t in trays):
        raise ValueError("trays must be a list of trays")
    for t in trays:
        if not isinstance(t.get("contents", []), list):
            raise ValueError("each tray's contents must be a list")
    return layout


def create_counter_layout_router(data_dir: Path) -> APIRouter:
    store = StudioProgressStore(data_dir, folder="counter_layout")
    router = APIRouter(prefix="/api/foresight/counter-layout", tags=["foresight"])
    router.store = store  # type: ignore[attr-defined]

    @router.get("")
    async def read_layout(identity: Dict[str, Any] = Depends(current_identity)):
        record = store.get(_owner(identity))
        if not record:
            return {"ok": True, "revision": 0, "layout": None}
        return {"ok": True, "revision": record.get("revision", 0), "saved_at": record.get("saved_at"),
                "client_saved_at": record.get("client_saved_at"), "layout": record.get("progress")}

    @router.put("")
    async def write_layout(request: Request, identity: Dict[str, Any] = Depends(current_identity)):
        raw = await request.body()
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "layout is too large")
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            raise HTTPException(400, "layout must be JSON") from None
        if not isinstance(body, dict):
            raise HTTPException(400, "body must be an object")
        expected = body.get("expected_revision")
        if expected is not None and (not isinstance(expected, int) or isinstance(expected, bool) or expected < 0):
            raise HTTPException(400, "expected_revision must be a whole number")
        client_at = body.get("client_saved_at")
        if client_at is not None and (not isinstance(client_at, (int, float)) or isinstance(client_at, bool)):
            raise HTTPException(400, "client_saved_at must be a time in milliseconds")
        try:
            layout = validate(body.get("layout"))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        try:
            record = store.put(_owner(identity), layout, expected, extra={"client_saved_at": client_at})
        except RevisionConflict as exc:
            raise HTTPException(409, {"message": str(exc), "revision": exc.revision}) from None
        return {"ok": True, "revision": record["revision"], "saved_at": record["saved_at"]}

    return router


__all__ = ["create_counter_layout_router", "validate"]
