# PubCast AI — system_memory.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rear View Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""
system_memory.py — Jeremy Cricket's operational process store.

Jeremy Cricket is the system's public-facing voice. He is not a character.
He has no avatar, no seat in the room, no story presence. He is background
process infrastructure that speaks when the system needs to reach a person
directly — warmly, personally, in the moment.

This module is his store. It holds:

  PROTOCOLS       — rules and how-tos (timeout rules, entry procedures, etc.)
  COACHING        — what Jeremy observed coaching individuals (cross-session)
  SYSTEM_INSIGHT  — patterns Jeremy synthesized across sessions for the host

Jeremy reads from this store when:
  - A guest asks a rule question
  - An AI needs coaching guidance
  - The Room Conductor needs a pre-session briefing
  - Governance needs a pattern report

Jeremy does NOT store here:
  - Error logs, rendering state, frame rates — that is e-PETE's domain
  - Character memories — those live in CricketKeeper per-character SQLite
  - Bans, consents, audit records — those live in governance.db

Architecture
------------
  SQLite at data/system/system_memory.db
  Thread-safe via asyncio.to_thread
  No external dependencies beyond stdlib
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("pubcast.system_memory")


# ── Entry types ───────────────────────────────────────────────────────────────

class SystemEntryType(str, Enum):
    PROTOCOL       = "protocol"        # rules and procedures (governance-adjacent)
    COACHING       = "coaching"        # what Jeremy observed helping an individual
    SYSTEM_INSIGHT = "system_insight"  # patterns synthesized across sessions


# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS system_memory (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_type   TEXT    NOT NULL,
    topic        TEXT    NOT NULL,          -- e.g. "timeout", "proving_ground", "entry"
    content      TEXT    NOT NULL,
    importance   INTEGER NOT NULL DEFAULT 5,
    tags         TEXT    NOT NULL DEFAULT '[]',
    created_at   REAL    NOT NULL,
    updated_at   REAL    NOT NULL,
    session_id   TEXT    DEFAULT NULL,      -- which session this came from (if any)
    subject_id   TEXT    DEFAULT NULL       -- guest_id or ai_id if coaching record
);

