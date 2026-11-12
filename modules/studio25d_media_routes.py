"""Bounded, authenticated 2.5D browser-origin video confidence frames.

The rendering browser is the video producer. The canonical CameraManager remains
the control plane; this small media plane serves *real rendered JPEG frames* to
remote operator monitors. A latest-frame confidence feed is NOT a broadcast-grade
WebRTC/NDI/RTMP ingest or server-side video recording system.

Limits prevent arbitrary upload, accidental huge memory use, and cross-session
takeover. Standard library JPEG SOF parsing avoids adding a heavy image dependency.
"""
from __future__ import annotations

import re
import math
import time
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from .cameras import CameraManager
from .route_security import current_identity
from .auth import role_gte

MAX_BYTES = 240_000
MAX_SOURCES = 16
MAX_WIDTH = 1280
MAX_HEIGHT = 720
LEASE_SECONDS = 5.0
MIN_FRAME_INTERVAL = 0.09
_SOURCE = re.compile(r"p25d_[a-z0-9_]{2,100}\Z")
_SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{7,127}\Z")
_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


@dataclass
class Frame:
    content: bytes
    timestamp: float
    owner: str
    session: str
    sequence: int
    width: int
    height: int
    pool_id: str = ""
    participant_id: str = ""
    grant: str = ""
    scene_version: int = 0
    assignment_id: str = ""


def jpeg_dimensions(payload: bytes) -> tuple[int, int]:
    """Reject truncated/suspicious JPEGs and images larger than the preview budget."""
    if len(payload) < 100 or not payload.startswith(b"\xff\xd8") or not payload.endswith(b"\xff\xd9"):
        raise ValueError("Expected a complete JPEG frame")
    offset = 2
    width = height = None
    while offset + 3 < len(payload):
        if payload[offset] != 0xFF:
            raise ValueError("Invalid JPEG segment marker")
        while offset < len(payload) and payload[offset] == 0xFF:
            offset += 1
        if offset >= len(payload):
            break
        marker = payload[offset]
        offset += 1
        if marker == 0xD9 or marker == 0xDA:
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(payload):
            break
        length = int.from_bytes(payload[offset:offset + 2], "big")
        if length < 2 or offset + length > len(payload):
            raise ValueError("Truncated JPEG segment")
        if marker in _SOF:
            if length < 7:
                raise ValueError("Invalid JPEG frame header")
            height = int.from_bytes(payload[offset + 3:offset + 5], "big")
            width = int.from_bytes(payload[offset + 5:offset + 7], "big")
        offset += length
    if width is None or height is None or not 32 <= width <= MAX_WIDTH or not 32 <= height <= MAX_HEIGHT:
        raise ValueError("Missing or unsupported JPEG dimensions")
    return width, height


async def operator(identity: dict = Depends(current_identity)) -> dict:
    # Unlike compatibility control routes, video frames are *never* anonymous,
    # even when PUBCAST_ENFORCE_AUTH is disabled for a development environment.
    if not identity.get("authenticated") or not role_gte(identity.get("role", "guest"), "mod"):
        raise HTTPException(403, "Authenticated studio operator required")
    return identity


