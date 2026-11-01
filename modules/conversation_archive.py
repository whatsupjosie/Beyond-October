"""PubCast Conversation Archive authority.

Append-only/verbatim conversation storage, local FTS search, and portable exports.
This service deliberately does not own 2i manuscript state or model memory.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import json
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


@dataclass(frozen=True)
class ArchivedMessage:
    message_id: str
    conversation_id: str
    ordinal: int
    speaker: str
    exact_text: str
    created_at: str
    parent_message_id: Optional[str] = None
    character_id: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    room: Optional[str] = None
    program: Optional[str] = None
    build_id: Optional[str] = None
    attachments_json: str = "[]"
    metadata_json: str = "{}"


class ConversationArchive:
    """SQLite-backed canonical transcript authority for PubCast conversations."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        """Open one transaction-scoped connection and always close its handle.

        sqlite3.Connection.__exit__ commits/rolls back but does not close the
        connection. Python 3.13 reports that old pattern as a ResourceWarning;
        long-running PubCast servers would accumulate open DB handles until GC.
        """
        connection = sqlite3.connect(self.db_path)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            with connection:
                yield connection
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    discussion_type TEXT NOT NULL DEFAULT 'chat',
                    project_id TEXT,
                    build_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
                    ordinal INTEGER NOT NULL,
                    speaker TEXT NOT NULL,
                    exact_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    parent_message_id TEXT,
                    character_id TEXT,
                    model TEXT,
                    provider TEXT,
                    room TEXT,
                    program TEXT,
                    build_id TEXT,
                    attachments_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(conversation_id, ordinal)
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id, ordinal);
                CREATE VIRTUAL TABLE IF NOT EXISTS message_search USING fts5(
                    message_id UNINDEXED,
                    conversation_id UNINDEXED,
                    speaker,
                    exact_text,
                    character_id,
                    room,
                    program,
                    build_id,
                    tokenize='unicode61'
                );
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def create_conversation(
        self,
        *,
        title: str = "Untitled",
        conversation_id: Optional[str] = None,
        discussion_type: str = "chat",
        project_id: Optional[str] = None,
        build_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> str:
        conversation_id = conversation_id or f"chat_{uuid.uuid4().hex}"
        now = self._now()
        with self._connect() as db:
            db.execute(
                """INSERT INTO conversations
                (conversation_id,title,discussion_type,project_id,build_id,created_at,updated_at,metadata_json)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    conversation_id,
                    title or "Untitled",
                    discussion_type or "chat",
                    project_id,
                    build_id,
                    now,
                    now,
                    json.dumps(dict(metadata or {}), ensure_ascii=False, sort_keys=True),
                ),
            )
        return conversation_id

    def append_message(
        self,
        conversation_id: str,
        *,
        speaker: str,
        exact_text: str,
        message_id: Optional[str] = None,
        parent_message_id: Optional[str] = None,
        character_id: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        room: Optional[str] = None,
        program: Optional[str] = None,
        build_id: Optional[str] = None,
        attachments: Optional[Iterable[Mapping[str, Any]]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        created_at: Optional[str] = None,
    ) -> ArchivedMessage:
        """Append exact_text without trimming, normalization, or rewriting."""
        if not isinstance(exact_text, str):
            raise TypeError("exact_text must be a string")
        if not str(speaker):
            raise ValueError("speaker is required")
        message_id = message_id or f"msg_{uuid.uuid4().hex}"
        created_at = created_at or self._now()
        attachments_json = json.dumps(list(attachments or []), ensure_ascii=False, sort_keys=True)
        metadata_json = json.dumps(dict(metadata or {}), ensure_ascii=False, sort_keys=True)
        with self._connect() as db:
            # Serialize writers before reading the next ordinal. Without this,
            # concurrent requests can calculate the same ordinal and lose a turn.
            db.execute("BEGIN IMMEDIATE")
            exists = db.execute(
                "SELECT 1 FROM conversations WHERE conversation_id=?", (conversation_id,)
            ).fetchone()
            if not exists:
                raise KeyError(f"unknown conversation: {conversation_id}")
            if parent_message_id is not None:
                parent = db.execute(
                    "SELECT conversation_id FROM messages WHERE message_id=?",
                    (parent_message_id,),
                ).fetchone()
                if parent is None or parent["conversation_id"] != conversation_id:
                    raise ValueError("parent message must exist in the same conversation")
            ordinal = int(
                db.execute(
                    "SELECT COALESCE(MAX(ordinal),0)+1 FROM messages WHERE conversation_id=?",
                    (conversation_id,),
                ).fetchone()[0]
            )
            values = (
                message_id, conversation_id, ordinal, str(speaker), exact_text, created_at,
                parent_message_id, character_id, model, provider, room, program, build_id,
                attachments_json, metadata_json,
            )
            db.execute(
                """INSERT INTO messages
                (message_id,conversation_id,ordinal,speaker,exact_text,created_at,parent_message_id,
                 character_id,model,provider,room,program,build_id,attachments_json,metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                values,
            )
            db.execute(
                """INSERT INTO message_search
                (message_id,conversation_id,speaker,exact_text,character_id,room,program,build_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                (message_id, conversation_id, str(speaker), exact_text, character_id, room, program, build_id),
            )
            db.execute(
                "UPDATE conversations SET updated_at=? WHERE conversation_id=?",
                (created_at, conversation_id),
            )
        return ArchivedMessage(*values)

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM conversations WHERE conversation_id=?", (conversation_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown conversation: {conversation_id}")
            messages = db.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY ordinal",
                (conversation_id,),
            ).fetchall()
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        result["messages"] = []
        for message in messages:
            item = dict(message)
            item["attachments"] = json.loads(item.pop("attachments_json"))
            item["metadata"] = json.loads(item.pop("metadata_json"))
            result["messages"].append(item)
        return result

    def list_conversations(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT c.*, COUNT(m.message_id) AS message_count
                FROM conversations c LEFT JOIN messages m USING(conversation_id)
                GROUP BY c.conversation_id ORDER BY c.updated_at DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def list_conversations_for_owner(self, owner_id: str) -> list[dict[str, Any]]:
        """Filter ownership in SQLite before fetching transcript metadata."""
        with self._connect() as db:
            rows = db.execute(
                """SELECT c.*, COUNT(m.message_id) AS message_count
                FROM conversations c LEFT JOIN messages m USING(conversation_id)
                WHERE json_extract(c.metadata_json, '$.owner') = ?
                GROUP BY c.conversation_id ORDER BY c.updated_at DESC""",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def search(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        with self._connect() as db:
            # Validate MATCH independently of joins: with no owned rows SQLite
            # can otherwise skip FTS evaluation and accept malformed syntax.
            db.execute("SELECT rowid FROM message_search WHERE message_search MATCH ? LIMIT 1", (query,)).fetchone()
            rows = db.execute(
                """SELECT m.* FROM message_search s
                JOIN messages m ON m.message_id=s.message_id
                WHERE message_search MATCH ? ORDER BY bm25(message_search), m.created_at LIMIT ?""",
                (query, max(1, min(int(limit), 500))),
            ).fetchall()
        return [dict(row) for row in rows]

    def search_for_owner(self, query: str, owner_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Search only this owner's messages, applying LIMIT after ownership filtering.

        Owner isolation is enforced in SQLite, not by post-filtering a global
        top-N result set that could hide valid hits behind other users' data.
        """
        if not query.strip():
            return []
        with self._connect() as db:
            # Validate MATCH independently of joins: with no owned rows SQLite
            # can otherwise skip FTS evaluation and accept malformed syntax.
            db.execute("SELECT rowid FROM message_search WHERE message_search MATCH ? LIMIT 1", (query,)).fetchone()
            rows = db.execute(
                """SELECT m.* FROM message_search s
                JOIN messages m ON m.message_id=s.message_id
                JOIN conversations c ON c.conversation_id=m.conversation_id
                WHERE message_search MATCH ?
                  AND json_extract(c.metadata_json, '$.owner') = ?
                ORDER BY bm25(message_search), m.created_at LIMIT ?""",
                (query, owner_id, max(1, min(int(limit), 500))),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _safe_stem(value: str) -> str:
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._-")
        return stem[:100] or "Untitled"

    def export_documents(self, conversation_id: str, destination: Path | str) -> dict[str, Path]:
        """Materialize one conversation as TXT, Markdown, JSON, JSONL and offline HTML."""
        conversation = self.get_conversation(conversation_id)
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().strftime("%m-%d-%Y_%H-%M-%S_%f") + "_" + uuid.uuid4().hex[:8]
        kind = "BuildDiscussion" if conversation.get("discussion_type") == "build" else "Chat"
        title_stem = self._safe_stem(conversation["title"])
        id_stem = self._safe_stem(conversation_id)
        prefix = f"PubCast_{kind}_"
        stem = f"{prefix}{title_stem}_{id_stem}_{stamp}"
        # Each export creates five files, and some filesystems reject a single
        # filename component longer than 255 bytes. Keep room for the longest
        # extension and a portability margin while preserving legacy names for
        # ordinary conversations. Use a digest when shortening a long ID so
        # distinct IDs that share a prefix do not become indistinguishable.
        if len(stem) + len(".jsonl") > 240:
            id_digest = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()[:16]
            id_stem = f"{id_stem[:48]}_{id_digest}"
            title_budget = max(1, 240 - len(".jsonl") - len(prefix) - len(id_stem) - len(stamp) - 2)
            title_stem = title_stem[:title_budget]
            stem = f"{prefix}{title_stem}_{id_stem}_{stamp}"
        messages = conversation["messages"]
        plain = "\n\n".join(f"{m['speaker']}:\n{m['exact_text']}" for m in messages) + ("\n" if messages else "")
        markdown = "\n\n".join(f"## {m['speaker']}\n\n{m['exact_text']}" for m in messages) + ("\n" if messages else "")
        paths = {
            "txt": destination / f"{stem}.txt",
            "md": destination / f"{stem}.md",
            "json": destination / f"{stem}.json",
            "jsonl": destination / f"{stem}.jsonl",
            "html": destination / f"{stem}.html",
        }
        paths["txt"].write_text(plain, encoding="utf-8")
        paths["md"].write_text(markdown, encoding="utf-8")
        paths["json"].write_text(json.dumps(conversation, ensure_ascii=False, indent=2), encoding="utf-8")
        with paths["jsonl"].open("w", encoding="utf-8", newline="\n") as handle:
            for message in messages:
                handle.write(json.dumps(message, ensure_ascii=False, sort_keys=True) + "\n")
        html_messages = "\n".join(
            f"<section><h2>{escape(m['speaker'])}</h2><pre>{escape(m['exact_text'])}</pre></section>"
            for m in messages
        )
        paths["html"].write_text(
            "<!doctype html><meta charset='utf-8'><title>" + escape(conversation["title"]) +
            "</title><style>body{max-width:900px;margin:auto;padding:2rem;font-family:system-ui}"
            "pre{white-space:pre-wrap;font:inherit}section{margin:0 0 2rem}</style><h1>" +
            escape(conversation["title"]) + "</h1>" + html_messages,
            encoding="utf-8",
        )
        return paths


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


__all__ = ["ArchivedMessage", "ConversationArchive", "sha256_file"]
