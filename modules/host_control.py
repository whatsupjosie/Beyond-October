"""Host control of people in PubCast: possession, timeout, profile, gifts and the tracker log.

The server half of handoffs/HOST_CONTROL_SPEC_2026-10-29.md. Every action goes through ``HostControl`` and the routes
below: the role is checked on the server, the governance engine does the work (its audit log gets an entry), a private
event goes to the target only (``Hub.send_private_event``), and the tracker log notes it. The panel in the walker is a
client of these routes and changes nothing itself.

    data/people/<person>.json                 the profile: title, position, notes, privileges, gifts, discipline, tracked
    data/people_log/<person>/<YYYY-MM-DD>.md  the tracker log, append-only text, written for tracked people
    data/host_control/messages.json           the wording of the private notices (Josie's, not ours: see below)

Wording rule: the possession notice is Josie's own text. It is read from ``messages.json`` at the moment it is used and
is never written by this code. Until she has put it there, possession refuses (409 ``possession_notice_not_set``)
instead of sending words nobody approved.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from .route_security import require_role
from .studio_progress import StudioProgressStore

logger = logging.getLogger("pubcast.host_control")

_ID = re.compile(r"^[A-Za-z0-9_.@-]{1,120}$")
_ROOM = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRIVILEGES = ("control_room",)                       # what can be granted or revoked; extend here and nowhere else
GIFT_KINDS = ("control_room_access", "accessory")
LIMITS = {"title": 80, "position": 80, "notes": 4000, "item": 80, "reason": 512}
DETENTION_ROOM = "waiting_room_disciplinary"         # the disciplinary side of the waiting room (Josie, 2026-10-29)
DEFAULT_POSSESSION_SECONDS = 600
MAX_HOLD_SECONDS = 3600
DEFAULT_TIMEOUT_SECONDS = 300
MAX_LOG_BYTES = 1_000_000                            # per person per day
CONTROL_ROLE = "admin"                               # taking over, teleporting, granting: admin and owner (Josie, "as the owner"); reading: mod
READ_ROLE = "mod"


def _clean_id(value: Any, field: str = "user_id") -> str:
    if not isinstance(value, str) or not _ID.match(value):
        raise HTTPException(400, f"{field} must be a short id")
    return value


def _text(body: Dict[str, Any], key: str) -> Optional[str]:
    if key not in body:
        return None
    v = body[key]
    if not isinstance(v, str):
        raise HTTPException(400, f"{key} must be text")
    v = v.strip()
    if len(v) > LIMITS[key]:
        raise HTTPException(400, f"{key} must be at most {LIMITS[key]} characters")
    return v


def _seconds(body: Dict[str, Any], default: int) -> int:
    v = body.get("duration_seconds", default)
    if v is None:
        return default
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 1 <= v <= MAX_HOLD_SECONDS:
        raise HTTPException(400, f"duration_seconds must be between 1 and {MAX_HOLD_SECONDS}")
    return int(v)


def _k(person: str) -> str:
    """The key a person is kept under. The hub compares user ids case-insensitively, so two spellings are one person."""
    return person.casefold()


def _actor(identity: Dict[str, Any]) -> str:
    return str(identity.get("user_id") or identity.get("sub") or "host")


# ── the tracker log ─────────────────────────────────────────────────────────────

class TrackerLog:
    """Append-only text record per person per day. One line per event, readable as it is."""
    def __init__(self, data_dir: Path):
        self.root = Path(data_dir) / "people_log"
        self._lock = threading.Lock()

    def _path(self, person: str, day: str) -> Path:
        return self.root / re.sub(r"[^A-Za-z0-9_.@-]", "_", person)[:120] / f"{day}.md"

    def add(self, person: str, kind: str, text: str, with_: Optional[List[str]] = None) -> None:
        now = datetime.now(timezone.utc)
        line = f"- {now:%H:%M:%S}Z {kind}: {' '.join(str(text).split())[:1000]}"
        if with_:
            line += " (with " + ", ".join(str(w) for w in with_[:10]) + ")"
        path = self._path(person, f"{now:%Y-%m-%d}")
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            size = path.stat().st_size if path.exists() else 0
            if size >= MAX_LOG_BYTES:
                return                                          # the day is full; the marker below was written once
            with path.open("a", encoding="utf-8") as fh:
                if size == 0:
                    fh.write(f"# {person}, {now:%Y-%m-%d}\n\n")
                fh.write(line + "\n")
                if size + len(line) >= MAX_LOG_BYTES:
                    fh.write("- (log full for today: later events are not kept in this file)\n")

    def read(self, person: str, day: str) -> str:
        try:
            return self._path(person, day).read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""


# ── the dispatcher ──────────────────────────────────────────────────────────────

class HostControl:
    def __init__(self, gov: Any, hub: Any, data_dir: Path, senders: Optional[List[Any]] = None):
        self.gov, self.hub, self.data_dir = gov, hub, Path(data_dir)
        # where a private event can be delivered: the hub's verified chat sockets, plus any extra senders (the walker's own)
        self.senders = [hub.send_private_event] + list(senders or [])
        self.people = StudioProgressStore(self.data_dir, folder="people")
        self.log = TrackerLog(self.data_dir)
        self.messages_path = self.data_dir / "host_control" / "messages.json"
        self.possessed: Dict[str, Dict[str, Any]] = {}
        self.timeouts: Dict[str, Dict[str, Any]] = {}
        self._tasks: Dict[tuple, asyncio.Task] = {}                 # ("p"|"t", person key): a possession and a timeout each keep their own timer

    # -- wording (Josie's, read when used) --
    def notice(self, key: str) -> Optional[str]:
        try:
            v = json.loads(self.messages_path.read_text(encoding="utf-8")).get(key)
        except (OSError, ValueError, AttributeError):
            return None
        return v if isinstance(v, str) and v.strip() else None

    # -- profile --
    def record(self, person: str) -> Dict[str, Any]:
        rec = (self.people.get(_k(person)) or {}).get("progress")
        if isinstance(rec, dict):
            return rec
        return {"id": person, "name": person, "title": "", "position": "", "notes": "", "tracked": False,
                "privileges": {p: False for p in PRIVILEGES}, "gifts": [], "discipline": []}

    def _save(self, person: str, rec: Dict[str, Any], actor: str, action: str, detail: str) -> Dict[str, Any]:
        self._audit(action, actor, person, detail)
        self.people.put(_k(person), rec)
        if rec.get("tracked"):
            self.log.add(person, action.lower(), f"{detail} (by {actor})")
        return rec

    def _audit(self, action: str, actor: str, target: str, detail: str, required: bool = True) -> None:
        """Write the governance audit entry. For anything that acts on a person it is written first and is required:
        if the log cannot be written the action does not happen (503), because an unlogged takeover is worse than none."""
        try:
            self.gov._audit(action, actor, target, detail)
        except Exception:
            logger.exception("audit write failed for %s", action)
            if required:
                raise HTTPException(503, "audit_unavailable") from None

    def edit(self, person: str, actor: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        if "name" in fields:
            raise HTTPException(400, "a name cannot be changed")
        rec = self.record(person)
        changed = []
        for key in ("title", "position", "notes"):
            if key in fields:
                rec[key] = fields[key]; changed.append(key)
        if "tracked" in fields:
            if not isinstance(fields["tracked"], bool):
                raise HTTPException(400, "tracked must be true or false")
            rec["tracked"] = fields["tracked"]; changed.append("tracked")
        if not changed:
            raise HTTPException(400, "nothing to change")
        return self._save(person, rec, actor, "PROFILE_EDIT", "set " + ", ".join(f"{k}={rec[k]!r}" if k != "notes" else k for k in changed))

    def set_privilege(self, person: str, actor: str, name: str, value: bool) -> Dict[str, Any]:
        if name not in PRIVILEGES:
            raise HTTPException(404, "no such privilege")
        rec = self.record(person)
        rec["privileges"] = dict(rec.get("privileges") or {}, **{name: bool(value)})
        return self._save(person, rec, actor, "PRIVILEGE_GRANT" if value else "PRIVILEGE_REVOKE", name)

    def give_gift(self, person: str, actor: str, kind: str, item: str) -> Dict[str, Any]:
        if kind not in GIFT_KINDS:
            raise HTTPException(400, f"kind must be one of {', '.join(GIFT_KINDS)}")
        if kind == "accessory" and not item:
            raise HTTPException(400, "an accessory gift needs an item")
        rec = self.record(person)
        rec["gifts"] = list(rec.get("gifts") or []) + [{"kind": kind, "item": item, "by": actor, "at": time.time()}]
        if kind == "control_room_access":
            rec["privileges"] = dict(rec.get("privileges") or {}, control_room=True)
        return self._save(person, rec, actor, "GIFT", f"{kind} {item}".strip())

    # -- control --
    async def _private(self, person: str, event: Dict[str, Any]) -> int:
        delivered = 0
        for send in self.senders:
            try:
                delivered += int(await send({person}, event))
            except Exception:
                logger.exception("private event to %s failed on one channel", person)
        return delivered

    def _schedule(self, kind: str, key: str, seconds: int, token: float, finish) -> None:
        async def later() -> None:
            await asyncio.sleep(seconds)
            await finish(key, token)
        old = self._tasks.pop((kind, key), None)
        if old:
            old.cancel()
        self._tasks[(kind, key)] = asyncio.get_running_loop().create_task(later())

    async def possess(self, actor: str, target: str, reason: str, seconds: int) -> Dict[str, Any]:
        key = _k(target)
        notice = self.notice("possession_notice")
        if not notice:
            raise HTTPException(409, "possession_notice_not_set")
        if key in self.possessed:
            raise HTTPException(409, "already_possessed")
        if self.gov.is_frozen(target)[0]:
            raise HTTPException(409, "already_frozen")                  # someone froze them by other means: do not take that over silently
        self._audit("POSSESS", actor, target, f"seconds={seconds} reason={reason}")
        token = time.time()
        self.possessed[key] = {"user_id": target, "by": actor, "since": token, "until": token + seconds, "reason": reason}
        self.gov.freeze_avatar(target, actor, reason, {"mode": "possession"})
        delivered = await self._private(target, {"type": "host_notice", "kind": "possession", "text": notice, "until": token + seconds})
        if delivered < 1:
            # Nobody verified received the notice, so the person has not been told. Never keep control in that state.
            self.possessed.pop(key, None)
            self.gov.unfreeze_avatar(target, actor)
            self._audit("POSSESS_UNDONE", actor, target, "notice could not be delivered", required=False)
            raise HTTPException(409, "target_not_connected")
        await self.hub.broadcast_system_event({"type": "avatar_possessed", "payload": {"user_id": target, "by": actor}})
        if self.record(target).get("tracked"):
            self.log.add(target, "possessed", f"by {actor}, {seconds}s, notice delivered to {delivered} socket(s)")
        self._schedule("p", key, seconds, token, self._auto_release)
        return {"ok": True, "until": token + seconds, "notice_delivered": True}

    async def _auto_release(self, key: str, token: float) -> None:
        cur = self.possessed.get(key)
        if cur and cur["since"] == token:                       # only the possession this timer was made for
            try:
                await self.release("host_control_timer", cur["user_id"], automatic=True)
            except Exception:
                logger.exception("automatic release of %s failed", key)

    async def release(self, actor: str, target: str, automatic: bool = False) -> Dict[str, Any]:
        key = _k(target)
        cur = self.possessed.get(key)
        if not cur:
            raise HTTPException(404, "not possessed")
        self._audit("RELEASE", actor, target, "automatic" if automatic else "by host", required=not automatic)
        self.possessed.pop(key, None)
        task = self._tasks.pop(("p", key), None)
        if task and task is not asyncio.current_task():
            task.cancel()
        self.gov.unfreeze_avatar(cur["user_id"], actor)
        await self._private(target, {"type": "host_release"})
        await self.hub.broadcast_system_event({"type": "avatar_released", "payload": {"user_id": target, "by": actor, "automatic": automatic}})
        if self.record(target).get("tracked"):
            self.log.add(target, "released", f"by {actor}" + (" (timer)" if automatic else ""))
        return {"ok": True}

    async def drive(self, actor: str, target: str, pos: Any) -> Dict[str, Any]:
        cur = self.possessed.get(_k(target))
        if not cur or cur["by"] != actor:
            raise HTTPException(409, "you are not controlling this person")
        if not (isinstance(pos, list) and len(pos) == 2 and all(isinstance(p, (int, float)) and not isinstance(p, bool) and abs(p) < 1e5 for p in pos)):
            raise HTTPException(400, "pos must be two numbers")
        delivered = await self._private(target, {"type": "host_drive", "pos": [float(pos[0]), float(pos[1])]})
        return {"ok": True, "delivered": delivered > 0}

    async def timeout(self, actor: str, target: str, room: str, seconds: int, reason: str) -> Dict[str, Any]:
        key = _k(target)
        self._audit("TIMEOUT", actor, target, f"room={room} seconds={seconds} reason={reason}")
        token = time.time()
        self.timeouts[key] = {"user_id": target, "by": actor, "room": room, "since": token, "until": token + seconds, "reason": reason}
        event = {"type": "host_teleport", "room": room, "until": token + seconds, "recording": True}
        text = self.notice("timeout_notice")
        if text:
            event["text"] = text
        delivered = await self._private(target, event)
        self.log.add(target, "timeout", f"to {room} for {seconds}s by {actor}; detention is recorded")
        self._schedule("t", key, seconds, token, self._auto_end_timeout)
        return {"ok": True, "until": token + seconds, "delivered": delivered > 0, "notice_sent": bool(text)}

    async def _auto_end_timeout(self, key: str, token: float) -> None:
        cur = self.timeouts.get(key)
        if cur and cur["since"] == token:
            try:
                await self.end_timeout("host_control_timer", cur["user_id"], automatic=True)
            except Exception:
                logger.exception("automatic end of timeout for %s failed", key)

    async def end_timeout(self, actor: str, target: str, automatic: bool = False) -> Dict[str, Any]:
        key = _k(target)
        cur = self.timeouts.get(key)
        if not cur:
            raise HTTPException(404, "not in timeout")
        self._audit("TIMEOUT_END", actor, target, "automatic" if automatic else "by host", required=not automatic)
        self.timeouts.pop(key, None)
        task = self._tasks.pop(("t", key), None)
        if task and task is not asyncio.current_task():
            task.cancel()
        await self._private(target, {"type": "host_timeout_end", "room": cur["room"]})
        self.log.add(target, "timeout_end", f"by {actor}" + (" (timer)" if automatic else ""))
        return {"ok": True}

    def pending_for(self, person: str) -> List[Dict[str, Any]]:
        """What a newly connected page of this person must be told: a possession or timeout that is still running."""
        key, now, out = _k(person), time.time(), []
        cur = self.possessed.get(key)
        if cur and cur["until"] > now:
            notice = self.notice("possession_notice")
            if notice:
                out.append({"type": "host_notice", "kind": "possession", "text": notice, "until": cur["until"]})
        cur = self.timeouts.get(key)
        if cur and cur["until"] > now:
            event = {"type": "host_teleport", "room": cur["room"], "until": cur["until"], "recording": True}
            text = self.notice("timeout_notice")
            if text:
                event["text"] = text
            out.append(event)
        return out

    def on_room_change(self, person: str, left: str, entered: str) -> None:
        """Called by the walker socket registry when a verified person changes room. Tracked people get a line in their record."""
        if self.record(person).get("tracked"):
            self.log.add(person, "moved", f"{left or 'somewhere'} to {entered or 'somewhere'}")

    def state(self) -> Dict[str, Any]:
        return {"possessed": self.possessed, "timeouts": self.timeouts}

    def roster(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Who is on the walker right now, with what the host knows about each of them."""
        out = []
        for e in entries:
            rec, key = self.record(e["user_id"]), _k(e["user_id"])
            out.append(dict(e, name=rec.get("name") or e["user_id"], title=rec.get("title", ""), position=rec.get("position", ""), tracked=bool(rec.get("tracked")),
                            privileges=rec.get("privileges", {}), gifts=len(rec.get("gifts") or []),
                            possessed=self.possessed.get(key), timeout=self.timeouts.get(key)))
        return out