CREATE INDEX IF NOT EXISTS idx_entry_type ON system_memory (entry_type);
CREATE INDEX IF NOT EXISTS idx_topic      ON system_memory (topic);
CREATE INDEX IF NOT EXISTS idx_subject    ON system_memory (subject_id);
CREATE INDEX IF NOT EXISTS idx_importance ON system_memory (importance DESC);
"""


# ── Entry dataclass ───────────────────────────────────────────────────────────

@dataclass
class SystemEntry:
    id:          int
    entry_type:  SystemEntryType
    topic:       str
    content:     str
    importance:  int
    tags:        List[str]
    created_at:  float
    updated_at:  float
    session_id:  Optional[str]
    subject_id:  Optional[str]

    @classmethod
    def from_row(cls, row: tuple) -> "SystemEntry":
        (id_, entry_type, topic, content, importance,
         tags_json, created_at, updated_at, session_id, subject_id) = row
        return cls(
            id=id_,
            entry_type=SystemEntryType(entry_type),
            topic=topic,
            content=content,
            importance=importance,
            tags=json.loads(tags_json),
            created_at=created_at,
            updated_at=updated_at,
            session_id=session_id,
            subject_id=subject_id,
        )

    def relevance_score(self, query_tokens: List[str]) -> float:
        """Score relevance to a query by keyword overlap + importance."""
        text = (self.topic + " " + self.content + " " + " ".join(self.tags)).lower()
        overlap = sum(1 for t in query_tokens if t in text)
        if not overlap and query_tokens:
            return 0.0
        importance_weight = (self.importance / 10) ** 2
        return overlap * importance_weight


# ── SystemMemory ──────────────────────────────────────────────────────────────

class SystemMemory:
    """
    Jeremy Cricket's operational process store.

    Not a character. Not a governance record. Jeremy's working memory
    for protocols, coaching observations, and system-level insights.

    Usage
    -----
        system_mem = SystemMemory(data_dir=Path("data/system"))
        await system_mem.init()

        # Store a protocol
        await system_mem.store_protocol(
            topic="timeout",
            content="First offense: 5 minute cooldown. Repeated: manual review required.",
            importance=9,
            tags=["timeout", "discipline", "entry"],
        )

        # Jeremy assists a guest
        rules = await system_mem.get_protocols(query="timeout rule")

        # Jeremy logs a coaching observation
        await system_mem.log_coaching(
            subject_id="ai_pete_01",
            session_id="sess_abc",
            topic="proving_ground",
            content="AI struggled with rotation. Overshot turns 3 times. Responded well to slower cue.",
            importance=6,
        )

        # Jeremy synthesizes for Room Conductor
        insights = await system_mem.get_insights(topic="proving_ground")
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._db_path = data_dir / "system_memory.db"
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()

    async def init(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._sync_init)
        logger.info("SystemMemory ready at %s", self._db_path)

    def _sync_init(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None

    # ── Write ─────────────────────────────────────────────────────────────────

    async def store_protocol(
        self,
        topic: str,
        content: str,
        importance: int = 8,
        tags: Optional[List[str]] = None,
    ) -> int:
        """Store or update a system protocol/rule."""
        return await self._write(
            entry_type=SystemEntryType.PROTOCOL,
            topic=topic,
            content=content,
            importance=importance,
            tags=tags or [],
            session_id=None,
            subject_id=None,
        )

    async def log_coaching(
        self,
        subject_id: str,
        session_id: str,
        topic: str,
        content: str,
        importance: int = 5,
        tags: Optional[List[str]] = None,
    ) -> int:
        """Log a coaching observation Jeremy made about an individual."""
        return await self._write(
            entry_type=SystemEntryType.COACHING,
            topic=topic,
            content=content,
            importance=importance,
            tags=tags or [subject_id, topic],
            session_id=session_id,
            subject_id=subject_id,
        )

    async def store_insight(
        self,
        topic: str,
        content: str,
        importance: int = 7,
        tags: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """Store a system-level insight Jeremy synthesized across sessions."""
        return await self._write(
            entry_type=SystemEntryType.SYSTEM_INSIGHT,
            topic=topic,
            content=content,
            importance=importance,
            tags=tags or [topic],
            session_id=session_id,
            subject_id=None,
        )

    async def _write(
        self,
        entry_type: SystemEntryType,
        topic: str,
        content: str,
        importance: int,
        tags: List[str],
        session_id: Optional[str],
        subject_id: Optional[str],
    ) -> int:
        importance = max(1, min(10, importance))
        now = time.time()
        async with self._lock:
            row_id = await asyncio.to_thread(
                self._sync_insert,
                entry_type.value, topic, content, importance,
                json.dumps(tags), now, session_id, subject_id,
            )
        logger.debug(
            "SystemMemory stored [%s | %s | importance=%d]: %s",
            entry_type.value, topic, importance, content[:80]
        )
        return row_id

    def _sync_insert(
        self,
        entry_type: str, topic: str, content: str, importance: int,
        tags_json: str, now: float,
        session_id: Optional[str], subject_id: Optional[str],
    ) -> int:
        cur = self._conn.execute(
            """INSERT INTO system_memory
               (entry_type, topic, content, importance, tags,
                created_at, updated_at, session_id, subject_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry_type, topic, content, importance, tags_json,
             now, now, session_id, subject_id),
        )
        self._conn.commit()
        return cur.lastrowid

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_protocols(
        self,
        query: str = "",
        topic: Optional[str] = None,
        max_results: int = 10,
    ) -> List[SystemEntry]:
        """
        Retrieve protocols relevant to a query.
        Jeremy reads these when a guest asks a rule question.
        """
        return await self._fetch(
            entry_type=SystemEntryType.PROTOCOL,
            query=query,
            topic=topic,
            subject_id=None,
            max_results=max_results,
        )

    async def get_coaching_history(
        self,
        subject_id: str,
        query: str = "",
        max_results: int = 10,
    ) -> List[SystemEntry]:
        """
        Retrieve coaching history for a specific individual.
        Jeremy reads these when someone returns across sessions.
        """
        return await self._fetch(
            entry_type=SystemEntryType.COACHING,
            query=query,
            topic=None,
            subject_id=subject_id,
            max_results=max_results,
        )

    async def get_insights(
        self,
        topic: Optional[str] = None,
        query: str = "",
        max_results: int = 10,
    ) -> List[SystemEntry]:
        """
        Retrieve system-level insights.
        Jeremy reads these when briefing the Room Conductor or host.
        """
        return await self._fetch(
            entry_type=SystemEntryType.SYSTEM_INSIGHT,
            query=query,
            topic=topic,
            subject_id=None,
            max_results=max_results,
        )

    async def _fetch(
        self,
        entry_type: SystemEntryType,
        query: str,
        topic: Optional[str],
        subject_id: Optional[str],
        max_results: int,
    ) -> List[SystemEntry]:
        async with self._lock:
            entries = await asyncio.to_thread(
                self._sync_fetch, entry_type.value, topic, subject_id
            )
        if not entries:
            return []

        if query.strip():
            tokens = _tokenize(query)
            if tokens:
                # Real keywords — score and filter
                scored = [(e.relevance_score(tokens), e) for e in entries]
                scored.sort(key=lambda x: x[0], reverse=True)
                matched = [e for score, e in scored if score > 0]
                if matched:
                    return matched[:max_results]
                # No keyword matches — fall through to importance sort
            # Empty tokens (all stopwords) or no keyword matches — return by importance
            entries.sort(key=lambda e: e.importance, reverse=True)
            return entries[:max_results]
        else:
            # No query at all — return by importance
            entries.sort(key=lambda e: e.importance, reverse=True)
            return entries[:max_results]

    def _sync_fetch(
        self,
        entry_type: str,
        topic: Optional[str],
        subject_id: Optional[str],
    ) -> List[SystemEntry]:
        sql = "SELECT * FROM system_memory WHERE entry_type=?"
        params: list = [entry_type]
        if topic:
            sql += " AND topic=?"
            params.append(topic)
        if subject_id:
            sql += " AND subject_id=?"
            params.append(subject_id)
        rows = self._conn.execute(sql, params).fetchall()
        return [SystemEntry.from_row(r) for r in rows]

    async def delete(self, entry_id: int) -> None:
        """Remove a specific entry."""
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM system_memory WHERE id=?", (entry_id,)
            )
            await asyncio.to_thread(self._conn.commit)

    # ── Diagnostics ───────────────────────────────────────────────────────────

    async def health(self) -> Dict:
        async with self._lock:
            rows = await asyncio.to_thread(
                self._conn.execute,
                """SELECT entry_type, COUNT(*) as cnt, AVG(importance) as avg_imp
                   FROM system_memory GROUP BY entry_type"""
            )
            results = rows.fetchall()
        by_type = {r[0]: {"count": r[1], "avg_importance": round(r[2], 2)} for r in results}
        total = sum(v["count"] for v in by_type.values())
        return {
            "db_path": str(self._db_path),
            "total_entries": total,
            "by_type": by_type,
        }


# ── Utility ───────────────────────────────────────────────────────────────────

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "for",
    "of", "and", "or", "but", "i", "me", "my", "you", "your", "we",
    "do", "did", "was", "are", "be", "been", "has", "have", "had",
    "this", "that", "with", "from", "by", "about", "what", "how",
    "when", "where", "who", "which", "so", "just", "can", "will",
    "not", "no", "as", "if", "then", "than", "up", "out", "get",
})

def _tokenize(text: str) -> List[str]:
    words = re.findall(r"[a-z]{3,}", text.lower())
    return [w for w in words if w not in _STOP_WORDS]


__all__ = ["SystemMemory", "SystemEntry", "SystemEntryType"]
