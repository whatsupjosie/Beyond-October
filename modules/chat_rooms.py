"""modules/chat_rooms.py - Role-gated chat rooms and private DM system. Feic Mo Chroi 2026."""
from __future__ import annotations

import hashlib
import json
import re
import logging
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketState

logger = logging.getLogger("pubcast.chat_rooms")

# Role hierarchy
ROLE_RANK: Dict[str, int] = {
    "guest":    0,
    "friend":   1,
    "crew":     2,
    "security": 3,
    "mod":      4,
    "owner":    5,
}

# Roles that bypass DM request
DM_BYPASS_ROLES: Set[str] = {"owner", "mod", "security"}

# Room registry
ROOM_REGISTRY: Dict[str, Dict[str, Any]] = {
    "stage":       {"display": "Stage",          "tier": "public",    "min_role": "guest",    "desc": "The main stage."},
    "gallery":     {"display": "Gallery",        "tier": "public",    "min_role": "guest",    "desc": "Artwork and community display."},
    "bar":         {"display": "Bar",            "tier": "public",    "min_role": "guest",    "desc": "Casual conversation."},
    "world":       {"display": "World",          "tier": "public",    "min_role": "guest",    "desc": "The PubWorld open space."},
    "greenroom":   {"display": "Green Room",     "tier": "social",    "min_role": "friend",   "desc": "Pre-show space for friends."},
    "lounge":      {"display": "Lounge",         "tier": "social",    "min_role": "friend",   "desc": "Private social space."},
    "dressing":    {"display": "Dressing Room",  "tier": "social",    "min_role": "friend",   "desc": "Avatar setup and prep."},
    "studio":      {"display": "Studio",         "tier": "backstage", "min_role": "crew",     "desc": "Main production floor."},
    "controlroom": {"display": "Control Room",   "tier": "backstage", "min_role": "crew",     "desc": "Technical direction."},
    "director":    {"display": "Director",       "tier": "backstage", "min_role": "crew",     "desc": "Camera switching."},
    "teleprompter":{"display": "Teleprompter",   "tier": "backstage", "min_role": "crew",     "desc": "Script feed."},
    "waitingroom": {"display": "Waiting Room",   "tier": "secure",    "min_role": "security", "desc": "Admission queue."},
    "governance":  {"display": "Governance",     "tier": "secure",    "min_role": "security", "desc": "Bans, mutes, freeze log."},
}

VALID_ROLES: Set[str] = set(ROLE_RANK.keys())


def role_can_access(role: str, room_id: str) -> bool:
    if room_id.startswith(("dm____", "dmv2_")):
        return False  # A public role cannot authorize a specific private pair.
    room = ROOM_REGISTRY.get(room_id)
    if not room:
        return False
    return ROLE_RANK.get(role, -1) >= ROLE_RANK.get(room["min_role"], 99)


def rooms_for_role(role: str) -> List[Dict[str, Any]]:
    tier_order = {"public": 0, "social": 1, "backstage": 2, "secure": 3}
    accessible = []
    for room_id, info in ROOM_REGISTRY.items():
        if role_can_access(role, room_id):
            accessible.append({
                "room_id":  room_id,
                "display":  info["display"],
                "tier":     info["tier"],
                "desc":     info["desc"],
                "min_role": info["min_role"],
            })
    return sorted(accessible, key=lambda r: (tier_order.get(r["tier"], 9), r["display"]))


