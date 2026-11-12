"""Consent-bound, session-scoped allocation of actual camera preview rendering.

CameraManager remains camera authority. This allocator neither executes arbitrary
code nor claims that preview JPEGs are a broadcast/recording master.
"""
from __future__ import annotations

import math
import asyncio
import json
import time
import uuid
from collections import deque
from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .auth import role_gte
from .cameras import CameraManager, CameraSwitchEvent, CameraTransport
from .route_security import current_identity

PACKAGES = {"news", "late_night", "debate", "political_discussion", "audience", "game", "variety", "general"}
HEARTBEAT_TTL = 12.0
SCENE_TTL = 6.0
DIRECTOR_TTL = 60.0
MAX_JSON_BYTES = 32_768


class PoolJSONRoute(APIRoute):
    """Bound streamed control JSON before FastAPI parses it into objects."""
    def get_route_handler(self):
        original = super().get_route_handler()

        async def bounded(request: Request):
            if request.method not in {"POST", "PUT"}:
                return await original(request)
            try:
                size = int(request.headers.get("content-length", "0"))
            except ValueError:
                raise HTTPException(400, "Invalid Content-Length") from None
            if size < 0 or size > MAX_JSON_BYTES:
                raise HTTPException(413, "Camera pool control data exceeds 32 KiB")

            async def read():
                data = bytearray()
                async for chunk in request.stream():
                    if len(chunk) > MAX_JSON_BYTES - len(data):
                        raise HTTPException(413, "Camera pool control data exceeds 32 KiB")
                    data.extend(chunk)
                return bytes(data)
            try:
                body = await asyncio.wait_for(read(), timeout=5)
            except asyncio.TimeoutError:
                raise HTTPException(408, "Camera pool request body timed out") from None
            if body:
                def no_constant(value):
                    raise ValueError("Non-finite JSON values are not supported")
                try:
                    value = json.loads(body, parse_constant=no_constant)
                    if value is not None and not isinstance(value, dict):
                        raise ValueError("Control data must be an object")
                    pending = [(value, 0)]
                    visited = 0
                    while pending:
                        item, depth = pending.pop()
                        visited += 1
                        if depth > 8 or visited > 2048:
                            raise ValueError("Control data is too deeply nested or complex")
                        if isinstance(item, dict):
                            pending.extend((v, depth + 1) for v in item.values())
                        elif isinstance(item, list):
                            pending.extend((v, depth + 1) for v in item)
                except (ValueError, RecursionError):
                    raise HTTPException(400, "Expected finite, bounded JSON control data") from None
            sent = False

            async def receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await request.receive()
            return await original(Request(request.scope, receive))
        return bounded


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    max_cameras: int = Field(default=1, ge=1, le=4)
    max_fps: int = Field(default=3, ge=1, le=4)
    max_upload_kbps: int = Field(default=2000, ge=256, le=10000)
    render_ms_per_sec: int = Field(default=200, ge=10, le=600)
    allow_quality_reduction: bool = False


class PerformanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    state: Literal["calibrating", "running", "reduced", "paused"]
    baseline_p95_ms: float | None = Field(default=None, ge=0, le=100000)
    frame_p95_ms: float | None = Field(default=None, ge=0, le=100000)
    work_scale: float = Field(ge=0, le=1)
    preview_width: int = Field(ge=320, le=640)
    reason: str = Field(max_length=160)


class Join(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    consent: Literal[True]
    label: str = Field(min_length=1, max_length=48)
    limits: Limits = Field(default_factory=Limits)

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Explicit consent must be true")
        return value


class Assignment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    participant_id: str
    source_id: str
    fps: int = Field(default=2, ge=1, le=4)
    task: Literal["camera_preview"] = "camera_preview"


class Performer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=96)
    slot: str = Field(max_length=32)
    avatar: Literal["female", "male"]
    position: list[float] = Field(min_length=2, max_length=2)
    vx: float = 0.0
    vy: float = 0.0
    moving: bool = False


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    package: str = Field(max_length=32)
    performers: list[Performer] = Field(max_length=8)
    lowerThird: bool = False
    lowerText: str = Field(default="", max_length=160)
    scores: list[int] = Field(default_factory=lambda: [0, 0], min_length=2, max_length=2)
    blackout: bool = False