def create_studio25d_media_router(
    cameras: CameraManager, *, clock: Callable[[], float] = time.monotonic, pool=None
) -> APIRouter:
    router = APIRouter(prefix="/api/studio25d/media", tags=["2.5D Live Confidence Media"])
    frames: dict[str, Frame] = {}
    # A released session cannot resurrect a stale frame from an in-flight upload.
    closed_sessions: dict[tuple[str, str], float] = {}

    if pool is not None:
        def before_assign(source, owner):
            prune(clock())
            old = frames.get(source)
            previous_pool = pool.sessions.get(old.pool_id) if old and old.pool_id else None
            if old and old.owner != owner and (not previous_pool or previous_pool["owner"] != owner):
                raise HTTPException(409, "Another producer owns this camera; wait for release")
        pool.before_assign = before_assign
        pool.invalidate = lambda source: frames.pop(source, None)

    def camera_exists(source: str) -> None:
        if not _SOURCE.fullmatch(source):
            raise HTTPException(400, "Invalid studio camera ID")
        camera = cameras.get(source)
        if camera is None or "studio25d" not in camera.tags or camera.location != "studio25d":
            raise HTTPException(404, "Studio camera not registered")

    def prune(now: float) -> None:
        for source, entry in list(frames.items()):
            if now - entry.timestamp > LEASE_SECONDS:
                frames.pop(source, None)
            elif entry.pool_id:
                try:
                    pool.authorize(entry.pool_id, entry.participant_id, entry.owner, source, entry.grant, entry.scene_version)
                except HTTPException:
                    frames.pop(source, None)
        for key, closed_at in list(closed_sessions.items()):
            if now - closed_at > LEASE_SECONDS * 2:
                closed_sessions.pop(key, None)

    def writable_frame(source: str, actor: str, session: str, now: float) -> Frame | None:
        prune(now)
        old = frames.get(source)
        if (actor, session) in closed_sessions:
            raise HTTPException(410, "This studio session was already released")
        if old and (old.owner, old.session) != (actor, session):
            raise HTTPException(409, "Another active studio session owns this camera feed")
        if old and now - old.timestamp < MIN_FRAME_INTERVAL:
            raise HTTPException(429, "Frame rate exceeded", headers={"Retry-After": "0.1"})
        if source not in frames and len(frames) >= MAX_SOURCES:
            raise HTTPException(503, "Studio confidence feed capacity reached")
        return old

    @router.post("/frames/{source_id}")
    async def publish(source_id: str, request: Request, identity: dict = Depends(current_identity)):
        pool_id = request.headers.get("X-Camera-Pool", "")
        participant = request.headers.get("X-Pool-Participant", "")
        grant = request.headers.get("X-Pool-Grant", "")
        scene_version = 0
        if pool_id:
            revision = request.headers.get("X-Pool-Scene-Version", "")
            if not re.fullmatch(r"[1-9][0-9]{0,15}", revision):
                raise HTTPException(400, "Valid pool scene version required")
            scene_version = int(revision)
        def authorize():
            if pool_id:
                if pool is None or not identity.get("authenticated"):
                    raise HTTPException(403, "Authenticated pool participation required")
                pool.authorize(pool_id, participant, str(identity.get("user_id")), source_id, grant, scene_version)
            else:
                if not identity.get("authenticated") or not role_gte(identity.get("role", "guest"), "mod"):
                    raise HTTPException(403, "Authenticated studio operator required")
                if pool is not None and pool.reservation(source_id):
                    raise HTTPException(409, "Camera rendering is assigned to a pool participant")
        authorize()
        camera_exists(source_id)
        session = request.headers.get("X-Studio-Session", "")
        if not _SESSION.fullmatch(session):
            raise HTTPException(400, "Valid studio session ID required")
        if request.headers.get("content-type", "").split(";")[0].lower() != "image/jpeg":
            raise HTTPException(415, "Only image/jpeg frames are supported")
        actor = str(identity.get("user_id"))
        writable_frame(source_id, actor, session, clock())
        if request.headers.get("content-length"):
            try:
                claimed_length = int(request.headers["content-length"])
            except ValueError:
                raise HTTPException(400, "Invalid Content-Length") from None
            if claimed_length < 0 or claimed_length > MAX_BYTES:
                raise HTTPException(413, "Confidence frame is too large")
        data = bytearray()
        async for piece in request.stream():
            if len(piece) > MAX_BYTES - len(data):
                raise HTTPException(413, "Confidence frame is too large")
            data.extend(piece)
        try:
            width, height = jpeg_dimensions(bytes(data))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        # Reading a streamed request yields to other publishers and releases.
        # Revalidate at commit time, without any await before the assignment.
        camera_exists(source_id)
        authorize()  # A participant may withdraw while this request is streaming.
        now = clock()
        old = writable_frame(source_id, actor, session, now)
        if pool_id:
            if width > 640 or height > 360:
                raise HTTPException(422, "Pool tasks accept camera previews up to 640x360")
            try:
                render_ms = float(request.headers.get("X-Render-Ms", "0"))
                if not math.isfinite(render_ms) or not 0 <= render_ms <= 20000:
                    raise ValueError()
            except ValueError:
                raise HTTPException(422, "Invalid render duration") from None
            pool.accept(pool_id, participant, actor, source_id, grant, len(data), render_ms, width, height, scene_version)
        assignment_id = pool.get(pool_id)["assignments"][source_id]["assignment_id"] if pool_id else ""
        sequence = old.sequence + 1 if old else 1
        frames[source_id] = Frame(bytes(data), now, actor, session, sequence, width, height,
                                 pool_id, participant, grant, scene_version, assignment_id)
        result = {"ok": True, "source_id": source_id, "sequence": sequence, "width": width, "height": height}
        if pool_id:
            result.update(pool_id=pool_id, participant_id=participant, assignment_id=assignment_id, scene_version=scene_version)
        return result

    @router.get("/frames/{source_id}")
    async def latest(source_id: str, identity: dict = Depends(current_identity)):
        if not identity.get("authenticated"):
            raise HTTPException(403, "Authenticated studio operator or pool participant required")
        if not role_gte(identity.get("role", "guest"), "mod"):
            reservation = pool.reservation(source_id) if pool is not None else None
            if reservation is None:
                raise HTTPException(403, "This camera is not in your pool")
            pool.state(reservation["id"], identity)
        camera_exists(source_id)
        now = clock()
        prune(now)
        frame = frames.get(source_id)
        if frame and frame.pool_id:
            try:
                pool.authorize(frame.pool_id, frame.participant_id, frame.owner, source_id, frame.grant, frame.scene_version)
            except HTTPException:
                frames.pop(source_id, None)
                frame = None
        if not frame:
            raise HTTPException(503, "No recent real video frame from this source")
        if frame.pool_id:
            pool.delivered(source_id, len(frame.content), identity["user_id"])
        return Response(
            frame.content, media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store, no-cache",
                "X-Studio-Sequence": str(frame.sequence),
                "X-Studio-Frame-Age-Ms": str(round((now - frame.timestamp) * 1000)),
                "X-Studio-Frame-Width": str(frame.width),
                "X-Studio-Frame-Height": str(frame.height),
                "X-Pool-Scene-Version": str(frame.scene_version),
                "X-Pool-Assignment": frame.assignment_id,
            },
        )

    @router.get("/status")
    async def status(identity: dict = Depends(operator)):
        now = clock()
        prune(now)
        return {"ok": True, "media_type": "jpeg_confidence_frames", "transport": "latest_frame_http",
                "fresh_sources": [{"source_id": source, "sequence": frame.sequence,
                                   "width": frame.width, "height": frame.height,
                                   "age_ms": round((now - frame.timestamp) * 1000)}
                                  for source, frame in sorted(frames.items())]}

    @router.delete("/sessions/{session_id}")
    async def release(session_id: str, identity: dict = Depends(operator)):
        if not _SESSION.fullmatch(session_id):
            raise HTTPException(400, "Invalid session ID")
        actor = str(identity.get("user_id"))
        released = [src for src, frame in list(frames.items()) if (frame.owner, frame.session) == (actor, session_id)]
        for src in released:
            frames.pop(src, None)
        prune(clock())
        closed_sessions[(actor, session_id)] = clock()
        # Bound tombstones even if an operator opens many short sessions.
        if len(closed_sessions) > 128:
            oldest = min(closed_sessions, key=closed_sessions.get)
            closed_sessions.pop(oldest, None)
        return {"ok": True, "released": released}

    return router
