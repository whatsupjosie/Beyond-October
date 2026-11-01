"""Owner-scoped Base/Horizon docking on the existing sync engine.

Cartridges, running hosts and docking replicas are distinct layers. This module
does not make a second persona or silently promote experiences into facts.
Hosts supply paired nodes; remote authentication/discovery remains transport work.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .engine import SyncEngine
from .identity import load_or_create_identity
from .store import SyncStore


class DockingNode:
    def __init__(self, root, *, owner_id: str, role: str, node_id=None):
        if role not in {"portable", "resident"} or not owner_id.strip():
            raise ValueError("docking requires an owner and portable/resident role")
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        owner_path = root / "owner.json"
        if owner_path.exists() and json.loads(owner_path.read_text())["owner_id"] != owner_id:
            raise ValueError("docking storage belongs to another owner")
        self.identity = load_or_create_identity(root / "identity.json", role, node_id)
        if not owner_path.exists():
            owner_path.write_text(json.dumps({"owner_id": owner_id}))
        self.owner_id = owner_id
        self.store = SyncStore(root / "sync.db")
        self.engine = SyncEngine(self.identity.node_id, self.store)
        self._cartridge = None
        self._cartridge_friend = None

    def attach_cartridge(self, cartridge, friend_id):
        self._cartridge, self._cartridge_friend = cartridge, friend_id

    def _put(self, kind, identity, fields):
        fields = {**fields, "owner_id": self.owner_id}
        previous = self.store.get(kind, identity)
        if previous is None or previous.deleted or previous.fields != fields:
            self.engine.upsert(kind, identity, fields)
        return identity

    def record_experience(self, *, user_text, reply_text, session_id, friend_id, source_ref, review=None):
        if not all(isinstance(value, str) and value.strip() for value in (session_id, friend_id, source_ref)):
            raise ValueError("experiences require session, companion and provenance")
        material = "\0".join([self.owner_id, self.identity.node_id, friend_id, session_id, source_ref])
        identity = hashlib.sha256(material.encode()).hexdigest()
        return self._put("experience", identity, dict(user_text=user_text, reply_text=reply_text,
            session_id=session_id, friend_id=friend_id, source_ref=source_ref,
            origin_node=self.identity.node_id, review=review, status="experienced"))

    def record_knowledge(self, identity, *, text, friend_id, source_ref, confirmed=False):
        if not text.strip() or not source_ref.strip() or not friend_id.strip() or not identity.strip():
            raise ValueError("knowledge requires text and provenance")
        identity = hashlib.sha256("\0".join([self.owner_id, friend_id, identity]).encode()).hexdigest()
        return self._put("knowledge", identity, dict(text=text, friend_id=friend_id,
            source_ref=source_ref, status="confirmed" if confirmed else "candidate"))

    def _stage_cartridge(self):
        if self._cartridge is None:
            return
        for memory in self._cartridge.memory.all():
            identity = hashlib.sha256((self.identity.node_id + "\0" + self._cartridge_friend + "\0" + str(memory.id)).encode()).hexdigest()
            self._put("memory", identity, dict(text=memory.text, friend_id=self._cartridge_friend,
                source_ref=f"cartridge:{memory.id}", memory_type=memory.memory_type,
                importance=memory.importance, status="cartridge_memory"))

    def health(self):
        with self.store.lock:
            checks = [row[0] for row in self.store.db.execute("PRAGMA quick_check")]
            conflicts = self.store.db.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0]
        return {"status": "healthy" if checks == ["ok"] else "unhealthy",
                "checks": checks, "owner_id": self.owner_id,
                "role": self.identity.role, "node_id": self.identity.node_id,
                "protocol": self.engine.PROTOCOL, "conflicts": conflicts}

    def dock(self, peer):
        before = [self.health(), peer.health()]
        if any(x["status"] != "healthy" for x in before):
            raise RuntimeError("docking health check failed")
        if self.owner_id != peer.owner_id:
            raise ValueError("cannot dock companions belonging to different owners")
        if self.identity.node_id == peer.identity.node_id:
            raise ValueError("docking nodes must have distinct identities")
        if {self.identity.role, peer.identity.role} != {"portable", "resident"}:
            raise ValueError("dock requires one Horizon portable and one Base resident")
        if self.engine.PROTOCOL != peer.engine.PROTOCOL:
            raise ValueError("docking protocol mismatch")
        self._stage_cartridge()
        peer._stage_cartridge()
        outward = self.engine.envelope(peer.engine.clock)
        inward = peer.engine.envelope(self.engine.clock)
        received_peer = peer.engine.receive(outward)
        received_self = self.engine.receive(inward)
        after = [self.health(), peer.health()]
        if any(x["status"] != "healthy" for x in after):
            status = "health_failed_after_sync"
        elif any(x["conflicts"] for x in after):
            status = "synced_with_conflicts"
        else:
            status = "synced"
        return {"status": status,
                "sent": sum(r.applied for r in received_peer),
                "received": sum(r.applied for r in received_self),
                "before": before, "after": after}

    def recall(self, *, owner_id, friend_id, query, limit=6, max_scan=1024):
        limit = max(0, min(20, int(limit)))
        if owner_id != self.owner_id:
            return {"items": [], "complete": True}
        terms = set(re.findall(r"\w+", query.casefold()))
        selected, scanned = [], 0
        with self.store.lock:
            rows = self.store.db.execute("SELECT entity_type,entity_id,payload FROM entities WHERE deleted=0 AND entity_type IN ('memory','knowledge','experience')")
            for row in rows:
                scanned += 1
                if scanned > max_scan:
                    break
                fields = json.loads(row["payload"])
                if fields.get("owner_id") != owner_id or fields.get("friend_id") != friend_id or fields.get("status") == "candidate":
                    continue
                text = fields.get("text") or ("User: " + str(fields.get("user_text", "")) + "\nCompanion: " + str(fields.get("reply_text", "")))
                score = len(terms & set(re.findall(r"\w+", text.casefold())))
                if score:
                    selected.append({"id": row["entity_id"], "kind": row["entity_type"],
                                     "text": text, "source_ref": fields.get("source_ref"), "score": score})
        selected.sort(key=lambda x: (-x["score"], x["id"]))
        return {"items": selected[:limit],
                "complete": scanned <= max_scan and len(selected) <= limit}

    def close(self):
        self.store.close()