async def signed_in(identity=Depends(current_identity)):
    if not identity.get("authenticated"):
        raise HTTPException(403, "Sign in to participate in a camera pool")
    return identity


class CameraPool:
    def __init__(self, cameras: CameraManager, *, clock: Callable[[], float] = time.monotonic):
        self.cameras, self.clock = cameras, clock
        self.sessions: dict[str, dict] = {}
        self.before_assign = lambda source, owner: None
        self.invalidate = lambda source: None
        self._subscription = None
        self.start()

    def start(self):
        if self._subscription is None:
            self._subscription = self.cameras.subscribe(self._camera_event)

    def _camera_event(self, event):
        if isinstance(event, CameraSwitchEvent) and event.destination == "program":
            for session in self.sessions.values():
                if session["assignments"].pop(event.source_id, None) is not None:
                    self.invalidate(event.source_id)
                    session["notice"] = "Program camera returned to the source device: " + event.source_id

    def close_session(self, sid):
        session = self.sessions.pop(sid, None)
        if session:
            for source in list(session["assignments"]):
                self.invalidate(source)

    def close(self):
        if self._subscription is not None:
            self.cameras.unsubscribe(self._subscription)
            self._subscription = None
        for sid in list(self.sessions):
            self.close_session(sid)

    def maintain(self):
        now = self.clock()
        for sid, session in list(self.sessions.items()):
            self.expire(session)
            if now - session["director_seen"] > DIRECTOR_TTL:
                self.close_session(sid)

    def create(self, identity, package):
        self.maintain()
        if not role_gte(identity.get("role", "guest"), "mod"):
            raise HTTPException(403, "Studio operator required to create a pool")
        if not isinstance(package, str) or package not in PACKAGES:
            raise HTTPException(422, "Unsupported studio package")
        if len(self.sessions) >= 8:
            raise HTTPException(409, "Close an existing pool before creating another")
        sid = "pool_" + uuid.uuid4().hex
        self.sessions[sid] = dict(id=sid, owner=identity["user_id"], package=package,
                                 members={}, assignments={}, scene=None, scene_at=0, sequence=0,
                                 director_seen=self.clock(), notice="")
        return sid

    def get(self, sid):
        self.maintain()
        s = self.sessions.get(sid)
        if s is None:
            raise HTTPException(404, "Camera pool not found")
        self.expire(s)
        return s

    def host(self, sid, identity):
        s = self.get(sid)
        if s["owner"] != identity["user_id"]:
            raise HTTPException(403, "Only this pool's director may assign work")
        return s

    def expire(self, s):
        now = self.clock()
        for source in list(s["assignments"]):
            camera = self.cameras.get(source)
            if camera is None or camera.location != "studio25d" or camera.transport != CameraTransport.VIRTUAL or "studio25d" not in camera.tags:
                s["assignments"].pop(source)
                self.invalidate(source)
                s["notice"] = "Camera source was removed or changed; assignment released: " + source
        if s["assignments"] and (s["scene"] is None or now - s["scene_at"] > SCENE_TTL):
            for source in list(s["assignments"]):
                s["assignments"].pop(source)
                self.invalidate(source)
            s["notice"] = "Director scene expired; camera reservations released. Reassign after reconnecting."
        for member in s["members"].values():
            if member["active"] and now - member["seen"] > HEARTBEAT_TTL:
                member["active"] = False
                self.drop_member_tasks(s, member["id"])

    def drop_member_tasks(self, s, pid):
        for source, task in list(s["assignments"].items()):
            if task["participant_id"] == pid:
                del s["assignments"][source]
                self.invalidate(source)

    def member(self, sid, pid, actor):
        s = self.get(sid)
        m = s["members"].get(pid)
        if not m or m["actor"] != actor:
            raise HTTPException(403, "This participant belongs to another person")
        if not m["active"]:
            raise HTTPException(410, "Participation ended; explicit consent is required to rejoin")
        return s, m

    def join(self, sid, identity, body: Join):
        s = self.get(sid)
        if len(s["members"]) >= 32:
            inactive = [m for m in s["members"].values() if not m["active"]]
            if inactive:
                s["members"].pop(min(inactive, key=lambda m: m["seen"])["id"])
        if len(s["members"]) >= 32:
            raise HTTPException(409, "Participant limit reached; create a new pool")
        pid = "participant_" + uuid.uuid4().hex
        s["members"][pid] = dict(id=pid, actor=identity["user_id"], label=body.label,
                                  limits=body.limits.model_dump(), seen=self.clock(), active=True,
                                  upload=deque(maxlen=1000), download=deque(maxlen=1000),
                                  deliveries=deque(maxlen=1000),
                                  last_frames={},
                                  frames=0, bytes=0, render_ms=0.0, errors=0)
        return pid

    def assign(self, sid, identity, body: Assignment):
        s = self.host(sid, identity)
        m = s["members"].get(body.participant_id)
        if not m or not m["active"]:
            raise HTTPException(409, "Participant has not consented or is offline")
        c = self.cameras.get(body.source_id)
        prefix = "p25d_" + s["package"] + "_"
        if not c or not c.source_id.startswith(prefix) or "studio25d" not in c.tags or c.location != "studio25d" or c.transport != CameraTransport.VIRTUAL:
            raise HTTPException(422, "Assign a registered camera from this studio package")
        program = self.cameras.get_program_source()
        if program and program.source_id == body.source_id:
            raise HTTPException(409, "Program rendering stays on the source device; choose a preview camera")
        if s["scene"] is None or self.clock() - s["scene_at"] > SCENE_TTL:
            raise HTTPException(409, "A fresh director scene is required before assigning work")
        occupied = [t for src, t in s["assignments"].items()
                    if src != body.source_id and t["participant_id"] == m["id"]]
        if len(occupied) >= m["limits"]["max_cameras"] or body.fps > m["limits"]["max_fps"]:
            raise HTTPException(409, "Assignment exceeds the participant's consent limits")
        for other in self.sessions.values():
            self.expire(other)
            if other is not s and body.source_id in other["assignments"]:
                raise HTTPException(409, "Camera is assigned in another pool")
        self.before_assign(body.source_id, s["owner"])
        task = {**body.model_dump(), "grant": uuid.uuid4().hex, "assignment_id": uuid.uuid4().hex}
        s["assignments"][body.source_id] = task
        self.invalidate(body.source_id)
        return task

    def reservation(self, source):
        self.maintain()
        for s in self.sessions.values():
            self.expire(s)
            if source in s["assignments"]:
                return s
        return None

    def authorize(self, sid, pid, actor, source, grant, scene_version=None):
        s, m = self.member(sid, pid, actor)
        task = s["assignments"].get(source)
        if not task or task["participant_id"] != pid or task["grant"] != grant:
            raise HTTPException(409, "Camera assignment was revoked or reassigned")
        if s["scene"] is None or self.clock() - s["scene_at"] > SCENE_TTL:
            raise HTTPException(409, "Director scene is stale; rendering is paused")
        program = self.cameras.get_program_source()
        if program and source == program.source_id:
            raise HTTPException(409, "Program rendering stays on the source device")
        if scene_version is not None and scene_version != s["sequence"]:
            raise HTTPException(409, "Scene changed; discard this frame and refresh")
        return s, m, task

    def accept(self, sid, pid, actor, source, grant, count, render_ms, width, height, scene_version):
        s, m, task = self.authorize(sid, pid, actor, source, grant, scene_version)
        now = self.clock()
        if now - m["last_frames"].get(source, -math.inf) < 1 / task["fps"]:
            raise HTTPException(429, "Assigned frame rate exceeded")
        recent_frames = [(at, n, src) for at, n, src in m["upload"] if now - at < 1]
        if len(recent_frames) >= m["limits"]["max_cameras"] * m["limits"]["max_fps"]:
            raise HTTPException(429, "Participant frame rate reached its consent limit")
        recent = sum(n for _, n, _ in recent_frames)
        if recent + count > m["limits"]["max_upload_kbps"] * 1000 / 8:
            raise HTTPException(429, "Participant upload limit reached")
        task["last_frame"] = now
        m["last_frames"] = {src: at for src, at in m["last_frames"].items() if now - at < 1}
        m["last_frames"][source] = now
        task["frames"] = task.get("frames", 0) + 1
        task["dimensions"] = [width, height]
        m["upload"].append((now, count, source))
        m["frames"] += 1
        m["bytes"] += count
        # Client-reported render wall time, never presented as machine CPU/GPU %.
        m["render_ms"] = render_ms

    def delivered(self, source, size, recipient):
        s = self.reservation(source)
        if s:
            task = s["assignments"][source]
            s["members"][task["participant_id"]]["download"].append((self.clock(), size, source))
            s["members"][task["participant_id"]]["deliveries"].append((self.clock(), size, source, recipient))

    def state(self, sid, identity):
        s = self.get(sid)
        if identity["user_id"] != s["owner"] and not any(
            m["actor"] == identity["user_id"] and m["active"] for m in s["members"].values()
        ):
            raise HTTPException(403, "Join this pool to see its session data")
        now = self.clock()
        def rate(events):
            return round(sum(n for at, n, _ in events if now - at < 5) * 8 / 5000, 2)
        members = [{k: m[k] for k in ("id", "label", "active", "limits", "frames", "bytes", "render_ms")}
                   | {"upload_kbps": rate(m["upload"]), "relay_out_kbps": rate(m["download"]), "performance": m.get("performance"),
                      "actual_fps": round(sum(1 for at, _, _ in m["upload"] if now - at < 5) / 5, 2),
                      "age_ms": round((now - m["seen"]) * 1000)} for m in s["members"].values()]
        tasks = []
        for source, task in s["assignments"].items():
            member = s["members"][task["participant_id"]]
            visible = {k: task[k] for k in ("participant_id", "source_id", "fps", "task", "assignment_id")}
            if member["actor"] == identity["user_id"]:
                visible["grant"] = task["grant"]
            visible["age_ms"] = None if "last_frame" not in task else round((now - task["last_frame"]) * 1000)
            visible["upload_kbps"] = rate([e for e in member["upload"] if e[2] == source])
            visible["frames"] = task.get("frames", 0)
            visible["actual_fps"] = round(sum(1 for at, _, src in member["upload"] if now - at < 5 and src == source) / 5, 2)
            visible["dimensions"] = task.get("dimensions")
            tasks.append(visible)
        flows = []
        for member in s["members"].values():
            destinations = {(source, recipient) for at, _, source, recipient in member["deliveries"] if now - at < 5}
            for source, recipient in sorted(destinations):
                amount = sum(n for at, n, src, dst in member["deliveries"] if now - at < 5 and (src, dst) == (source, recipient))
                flows.append({"from": member["label"], "via": "PubCast relay", "to": str(recipient),
                              "source_id": source, "kbps": round(amount * 8 / 5000, 2)})
        return dict(id=sid, package=s["package"], is_director=s["owner"] == identity["user_id"],
                    members=members, assignments=tasks, scene=s["scene"], sequence=s["sequence"],
                    scene_fresh=s["scene"] is not None and now - s["scene_at"] <= SCENE_TTL,
                    scene_age_ms=round((now-s["scene_at"])*1000) if s["scene"] is not None else None,
                    transport="640x360 JPEG camera previews", rate_window_seconds=5,
                    flow="Participant → PubCast relay → session monitors", flows=flows,
                    program=getattr(self.cameras.get_program_source(), "source_id", None), notice=s["notice"])


