"""PubPartner Blackbox Light: an owner-scoped adapter to ConversationArchive.

The unmodified VerbatimVault remains the primary source for exact input.
ConversationArchive is the *searchable full-dialogue projection*. No second
bespoke transcript format, no theatrical Blackbox access ritual.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from .conversation_archive import ConversationArchive


class BlackboxLightError(RuntimeError):
    pass


def _key(*parts: str) -> str:
    encoded = json.dumps(list(parts), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:32]


class PubPartnerBlackboxLight:
    """One backend implementation usable in standalone PubPartner and PubCast.

    The Search/Read interface is owner-AND-partner scoped at the SQL boundary.
    Captures are idempotent by exact source id, so restarts/replays cannot double
    a conversation's archived exchange. Failures are reported, never ignored.
    """

    def __init__(self, data_dir: Path):
        self.archive = ConversationArchive(Path(data_dir) / "conversation_archive" / "pubpartner_light.sqlite3")

    @staticmethod
    def conversation_id(user_id: str, friend_id: str, session_id: str) -> str:
        return "ppbl_" + _key(user_id, friend_id, session_id)

    @staticmethod
    def _message_id(kind: str, user_id: str, friend_id: str, session_id: str, source_id: str) -> str:
        return "ppbl_" + kind + "_" + _key(user_id, friend_id, session_id, source_id)

    def _ensure_conversation(self, *, user_id: str, friend_id: str, session_id: str) -> str:
        cid = self.conversation_id(user_id, friend_id, session_id)
        try:
            existing = self.archive.get_conversation(cid)
        except KeyError:
            try:
                self.archive.create_conversation(
                    conversation_id=cid, title=f"PubPartner · {friend_id}",
                    discussion_type="pubpartner-private", metadata={
                        "owner": user_id, "partner_id": friend_id, "session_id": session_id,
                    },
                )
            except sqlite3.IntegrityError:
                # Another request may have created this exact conversation.
                pass
            existing = self.archive.get_conversation(cid)
        meta = existing.get("metadata") or {}
        if meta.get("owner") != user_id or meta.get("partner_id") != friend_id or meta.get("session_id") != session_id:
            raise BlackboxLightError("conversation identity collision")
        return cid

    def capture_exchange(self, *, user_id: str, friend_id: str, session_id: str,
                         source_id: str, user_text: str, friend_response: str,
                         model: str = "", provider: str = "", receipt_id: str = "") -> Dict[str, Any]:
        if not user_id or not friend_id or not session_id or not source_id:
            raise BlackboxLightError("capture requires explicit user, partner, session, and source")
        if not isinstance(user_text, str) or not isinstance(friend_response, str):
            raise BlackboxLightError("capture requires original text")
        if not friend_response.strip():
            raise BlackboxLightError("no successful partner response to archive")
        cid = self._ensure_conversation(user_id=user_id, friend_id=friend_id, session_id=session_id)
        uid = self._message_id("u", user_id, friend_id, session_id, source_id)
        aid = self._message_id("a", user_id, friend_id, session_id, source_id)
        records = {m["message_id"]: m for m in self.archive.get_conversation(cid)["messages"]}
        if uid in records and records[uid]["exact_text"] != user_text:
            raise BlackboxLightError("source id reused with different user text")
        if aid in records and records[aid]["exact_text"] != friend_response:
            raise BlackboxLightError("source id reused with different partner text")
        if uid not in records:
            try:
                self.archive.append_message(
                    cid, speaker="User", exact_text=user_text, message_id=uid,
                    character_id=friend_id, room="pubpartner", program="pubpartner",
                    metadata={"source_id": source_id, "direction": "user"},
                )
            except sqlite3.IntegrityError:
                current = {m["message_id"]: m for m in self.archive.get_conversation(cid)["messages"]}
                if uid not in current or current[uid]["exact_text"] != user_text:
                    raise
        if aid not in records:
            try:
                self.archive.append_message(
                    cid, speaker="Partner", exact_text=friend_response, message_id=aid,
                    parent_message_id=uid, character_id=friend_id,
                    provider=provider, model=model, room="pubpartner", program="pubpartner",
                    metadata={"source_id": source_id, "receipt_id": receipt_id, "direction": "assistant"},
                )
            except sqlite3.IntegrityError:
                current = {m["message_id"]: m for m in self.archive.get_conversation(cid)["messages"]}
                if aid not in current or current[aid]["exact_text"] != friend_response:
                    raise
        return {"ok": True, "conversation_id": cid, "source_id": source_id, "idempotent": uid in records and aid in records}

    def list_conversations(self, *, user_id: str, friend_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self.archive._connect() as db:
            rows = db.execute(
                """SELECT c.conversation_id,c.title,c.created_at,c.updated_at,
                          COUNT(m.message_id) AS message_count
                   FROM conversations c LEFT JOIN messages m USING(conversation_id)
                   WHERE json_extract(c.metadata_json,'$.owner') = ?
                     AND json_extract(c.metadata_json,'$.partner_id') = ?
                   GROUP BY c.conversation_id ORDER BY c.updated_at DESC LIMIT ?""",
                (user_id, friend_id, max(1, min(200, int(limit)))),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, *, user_id: str, friend_id: str, conversation_id: str) -> Dict[str, Any]:
        with self.archive._connect() as db:
            allowed = db.execute(
                """SELECT 1 FROM conversations WHERE conversation_id = ?
                   AND json_extract(metadata_json,'$.owner') = ?
                   AND json_extract(metadata_json,'$.partner_id') = ?""",
                (conversation_id, user_id, friend_id),
            ).fetchone()
        if not allowed:
            raise KeyError("conversation not found")
        return self.archive.get_conversation(conversation_id)

    def search(self, *, user_id: str, friend_id: str, query: str, limit: int = 30) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        with self.archive._connect() as db:
            # Invalid FTS syntax produces sqlite3.OperationalError (HTTP 400).
            rows = db.execute(
                """SELECT m.message_id,m.conversation_id,m.ordinal,m.speaker,
                          m.exact_text,m.created_at,m.character_id,m.provider,m.model
                   FROM message_search s
                   JOIN messages m ON m.message_id=s.message_id
                   JOIN conversations c ON c.conversation_id=m.conversation_id
                   WHERE message_search MATCH ?
                     AND json_extract(c.metadata_json,'$.owner')=?
                     AND json_extract(c.metadata_json,'$.partner_id')=?
                   ORDER BY bm25(message_search),m.created_at LIMIT ?""",
                (query, user_id, friend_id, max(1, min(100, int(limit)))),
            ).fetchall()
        return [dict(row) for row in rows]

    def export(self, *, user_id: str, friend_id: str) -> Dict[str, Any]:
        """Full partner-owned export. Never truncate at the interactive list cap."""
        with self.archive._connect() as db:
            conversations = [
                dict(row) for row in db.execute(
                    """SELECT conversation_id FROM conversations
                       WHERE json_extract(metadata_json,'$.owner')=?
                         AND json_extract(metadata_json,'$.partner_id')=?
                       ORDER BY created_at,conversation_id""",
                    (user_id, friend_id),
                ).fetchall()
            ]
        return {
            "format": "PubPartnerBlackboxLight.v1",
            "owner": user_id, "partner_id": friend_id,
            "conversations": [
                self.get_conversation(user_id=user_id, friend_id=friend_id, conversation_id=row["conversation_id"])
                for row in conversations
            ],
        }