# ── routes ──────────────────────────────────────────────────────────────────────

def create_host_control_router(gov: Any, hub: Any, data_dir: Path, senders: Optional[List[Any]] = None, roster: Optional[Any] = None) -> APIRouter:
    host = HostControl(gov, hub, data_dir, senders)
    router = APIRouter(prefix="/api/host", tags=["host-control"])
    router.host = host  # type: ignore[attr-defined]

    async def body_of(request: Request) -> Dict[str, Any]:
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "body must be JSON") from None
        if not isinstance(body, dict):
            raise HTTPException(400, "body must be an object")
        return body

    @router.get("/state")
    async def state(identity: Dict[str, Any] = Depends(require_role(READ_ROLE))):
        return {"ok": True, **host.state()}

    @router.get("/roster")
    async def read_roster(identity: Dict[str, Any] = Depends(require_role(READ_ROLE))):
        return {"ok": True, "people": host.roster(roster() if roster else [])}

    @router.get("/bans")
    async def read_bans(identity: Dict[str, Any] = Depends(require_role(READ_ROLE))):
        """Who is out, so a boot or a ban can be undone from the same screen (lifting goes through /api/governance/unban)."""
        return {"ok": True, "bans": [{"user_id": b.user_id, "kind": b.ban_type.value, "reason": b.reason, "by": b.issued_by, "at": b.issued_at,
                                      "until": b.expires_at} for b in sorted(gov.active_bans(), key=lambda b: b.issued_at)]}

    @router.get("/people/{person}")
    async def read_person(person: str, identity: Dict[str, Any] = Depends(require_role(READ_ROLE))):
        return {"ok": True, "person": host.record(_clean_id(person, "person"))}

    @router.patch("/people/{person}")
    async def edit_person(person: str, request: Request, identity: Dict[str, Any] = Depends(require_role(CONTROL_ROLE))):
        body = await body_of(request)
        fields = {k: _text(body, k) for k in ("title", "position", "notes") if k in body}
        if "tracked" in body:
            fields["tracked"] = body["tracked"]
        if "name" in body:
            fields["name"] = body["name"]
        return {"ok": True, "person": host.edit(_clean_id(person, "person"), _actor(identity), fields)}

    @router.put("/people/{person}/privileges/{name}")
    async def privilege(person: str, name: str, request: Request, identity: Dict[str, Any] = Depends(require_role(CONTROL_ROLE))):
        body = await body_of(request)
        if not isinstance(body.get("value"), bool):
            raise HTTPException(400, "value must be true or false")
        return {"ok": True, "person": host.set_privilege(_clean_id(person, "person"), _actor(identity), name, body["value"])}

    @router.post("/people/{person}/gifts", status_code=201)
    async def gift(person: str, request: Request, identity: Dict[str, Any] = Depends(require_role(CONTROL_ROLE))):
        body = await body_of(request)
        kind = body.get("kind")
        item = _text(body, "item") or ""
        return {"ok": True, "person": host.give_gift(_clean_id(person, "person"), _actor(identity), kind, item)}

    @router.get("/people/{person}/log")
    async def tracker(person: str, date: Optional[str] = None, identity: Dict[str, Any] = Depends(require_role(READ_ROLE))):
        day = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if not _DATE.match(day):
            raise HTTPException(400, "date must be YYYY-MM-DD")
        return {"ok": True, "date": day, "log": host.log.read(_clean_id(person, "person"), day)}

    @router.post("/possess")
    async def possess(request: Request, identity: Dict[str, Any] = Depends(require_role(CONTROL_ROLE))):
        body = await body_of(request)
        return await host.possess(_actor(identity), _clean_id(body.get("user_id")), _text(body, "reason") or "",
                                  _seconds(body, DEFAULT_POSSESSION_SECONDS))

    @router.post("/release")
    async def release(request: Request, identity: Dict[str, Any] = Depends(require_role(CONTROL_ROLE))):
        body = await body_of(request)
        return await host.release(_actor(identity), _clean_id(body.get("user_id")))

    @router.post("/drive")
    async def drive(request: Request, identity: Dict[str, Any] = Depends(require_role(CONTROL_ROLE))):
        body = await body_of(request)
        return await host.drive(_actor(identity), _clean_id(body.get("user_id")), body.get("pos"))

    @router.post("/timeout")
    async def timeout(request: Request, identity: Dict[str, Any] = Depends(require_role(CONTROL_ROLE))):
        body = await body_of(request)
        room = body.get("room", DETENTION_ROOM)
        if not isinstance(room, str) or not _ROOM.match(room):
            raise HTTPException(400, "room must be a short id")
        return await host.timeout(_actor(identity), _clean_id(body.get("user_id")), room,
                                  _seconds(body, DEFAULT_TIMEOUT_SECONDS), _text(body, "reason") or "")

    @router.post("/end-timeout")
    async def end_timeout(request: Request, identity: Dict[str, Any] = Depends(require_role(CONTROL_ROLE))):
        body = await body_of(request)
        return await host.end_timeout(_actor(identity), _clean_id(body.get("user_id")))

    return router


__all__ = ["create_host_control_router", "HostControl", "TrackerLog", "PRIVILEGES", "DETENTION_ROOM"]