def create_camera_pool_router(pool: CameraPool):
    r = APIRouter(prefix="/api/camera-pool", tags=["Session Camera Pool"], route_class=PoolJSONRoute)

    @r.post("/sessions")
    async def create(body: dict, identity=Depends(signed_in)):
        return {"id": pool.create(identity, body.get("package"))}

    @r.get("/sessions")
    async def owned(identity=Depends(signed_in)):
        pool.maintain()
        return {"sessions": [{"id": s["id"], "package": s["package"]} for s in pool.sessions.values()
                             if s["owner"] == identity["user_id"] or any(m["active"] and m["actor"] == identity["user_id"] for m in s["members"].values())]}

    @r.get("/sessions/{sid}")
    async def state(sid: str, identity=Depends(signed_in)):
        return pool.state(sid, identity)

    @r.post("/sessions/{sid}/join")
    async def join(sid: str, body: Join, identity=Depends(signed_in)):
        return {"participant_id": pool.join(sid, identity, body)}

    @r.post("/sessions/{sid}/participants/{pid}/heartbeat")
    async def heartbeat(sid: str, pid: str, body: PerformanceReport | None = None, identity=Depends(signed_in)):
        _, m = pool.member(sid, pid, identity["user_id"])
        m["seen"] = pool.clock()
        if body:
            m["performance"] = body.model_dump()
        return {"ok": True}

    @r.put("/sessions/{sid}/participants/{pid}/limits")
    async def limits(sid: str, pid: str, body: Limits, identity=Depends(signed_in)):
        s, m = pool.member(sid, pid, identity["user_id"])
        # Lowering consent stops current work before a director can assign anew.
        pool.drop_member_tasks(s, pid)
        m["limits"] = body.model_dump()
        return {"ok": True}

    @r.delete("/sessions/{sid}/participants/{pid}")
    async def leave(sid: str, pid: str, identity=Depends(signed_in)):
        s, m = pool.member(sid, pid, identity["user_id"])
        m["active"] = False
        pool.drop_member_tasks(s, pid)
        return {"ok": True}

    @r.post("/sessions/{sid}/assignments")
    async def assign(sid: str, body: Assignment, identity=Depends(signed_in)):
        pool.assign(sid, identity, body)
        return {"ok": True}

    @r.delete("/sessions/{sid}/assignments/{source}")
    async def unassign(sid: str, source: str, assignment_id: str | None = None, identity=Depends(signed_in)):
        s = pool.host(sid, identity)
        if source not in s["assignments"]:
            raise HTTPException(404, "Camera is not assigned in this pool")
        if assignment_id is not None and assignment_id != s["assignments"][source]["assignment_id"]:
            raise HTTPException(409, "Assignment changed; refresh before releasing it")
        s["assignments"].pop(source)
        pool.invalidate(source)
        return {"ok": True}

    @r.put("/sessions/{sid}/scene")
    async def scene(sid: str, body: Scene, identity=Depends(signed_in)):
        s = pool.host(sid, identity)
        if body.package != s["package"] or any(not 0 <= v <= 1 for p in body.performers for v in p.position):
            raise HTTPException(422, "Scene must match this package and stage bounds")
        if len({p.id for p in body.performers}) != len(body.performers):
            raise HTTPException(422, "Performer IDs must be unique")
        value = body.model_dump()
        if value != s["scene"]:
            s["sequence"] += 1
            for source in s["assignments"]:
                pool.invalidate(source)
        s.update(scene=value, scene_at=pool.clock(), director_seen=pool.clock())
        return {"ok": True, "sequence": s["sequence"]}

    @r.delete("/sessions/{sid}")
    async def close(sid: str, identity=Depends(signed_in)):
        s = pool.host(sid, identity)
        pool.close_session(sid)
        return {"ok": True}

    return r
