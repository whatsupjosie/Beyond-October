# PubCast AI — hub.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart

from __future__ import annotations
import asyncio
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Set
from fastapi import WebSocket
from starlette.websockets import WebSocketState
from .persistence import read_json, write_json
from .models import ProductionState
from .route_security import auth_enforced
from .chat_commit_store import ChatCommitStore

logger = logging.getLogger(__name__)

class Hub:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.rooms: Dict[str, Set[WebSocket]] = {}
        self.user_display_name: Dict[str, str] = {}  # uid -> display name (optional; for presence)
        self._ws_meta: Dict[int, Dict[str, Any]] = {}  # id(ws) -> {uid, username, role, room}
        # production state on disk
        self.prod_file = self.data_dir / "global" / "production.json"
        if not self.prod_file.parent.exists():
            self.prod_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.prod_file.exists():
            write_json(self.prod_file, ProductionState().model_dump())
        self.on_chat_callback = None
        self.blackbox_witness = None  # Wired after BlackBox runtime starts.
        self.eq_monitoring_recorder = None  # Optional development evidence recorder.
        self.dm_authorizer = None  # Bound to persistent consent by chat route install.
        self._chat_commit_store = None  # Lazy, installation-local SQLite receipts.

    def get_production_state(self) -> Dict[str, Any]:
        return read_json(self.prod_file)

    def update_production_state(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        current = self.get_production_state()
        # merge shallowly
        current.update(patch or {})
        # validate through model
        model = ProductionState(**current)
        write_json(self.prod_file, model.model_dump())
        return model.model_dump()

    async def connect(
        self,
        ws: WebSocket,
        room: str,
        *,
        uid: str = "anon",
        username: str = "anon",
        role: str = "guest",
        authenticated: bool = False,
        _already_accepted: bool = False,
        dm_peer: str | None = None,
    ) -> None:
        # Recheck even when the caller already resolved consent: another worker
        # may have revoked it while the WebSocket handshake was in progress.
        if room.startswith(("dm____", "dmv2_")):
            if not self._dm_recipient_authorized({
                "uid": uid, "dm_peer": dm_peer, "authenticated": authenticated
            }):
                raise PermissionError("No current permission to join private room")
        if not _already_accepted:
            await ws.accept()
        self.rooms.setdefault(room, set()).add(ws)
        self._ws_meta[id(ws)] = {"uid": uid, "username": username, "role": role,
                                  "room": room, "authenticated": authenticated,
                                  "dm_peer": dm_peer}
        if uid != "anon":
            self.user_display_name[uid] = username
        # Do not load the entire lifetime of a busy room into memory or block
        # the event loop while reading its history. The bounded tail reader is
        # also used by the REST history endpoint.
        history_path = self._log_path(room)
        recent = (await asyncio.to_thread(self._read_history_sync, history_path, 50)
                  if history_path.exists() else [])
        if recent:
            if dm_peer and not self._dm_recipient_authorized({
                "uid": uid, "dm_peer": dm_peer, "authenticated": authenticated
            }):
                await self.disconnect(ws, room)
                return
            await ws.send_text(json.dumps({"type": "history", "payload": recent}))
        # announce presence with names
        await self._broadcast(room, {"type": "presence", "payload": self._presence_payload(room)})

    async def disconnect(self, ws: WebSocket, room: str) -> None:
        try:
            self.rooms.get(room, set()).discard(ws)
            self._ws_meta.pop(id(ws), None)
        finally:
            await self._broadcast(room, {"type": "presence", "payload": self._presence_payload(room)})
            if ws.application_state == WebSocketState.CONNECTED:
                try:
                    await ws.close()
                except Exception:
                    pass

    async def close_room_connections(self, room: str) -> int:
        """Evict a revoked private-room membership from all current sockets."""
        peers = list(self.rooms.get(room, set()))
        for ws in peers:
            await self.disconnect(ws, room)
        return len(peers)

    def participants(self, room: str) -> List[Dict[str, Any]]:
        """Return list of participant metadata dicts for a room."""
        result = []
        for ws in self.rooms.get(room, set()):
            meta = self._ws_meta.get(id(ws))
            if meta:
                result.append({"uid": meta["uid"], "username": meta["username"], "role": meta["role"]})
        return result

    def _presence_payload(self, room: str) -> Dict[str, Any]:
        return {
            "room": room,
            "count": len(self.rooms.get(room, set())),
            "participants": self.participants(room),
        }

    async def broadcast_system_event(self, event: Dict[str, Any]):
        for room, conns in self.rooms.items():
            await self._broadcast(room, event)

    async def send_private_event(self, user_ids: Set[str], event: Dict[str, Any]) -> int:
        """Deliver a private notification only to verified sockets of its addressees.

        Presence in a public room, an unverified client_id or a legacy Hub
        connection is *not* sufficient proof of identity. A user connected in
        multiple rooms receives the notification once per physical socket.
        Offline recipients can retrieve pending DM requests via the HTTP API.
        """
        recipients = {uid.casefold() for uid in user_ids if isinstance(uid, str) and uid}
        if not recipients:
            return 0
        wire = json.dumps(event)
        delivered = 0
        visited: Set[int] = set()
        for connections in list(self.rooms.values()):
            for ws in list(connections):
                key = id(ws)
                if key in visited:
                    continue
                visited.add(key)
                meta = self._ws_meta.get(key)
                if (not meta or not meta.get("authenticated") or
                        str(meta.get("uid") or "").casefold() not in recipients):
                    continue
                if ws.application_state != WebSocketState.CONNECTED:
                    continue
                try:
                    await ws.send_text(wire)
                    delivered += 1
                except Exception:
                    logger.warning("Private notification delivery failed for authenticated socket")
        return delivered

    async def broadcast_presence_update(self, user_id: str, display_name: str):
        # Could be extended to map sockets to user ids to show names; minimal for now
        self.user_display_name[user_id] = display_name
        await self.broadcast_system_event({"type": "user_update", "payload": {"user_id": user_id, "display_name": display_name}})

    async def handle_message(self, ws: WebSocket, room: str, raw: str):
        # Expect raw to be JSON string
        try:
            data = json.loads(raw)
        except Exception as exc:
            logger.debug("hub: malformed WS frame in room=%s: %s", room, exc)
            return
        if not isinstance(data, dict):
            await ws.send_text(json.dumps({"type": "error", "payload": {"msg": "JSON object required"}}))
            return
        typ = data.get("type")
        if typ == "chat":
            meta = self._ws_meta.get(id(ws))
            text = data.get("text")
            if not isinstance(text, str) or not text.strip() or len(text) > 10000:
                await ws.send_text(json.dumps({"type": "error", "payload": {"msg": "Invalid chat text"}}))
                return
            if auth_enforced() and (not meta or not meta.get("authenticated")):
                await ws.send_text(json.dumps({"type": "error", "payload": {"msg": "Authentication required"}}))
                return
            client_id = data.get("client_message_id")
            if client_id is not None:
                try:
                    client_id = ChatCommitStore.validate_client_id(client_id)
                except ValueError as exc:
                    await ws.send_text(json.dumps({"type": "error", "payload": {"msg": str(exc)}}))
                    return
            # Legacy public clients may still provide a display name in local
            # development. A verified connection must never be impersonated by
            # a sender/user_id field supplied in a WebSocket frame.
            verified = bool(meta and meta.get("authenticated"))
            sender_id = (meta["uid"] if verified else
                         data.get("user_id") or data.get("user") or
                         (meta["uid"] if meta else "anon"))
            sender = (meta["username"] if verified else data.get("user", "anon"))
            if client_id is not None:
                # A keyed legacy WebSocket send follows the same durable
                # receipt path as REST. Never trust the author's identity in
                # the frame; the verified socket determines its receipt key.
                try:
                    receipt = await self.post_chat_message(room, str(sender_id), text,
                                                           client_message_id=client_id)
                except ValueError as exc:
                    await ws.send_text(json.dumps({"type": "error", "payload": {"msg": str(exc)}}))
                    return
                await ws.send_text(json.dumps({"type": "chat_receipt", "payload": {
                    "message_id": receipt["message_id"], "client_message_id": client_id,
                    "duplicate": receipt["duplicate"], "warnings": receipt["warnings"],
                }}))
                return
            payload = {
                "message_id": uuid.uuid4().hex,
                "t": time.time(),
                "room": room,
                "user": sender,
                "user_id": sender_id,
                "text": text,
            }
            await asyncio.to_thread(ChatCommitStore._append_durable, self._log_path(room), payload)
            self._witness_chat(payload)
            await self._broadcast(room, {"type": "chat", "payload": payload})
            if callable(self.on_chat_callback):
                try:
                    await self.on_chat_callback(payload)
                except Exception:
                    # The user's text is already on disk; a failed AI response
                    # must not turn a successful send into an apparent failure.
                    logger.exception("Chat AI callback failed after message %s was persisted", payload["message_id"])
        elif typ == "signal":
            # extension point for invites / cues
            await self._broadcast(room, {"type": "signal", "payload": data.get("payload", {})})
        elif typ == "production_state":
            # allow control room to push updates via ws (UI convenience)
            meta = self._ws_meta.get(id(ws))
            if auth_enforced() and (not meta or not meta.get("authenticated") or
                                    meta.get("role") not in {"mod", "owner"}):
                await ws.send_text(json.dumps({"type": "error", "payload": {"msg": "Production control requires mod or owner"}}))
                return
            patch = data.get("payload", {})
            if not isinstance(patch, dict):
                await ws.send_text(json.dumps({"type": "error", "payload": {"msg": "Invalid production patch"}}))
                return
            updated = self.update_production_state(patch)
            await self.broadcast_system_event({"type": "production_state", "payload": updated})
        else:
            # echo unknown
            await ws.send_text(json.dumps({"type": "error", "payload": {"msg": "unknown type"}}))

    def _dm_recipient_authorized(self, meta: Dict[str, Any] | None) -> bool:
        """Check the live, persistent permission on every private delivery.

        A database outage fails closed. In particular, no private frame may be
        forwarded based only on old in-memory WebSocket membership.
        """
        if (not meta or not meta.get("authenticated") or not meta.get("dm_peer")
                or not callable(self.dm_authorizer)):
            return False
        try:
            return bool(self.dm_authorizer(meta["uid"], meta["dm_peer"]))
        except Exception:
            logger.exception("Private room authorization unavailable; denying outgoing frame")
            return False

    async def _broadcast(self, room: str, msg: Dict[str, Any]):
        dead: List[WebSocket] = []
        revoked: List[WebSocket] = []
        wire = json.dumps(msg)
        private = room.startswith(("dm____", "dmv2_"))
        for ws in list(self.rooms.get(room, set())):
            meta = self._ws_meta.get(id(ws))
            # A revocation on another server worker must not leave this worker
            # broadcasting new private frames to an old authorized socket.
            # Fail closed if the local authorizer was never wired.
            if private and not self._dm_recipient_authorized(meta):
                revoked.append(ws)
                continue
            try:
                if ws.application_state == WebSocketState.CONNECTED:
                    await ws.send_text(wire)
                else:
                    dead.append(ws)
            except Exception as exc:
                logger.debug("hub: broadcast send failed to client in room=%s: %s", room, exc)
                dead.append(ws)
        for ws in dead:
            self.rooms.get(room, set()).discard(ws)
            self._ws_meta.pop(id(ws), None)
        for ws in revoked:
            if ws in self.rooms.get(room, set()):
                await self.disconnect(ws, room)

    def _log_path(self, room: str) -> Path:
        # Room IDs are filesystem components. Never permit separators, parent
        # traversal, Windows drive syntax, or Windows special device names.
        if not isinstance(room, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,159}", room):
            raise ValueError("Invalid room identifier")
        if room.upper().split(".", 1)[0] in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise ValueError("Reserved room identifier")
        logs_dir = self.data_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir / f"{room}.jsonl"

    # ── Methods required by BotManager ───────────────────────────────────────

    async def is_user_in_room(self, room: str, user_id: str) -> bool:
        """Return True if any live WebSocket in the room belongs to user_id.

        Now backed by real per-connection identity tracking (_ws_meta) instead
        of the prior conservative approximation. Falls back to the old
        "has a display name registered this session" check only if no live
        connection metadata matches, preserving bot-safe behavior for any
        caller that hasn't been updated to pass real uid/username/role into
        connect() yet.
        """
        for ws in self.rooms.get(room, set()):
            meta = self._ws_meta.get(id(ws))
            if meta and meta.get("uid") == user_id:
                return True
        return user_id in self.user_display_name

    async def get_recent_history(self, room: str, limit: int = 12) -> list:
        """Return the last `limit` chat messages from a room's log.

        File I/O is dispatched to a thread via run_in_executor so the async
        event loop is never blocked - safe to call from Jeremy's watcher loop.
        """
        history_path = self._log_path(room)
        if not history_path.exists():
            return []
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._read_history_sync, history_path, limit
        )

    def _read_history_sync(self, path: Path, limit: int) -> list:
        """Read only the tail, not the entire lifetime of a busy shared room.

        JSONL messages are UTF-8 and newline-terminated. The backward read uses
        byte chunks, then decodes only complete trailing lines; malformed lines
        cannot prevent recovery of the remaining messages.
        """
        if limit <= 0:
            return []
        limit = min(int(limit), 500)
        with open(path, "rb") as handle:
            handle.seek(0, 2)
            position = handle.tell()
            chunks = []
            newline_count = 0
            while position and newline_count <= limit:
                size = min(8192, position)
                position -= size
                handle.seek(position)
                block = handle.read(size)
                chunks.append(block)
                newline_count += block.count(b"\n")
        recent = b"".join(reversed(chunks)).splitlines()[-limit:]
        result = []
        for line in recent:
            try:
                result.append(json.loads(line.decode("utf-8")))
            except (ValueError, UnicodeDecodeError):
                continue
        return result

    def _witness_chat(self, payload: Dict[str, Any]) -> bool:
        witness = self.blackbox_witness
        if witness is None:
            return False
        try:
            receipt = witness.record_event(
                "chat.message", source="chat", actor=str(payload.get("user_id") or "anon"),
                data={"room": payload.get("room"), "text": payload.get("text"),
                      "t": payload.get("t"), "message_id": payload.get("message_id")},
            )
            if receipt is None:
                logger.warning("Chat message persisted in room %s but BlackBox witness failed", payload.get("room"))
                return False
            return True
        except Exception:
            # A failed independent witness is important, but it must not
            # change the HTTP send result after the canonical room log
            # committed. Recovery/reconciliation is still an open feature.
            logger.exception("BlackBox witness failed after chat message %s was persisted", payload.get("message_id"))
            return False

    async def post_chat_message(self, room: str, user_id: str, text: str,
                                client_message_id: str | None = None) -> Dict[str, Any]:
        """Commit room text first, then try the independent side effects.

        A UUID-keyed retry reuses the existing persisted message without a
        second broadcast or bot callback. Legacy unkeyed sends retain their
        existing contract and must not be described as idempotent.
        """
        display_name = self.user_display_name.get(user_id, user_id)
        if client_message_id is not None:
            if self._chat_commit_store is None:
                self._chat_commit_store = ChatCommitStore(self.data_dir)
            payload, duplicate = await asyncio.to_thread(
                self._chat_commit_store.commit, room, user_id, text,
                client_message_id, display_name)
            if duplicate:
                return {**payload, "duplicate": True, "warnings": [
                    "Message already saved; the previous BlackBox/AI delivery state is not rechecked"
                ]}
        else:
            payload = {
                "message_id": uuid.uuid4().hex, "t": time.time(),
                "room": room, "user": display_name, "user_id": user_id,
                "text": text,
            }
            await asyncio.to_thread(ChatCommitStore._append_durable, self._log_path(room), payload)
        witnessed = self._witness_chat(payload)
        if self.eq_monitoring_recorder is not None:
            try:
                self.eq_monitoring_recorder.record_message(payload)
            except Exception:
                logger.exception("EQ recorder failed after chat message %s was persisted", payload["message_id"])
        await self._broadcast(room, {"type": "chat", "payload": payload})
        warnings = [] if witnessed else ["BlackBox witness unavailable for this message"]
        if callable(self.on_chat_callback):
            try:
                await self.on_chat_callback(payload)
            except Exception:
                logger.exception("Chat AI callback failed after message %s was persisted", payload["message_id"])
                warnings.append("AI response could not be started for this message")
        payload["warnings"] = warnings
        payload["duplicate"] = False
        return payload

    def invalidate_user_cache(self, user_id: str) -> None:
        """No-op cache invalidation hook (extended in future presence layer)."""
        self.user_display_name.pop(user_id, None)