def dm_room_id(user_a: str, user_b: str) -> str:
    """Preserve unambiguous historical room names, encode unsafe pairs in a fixed stem.

    Historical `____` delimited names collide for pairs such as (a____b,c)
    and (a,b____c). Never route those pairs through the legacy identifier.
    The digest is derived from a length-unambiguous JSON pair, not concatenation.
    """
    a, b = sorted((user_a.casefold(), user_b.casefold()))
    if ("____" not in a and "____" not in b and
            all(re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", name) for name in (a, b))):
        return f"dm____{a}____{b}"
    canonical = json.dumps([a, b], ensure_ascii=False, separators=(",", ":"))
    return "dmv2_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── DM Request system ─────────────────────────────────────────────────────────

class DMRequestStatus(str, Enum):
    PENDING  = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    BYPASSED = "bypassed"
    REVOKED = "revoked"


@dataclass
class DMRequest:
    request_id:   str
    from_user:    str
    from_role:    str
    from_display: str
    to_user:      str
    status:       DMRequestStatus = DMRequestStatus.PENDING
    created_at:   float = field(default_factory=time.time)
    resolved_at:  Optional[float] = None
    message:      str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class DMManager:
    """Transactional per-installation DM consent store.

    Consent is data, not a process-local convenience: an accepted invitation
    must survive restart and revocation must be immediately visible to other
    processes. Each operation opens a fresh SQLite connection to the same
    installation-local database, with BEGIN IMMEDIATE for atomic transitions.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Invitations include private sender/recipient identities and text.
        # Restrict both new and existing installation-local consent stores.
        if os.name == 'posix':
            try:
                fd = os.open(self.db_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(fd)
            os.chmod(self.db_path, 0o600)
        # Multiple request handlers can construct this manager concurrently on
        # first use. Switching a new DB to WAL needs a transient exclusive lock;
        # retry that initialization race rather than treating a healthy peer's
        # setup as a permanent DM outage. Ordinary write transactions retain
        # their independent SQLite busy timeout and never catch-and-ignore
        # permission, disk, schema, or integrity failures.
        for attempt in range(5):
            try:
                with self._connection() as db:
                    if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                        db.execute("PRAGMA journal_mode=WAL")
                    self._create_schema(db)
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))

    @staticmethod
    def _create_schema(db: sqlite3.Connection) -> None:
        db.execute("""CREATE TABLE IF NOT EXISTS dm_requests (
            request_id TEXT PRIMARY KEY,
            from_user TEXT NOT NULL, from_key TEXT NOT NULL,
            from_role TEXT NOT NULL, from_display TEXT NOT NULL,
            to_user TEXT NOT NULL, to_key TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN
                ('pending', 'accepted', 'declined', 'bypassed', 'revoked')),
            created_at REAL NOT NULL, resolved_at REAL,
            message TEXT NOT NULL
        )""")
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS dm_pending_pair
            ON dm_requests(from_key, to_key) WHERE status='pending'""")
        db.execute("""CREATE INDEX IF NOT EXISTS dm_recipient_pending
            ON dm_requests(to_key, created_at) WHERE status='pending'""")
        db.execute("""CREATE INDEX IF NOT EXISTS dm_participant_consent
            ON dm_requests(from_key, to_key, status)""")

    @contextmanager
    def _connection(self, *, writing: bool = False):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("PRAGMA synchronous=FULL")
            if writing:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _request(row: sqlite3.Row) -> DMRequest:
        return DMRequest(
            request_id=row["request_id"], from_user=row["from_user"],
            from_role=row["from_role"], from_display=row["from_display"],
            to_user=row["to_user"], status=DMRequestStatus(row["status"]),
            created_at=row["created_at"], resolved_at=row["resolved_at"],
            message=row["message"],
        )

    @staticmethod
    def _key(user: str) -> str:
        if not isinstance(user, str) or not user.strip():
            raise ValueError("A participant identity is required")
        return user.casefold()

    def request_dm(self, from_user: str, from_role: str, from_display: str,
                   to_user: str, message: str = "") -> DMRequest:
        sender, recipient = self._key(from_user), self._key(to_user)
        if sender == recipient:
            raise ValueError("Cannot send a DM request to yourself")
        status = (DMRequestStatus.BYPASSED if from_role in DM_BYPASS_ROLES
                  else DMRequestStatus.PENDING)
        req = DMRequest(
            request_id=uuid.uuid4().hex,
            from_user=from_user, from_role=from_role, from_display=from_display,
            to_user=to_user, status=status, message=message[:280],
        )
        with self._connection(writing=True) as db:
            if db.execute("""SELECT 1 FROM dm_requests WHERE from_key=? AND to_key=?
                             AND status='pending'""", (sender, recipient)).fetchone():
                raise ValueError(f"You already have a pending DM request to {to_user}.")
            if db.execute("""SELECT 1 FROM dm_requests WHERE
                ((from_key=? AND to_key=?) OR (from_key=? AND to_key=?))
                AND status IN ('accepted','bypassed') LIMIT 1""",
                (sender, recipient, recipient, sender)).fetchone():
                raise ValueError("A DM between these participants is already open")
            db.execute("""INSERT INTO dm_requests
                (request_id, from_user, from_key, from_role, from_display, to_user,
                 to_key, status, created_at, resolved_at, message)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (req.request_id, from_user, sender, from_role, from_display,
                 to_user, recipient, req.status.value, req.created_at, None, req.message))
        logger.info("DM %s: %s (%s) -> %s status=%s",
                    req.request_id, from_user, from_role, to_user, status.value)
        return req

    def accept(self, request_id: str, acting_user: str) -> DMRequest:
        return self._resolve(request_id, acting_user, DMRequestStatus.ACCEPTED)

    def decline(self, request_id: str, acting_user: str) -> DMRequest:
        return self._resolve(request_id, acting_user, DMRequestStatus.DECLINED)

    def _resolve(self, request_id: str, acting_user: str, target: DMRequestStatus) -> DMRequest:
        with self._connection(writing=True) as db:
            row = db.execute("SELECT * FROM dm_requests WHERE request_id=?", (request_id,)).fetchone()
            if row is None:
                raise KeyError(f"DM request '{request_id}' not found")
            if row["to_key"] != self._key(acting_user):
                raise PermissionError(f"Request {request_id} is addressed to {row['to_user']}")
            if row["status"] != DMRequestStatus.PENDING.value:
                raise ValueError(f"Request {request_id} is not pending")
            resolved_at = time.time()
            db.execute("""UPDATE dm_requests SET status=?, resolved_at=?
                          WHERE request_id=? AND status='pending'""",
                       (target.value, resolved_at, request_id))
            return self._request(db.execute(
                "SELECT * FROM dm_requests WHERE request_id=?", (request_id,)
            ).fetchone())

    def can_open_dm(self, user_a: str, user_b: str) -> bool:
        a, b = self._key(user_a), self._key(user_b)
        with self._connection() as db:
            return db.execute("""SELECT 1 FROM dm_requests
                WHERE ((from_key=? AND to_key=?) OR (from_key=? AND to_key=?))
                AND status IN ('accepted','bypassed') LIMIT 1""", (a, b, b, a)).fetchone() is not None

    def peer_for_room(self, room_id: str, acting_user: str) -> Optional[str]:
        """Resolve an active room through the consent database, never its name alone.

        This accommodates hashed v2 names without exposing or guessing participants,
        rejects ambiguous legacy names, and prevents other users opening a DM by
        constructing a room ID belonging to an unrelated accepted pair.
        """
        if not room_id.startswith(("dm____", "dmv2_")):
            return None
        for grant in self.active_for_user(acting_user):
            if dm_room_id(grant.from_user, grant.to_user) == room_id:
                if self._key(acting_user) == self._key(grant.from_user):
                    return grant.to_user
                return grant.from_user
        return None

    def revoke(self, acting_user: str, other_user: str) -> int:
        """A participant may withdraw an existing DM grant from either direction."""
        a, b = self._key(acting_user), self._key(other_user)
        if a == b:
            raise ValueError("Cannot revoke a DM with yourself")
        with self._connection(writing=True) as db:
            result = db.execute("""UPDATE dm_requests SET status='revoked', resolved_at=?
                WHERE ((from_key=? AND to_key=?) OR (from_key=? AND to_key=?))
                AND status IN ('accepted','bypassed')""", (time.time(), a, b, b, a))
            if not result.rowcount:
                raise ValueError("No open DM to revoke")
            return result.rowcount

    def pending_for_user(self, user_id: str) -> List[DMRequest]:
        with self._connection() as db:
            return [self._request(row) for row in db.execute(
                """SELECT * FROM dm_requests WHERE to_key=? AND status='pending'
                   ORDER BY created_at ASC, request_id ASC""", (self._key(user_id),)
            ).fetchall()]

    def active_for_user(self, user_id: str) -> List[DMRequest]:
        """Rebuild a participant's accepted DM list after any restart."""
        key = self._key(user_id)
        with self._connection() as db:
            return [self._request(row) for row in db.execute(
                """SELECT * FROM dm_requests WHERE (from_key=? OR to_key=?)
                   AND status IN ('accepted','bypassed')
                   ORDER BY created_at DESC, request_id DESC""", (key, key)
            ).fetchall()]


def get_dm_manager(data_dir: Path) -> DMManager:
    """Resolve DM authority from the same installation data root as the Hub."""
    return DMManager(Path(data_dir) / "global" / "dm_requests.sqlite3")


# ── Router factory ────────────────────────────────────────────────────────────

def create_chat_router(hub: Any, get_identity_fn: Any) -> APIRouter:
    router = APIRouter(prefix="/api/chat", tags=["chat"])
    dm = get_dm_manager(hub.data_dir)

    @router.get("/rooms")
    async def list_rooms(identity: Dict[str, Any] = Depends(get_identity_fn)):
        role = identity.get("role", "guest")
        accessible = rooms_for_role(role)
        for r in accessible:
            r["online"] = len(hub.rooms.get(r["room_id"], set()))
        return {"role": role, "room_count": len(accessible), "rooms": accessible}

    @router.get("/rooms/{room_id}")
    async def room_info(room_id: str, limit: int = Query(default=100, ge=1, le=200),
                        identity: Dict[str, Any] = Depends(get_identity_fn)):
        if room_id not in ROOM_REGISTRY:
            raise HTTPException(404, f"Room not found: {room_id}")
        role = identity.get("role", "guest")
        if not role_can_access(role, room_id):
            req = ROOM_REGISTRY[room_id]["min_role"]
            raise HTTPException(403, f"Role '{role}' cannot access this room (requires {req})")
        info = ROOM_REGISTRY[room_id].copy()
        info["room_id"] = room_id
        info["online"] = len(hub.rooms.get(room_id, set()))
        info["recent_messages"] = await hub.get_recent_history(room_id, limit=limit)
        return info

    @router.get("/rooms/{room_id}/export")
    async def export_room_log(room_id: str, identity: Dict[str, Any] = Depends(get_identity_fn)):
        """Download the full append-only transcript of an authorized shared room.

        Private DM logs are not exposed by this endpoint; BlackBox remains offline.
        """
        if room_id not in ROOM_REGISTRY:
            raise HTTPException(404, "Room not found")
        if not role_can_access(identity.get("role", "guest"), room_id):
            raise HTTPException(403, "Room not accessible")
        path = hub._log_path(room_id)
        if not path.is_file():
            raise HTTPException(404, "No recorded messages in this room")
        return FileResponse(path, media_type="application/x-ndjson",
                            filename=f"PubCast_{room_id}_chat.jsonl")

    @router.post("/rooms/{room_id}/send")
    async def send_message(room_id: str, request: Request,
                           identity: Dict[str, Any] = Depends(get_identity_fn)):
        if room_id not in ROOM_REGISTRY:
            raise HTTPException(404, f"Room not found: {room_id}")
        role = identity.get("role", "guest")
        if not role_can_access(role, room_id):
            raise HTTPException(403, f"Role '{role}' cannot send to this room")
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, "Expected a JSON object")
        if not isinstance(body, dict):
            raise HTTPException(400, "Expected a JSON object")
        text = body.get("text", body.get("message", ""))
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(400, "text must be non-empty text")
        if len(text) > 10000:
            raise HTTPException(413, "Message exceeds 10000 characters")
        user_id = identity.get("user_id", "unknown")
        client_message_id = body.get("client_message_id")
        if client_message_id is not None:
            from modules.chat_commit_store import ChatCommitStore
            try:
                client_message_id = ChatCommitStore.validate_client_id(client_message_id)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        try:
            committed = await hub.post_chat_message(
                room_id, user_id, text, client_message_id=client_message_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"ok": True, "room_id": room_id, "user_id": user_id,
                "text": text, "message_id": committed["message_id"],
                "duplicate": committed["duplicate"],
                "warnings": committed["warnings"]}

    @router.get("/roles")
    async def list_roles():
        result = []
        for role, rank in sorted(ROLE_RANK.items(), key=lambda x: x[1]):
            accessible = rooms_for_role(role)
            tiers = sorted(set(r["tier"] for r in accessible))
            result.append({
                "role": role, "rank": rank,
                "tiers": tiers, "room_count": len(accessible),
                "dm_bypass": role in DM_BYPASS_ROLES,
            })
        return {"roles": result}

    @router.post("/dm/request")
    async def request_dm(request: Request, identity: Dict[str, Any] = Depends(get_identity_fn)):
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, "Expected a JSON object")
        if not isinstance(body, dict):
            raise HTTPException(400, "Expected a JSON object")
        to_user, message = body.get("to_user"), body.get("message", "")
        if not isinstance(to_user, str) or not to_user.strip() or len(to_user) > 100:
            raise HTTPException(400, "to_user must be 1–100 characters")
        if not isinstance(message, str) or len(message) > 280:
            raise HTTPException(400, "message must be at most 280 characters")
        to_user = to_user.strip()
        from_user    = identity.get("user_id", "")
        from_role    = identity.get("role", "guest")
        from_display = identity.get("display_name") or identity.get("username") or from_user
        try:
            req = dm.request_dm(from_user, from_role, from_display, to_user, message)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        room = dm_room_id(from_user, to_user)
        is_open = req.status.value in ("accepted", "bypassed")
        await hub.send_private_event({from_user, to_user}, {
            "type": "dm_request",
            "payload": {
                "request_id": req.request_id,
                "from_user": from_user, "from_display": from_display,
                "from_role": from_role, "message": req.message,
                "bypassed": is_open, "dm_room": room if is_open else None,
            }
        })
        return {
            "ok": True, "request_id": req.request_id,
            "status": req.status.value,
            "dm_room": room if is_open else None,
            "message": (
                f"Channel open - connect to /ws/chat/{room}" if is_open
                else f"Request sent to {to_user}. Waiting for acceptance."
            ),
        }

    @router.post("/dm/accept/{request_id}")
    async def accept_dm(request_id: str, identity: Dict[str, Any] = Depends(get_identity_fn)):
        user_id = identity.get("user_id", "")
        try:
            req = dm.accept(request_id, user_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        room = dm_room_id(req.from_user, req.to_user)
        await hub.send_private_event({req.from_user, req.to_user}, {
            "type": "dm_accepted",
            "payload": {"request_id": request_id,
                        "from_user": req.from_user, "to_user": req.to_user,
                        "dm_room": room}
        })
        return {"ok": True, "status": "accepted", "dm_room": room}

    @router.post("/dm/decline/{request_id}")
    async def decline_dm(request_id: str, identity: Dict[str, Any] = Depends(get_identity_fn)):
        user_id = identity.get("user_id", "")
        try:
            req = dm.decline(request_id, user_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        await hub.send_private_event({req.from_user, req.to_user}, {
            "type": "dm_declined",
            "payload": {"request_id": request_id,
                        "from_user": req.from_user, "to_user": req.to_user}
        })
        return {"ok": True, "status": "declined"}

    @router.post("/dm/revoke")
    async def revoke_dm(request: Request, identity: Dict[str, Any] = Depends(get_identity_fn)):
        """A participant withdraws consent; live DM sockets are also evicted."""
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, "Expected a JSON object")
        if not isinstance(body, dict) or not isinstance(body.get("other_user"), str):
            raise HTTPException(400, "other_user is required")
        other_user = body["other_user"].strip()
        if not other_user or len(other_user) > 100:
            raise HTTPException(400, "other_user must be 1–100 characters")
        acting_user = identity.get("user_id", "")
        try:
            affected = dm.revoke(acting_user, other_user)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        room = dm_room_id(acting_user, other_user)
        await hub.close_room_connections(room)
        await hub.send_private_event({acting_user, other_user}, {
            "type": "dm_revoked",
            "payload": {"from_user": acting_user, "to_user": other_user, "dm_room": room},
        })
        return {"ok": True, "status": "revoked", "dm_room": room,
                "grants_revoked": affected}

    @router.get("/dm/pending")
    async def pending_dms(identity: Dict[str, Any] = Depends(get_identity_fn)):
        user_id = identity.get("user_id", "")
        pending = dm.pending_for_user(user_id)
        return {"count": len(pending), "requests": [r.to_dict() for r in pending]}

    @router.get("/dm/active")
    async def active_dms(identity: Dict[str, Any] = Depends(get_identity_fn)):
        user_id = identity.get("user_id", "")
        active = dm.active_for_user(user_id)
        rooms = [{"other_user": (r.to_user if user_id.casefold() == r.from_user.casefold()
                                  else r.from_user),
                  "dm_room": dm_room_id(r.from_user, r.to_user),
                  "status": r.status.value, "accepted_at": r.resolved_at or r.created_at}
                 for r in active]
        return {"count": len(rooms), "rooms": rooms}

    return router


def _legacy_ws_query_tokens_allowed() -> bool:
    return str(os.getenv("PUBCAST_ALLOW_LEGACY_WS_QUERY_TOKEN", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _websocket_identity(ws: WebSocket) -> Dict[str, Any]:
    """Resolve a WebSocket caller without placing production JWTs in URLs.

    Preferred production transports are the Authorization header (native/non-
    browser clients) and the same-origin HttpOnly session cookie issued by the
    auth routes (browser clients). Query-string JWTs are disabled by default and
    exist only behind an explicit legacy compatibility switch.
    """
    from modules.auth import WS_SESSION_COOKIE, decode_access_token
    from modules.route_security import auth_enforced

    candidates = []
    authorization = str(ws.headers.get("authorization") or "").strip()
    if authorization:
        scheme, _, credential = authorization.partition(" ")
        if scheme.casefold() != "bearer" or not credential.strip():
            raise ValueError("Invalid WebSocket Authorization header")
        candidates.append(("authorization", credential.strip()))

    cookie_token = str(ws.cookies.get(WS_SESSION_COOKIE) or "").strip()
    if cookie_token:
        candidates.append(("cookie", cookie_token))

    query_token = str(ws.query_params.get("token") or "").strip()
    if query_token:
        if auth_enforced() and not _legacy_ws_query_tokens_allowed():
            raise ValueError("Query-string WebSocket authentication is disabled")
        candidates.append(("query", query_token))

    identity = None
    for source, token in candidates:
        claims = decode_access_token(token)
        if not claims or not str(claims.get("sub") or "").strip():
            raise ValueError(f"Invalid or expired WebSocket {source} token")
        resolved = {
            "user_id": str(claims["sub"]),
            "role": str(claims.get("role") or "guest"),
            "authenticated": True,
        }
        if identity and (resolved["user_id"], resolved["role"]) != (identity["user_id"], identity["role"]):
            raise ValueError("Conflicting WebSocket identities")
        identity = resolved

    if identity:
        return identity
    if auth_enforced():
        raise ValueError("Authentication required for room socket")
    # Local-only development mode is explicitly not an identity guarantee.
    name = (ws.query_params.get("client_id") or "anon").strip()[:100] or "anon"
    return {"user_id": name, "role": "guest", "authenticated": False}


def install_chat_websocket(app: Any, hub: Any, get_identity_fn: Any) -> None:
    dm = get_dm_manager(hub.data_dir)
    # Every live Hub, including an idle second worker, must verify shared
    # consent again *before* exposing any outgoing private-room frame.
    hub.dm_authorizer = dm.can_open_dm

    @app.websocket("/ws/chat/{room_id}")
    async def chat_ws(ws: WebSocket, room_id: str):
        try:
            identity = _websocket_identity(ws)
        except ValueError as exc:
            await ws.close(code=1008, reason=str(exc))
            return
        role = identity["role"]
        user_id = identity["user_id"]
        display = user_id
        dm_other = None
        if room_id.startswith(("dm____", "dmv2_")):
            dm_other = dm.peer_for_room(room_id, user_id)
            if dm_other is None:
                await ws.close(code=1008, reason="No accepted DM for this participant")
                return
        elif room_id not in ROOM_REGISTRY or not role_can_access(role, room_id):
            await ws.close(code=1008, reason="Room not accessible")
            return

        try:
            await hub.connect(ws, room_id, uid=user_id, username=display, role=role,
                              authenticated=identity["authenticated"], dm_peer=dm_other)
        except PermissionError:
            await ws.close(code=1008, reason="DM permission revoked")
            return
        logger.info("WS chat: %s (%s) joined %s", user_id, role, room_id)
        try:
            while True:
                raw = await ws.receive_text()
                # A session already connected before a consent revocation must
                # never be allowed to publish another private message.
                if dm_other is not None and not dm.can_open_dm(user_id, dm_other):
                    await ws.close(code=1008, reason="DM permission revoked")
                    break
                try:
                    data = json.loads(raw)
                except (ValueError, TypeError):
                    await ws.send_json({"type": "error", "message": "Invalid JSON"})
                    continue
                if not isinstance(data, dict) or data.get("type") != "chat":
                    await ws.send_json({"type": "error", "message": "Only chat messages are allowed here"})
                    continue
                message = data.get("text", "")
                if not isinstance(message, str) or not message.strip() or len(message) > 10000:
                    await ws.send_json({"type": "error", "message": "Message must be 1–10000 characters"})
                    continue
                client_id = data.get("client_message_id")
                if client_id is not None:
                    from modules.chat_commit_store import ChatCommitStore
                    try:
                        client_id = ChatCommitStore.validate_client_id(client_id)
                    except ValueError as exc:
                        await ws.send_json({"type": "error", "message": str(exc)})
                        continue
                # Never use caller-supplied sender/role/control fields.
                try:
                    receipt = await hub.post_chat_message(
                        room_id, user_id, message, client_message_id=client_id)
                except ValueError as exc:
                    await ws.send_json({"type": "error", "message": str(exc)})
                    continue
                if client_id is not None:
                    await ws.send_json({"type": "chat_receipt", "payload": {
                        "message_id": receipt["message_id"],
                        "client_message_id": client_id, "duplicate": receipt["duplicate"],
                        "warnings": receipt["warnings"],
                    }})
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.warning("WS error in room %s: %s", room_id, exc)
        finally:
            await hub.disconnect(ws, room_id)
            logger.info("WS chat: %s left %s", user_id, room_id)
