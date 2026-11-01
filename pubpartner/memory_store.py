"""
Persistent memory store for a cartridge.

Memories are typed (episodic / semantic / procedural / emotional / project /
personal) and stored in SQLite so a cartridge's memory survives between
sessions and processes. Retrieval ranks candidates by a blend of:

  - lexical relevance to the query (TF-IDF cosine similarity)
  - recency (exponential decay by age)
  - stated importance (0.0-1.0, set at write time)

This is a real, working retrieval algorithm — not a placeholder. It doesn't
require any external embedding API, so it costs nothing to run and works
offline.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MEMORY_TYPES = ("episodic", "semantic", "procedural", "emotional", "project", "personal")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 0.5,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
"""


class MemoryStoreError(ValueError):
    """Raised for invalid memory operations (bad type, bad importance, etc)."""


@dataclass(frozen=True)
class Memory:
    id: int
    text: str
    memory_type: str
    importance: float
    created_at: str  # ISO 8601, UTC

    def age_days(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        created = datetime.fromisoformat(self.created_at)
        return max(0.0, (now - created).total_seconds() / 86400.0)


@dataclass(frozen=True)
class ScoredMemory:
    memory: Memory
    score: float
    relevance: float
    recency: float


class MemoryStore:
    """Owns one SQLite connection for one cartridge's memories.db."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def add(
        self,
        text: str,
        memory_type: str,
        importance: float = 0.5,
        created_at: str | None = None,
    ) -> int:
        if not text.strip():
            raise MemoryStoreError("Memory text cannot be empty")
        if memory_type not in MEMORY_TYPES:
            raise MemoryStoreError(
                f"Invalid memory_type '{memory_type}'. Must be one of: {', '.join(MEMORY_TYPES)}"
            )
        if not (0.0 <= importance <= 1.0):
            raise MemoryStoreError(f"importance must be between 0.0 and 1.0, got {importance}")
        created_at = created_at or datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO memories (text, memory_type, importance, created_at) VALUES (?, ?, ?, ?)",
            (text, memory_type, importance, created_at),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def seed_from_jsonl(self, path: str | Path) -> int:
        """Bulk-load memories from a JSONL file. Each line must be a JSON
        object with at least `text` and `memory_type`; `importance` and
        `created_at` are optional. Returns the number of memories added.
        Raises MemoryStoreError with the offending line number on bad input."""
        path = Path(path)
        added = 0
        with path.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise MemoryStoreError(f"Invalid JSON on line {line_no} of {path.name}: {exc}") from exc
                if "text" not in record or "memory_type" not in record:
                    raise MemoryStoreError(
                        f"Line {line_no} of {path.name} missing required 'text' or 'memory_type'"
                    )
                self.add(
                    text=record["text"],
                    memory_type=record["memory_type"],
                    importance=float(record.get("importance", 0.5)),
                    created_at=record.get("created_at"),
                )
                added += 1
        return added

    def all(self, memory_type: str | None = None) -> list[Memory]:
        if memory_type is not None and memory_type not in MEMORY_TYPES:
            raise MemoryStoreError(
                f"Invalid memory_type '{memory_type}'. Must be one of: {', '.join(MEMORY_TYPES)}"
            )
        if memory_type:
            rows = self._conn.execute(
                "SELECT * FROM memories WHERE memory_type = ? ORDER BY id", (memory_type,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM memories ORDER BY id").fetchall()
        return [
            Memory(
                id=r["id"],
                text=r["text"],
                memory_type=r["memory_type"],
                importance=r["importance"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM memories").fetchone()
        return int(row["n"])

    def query(
        self,
        text: str,
        top_k: int = 5,
        memory_type: str | None = None,
        recency_half_life_days: float = 14.0,
        relevance_weight: float = 0.55,
        recency_weight: float = 0.20,
        importance_weight: float = 0.25,
    ) -> list[ScoredMemory]:
        """Rank stored memories against `text` by a weighted blend of TF-IDF
        relevance, recency decay, and stated importance. Returns the top_k
        highest-scoring memories, best first. Returns [] if the store is
        empty for the given filter — never raises for an empty corpus."""
        candidates = self.all(memory_type=memory_type)
        if not candidates:
            return []

        corpus = [m.text for m in candidates] + [text]
        vectorizer = TfidfVectorizer(stop_words="english")
        try:
            tfidf = vectorizer.fit_transform(corpus)
        except ValueError:
            # Empty vocabulary (e.g. query and all memories are pure stopwords/punctuation)
            relevances = [0.0] * len(candidates)
        else:
            query_vec = tfidf[-1]
            memory_vecs = tfidf[:-1]
            relevances = cosine_similarity(query_vec, memory_vecs).flatten().tolist()

        now = datetime.now(timezone.utc)
        scored: list[ScoredMemory] = []
        for memory, relevance in zip(candidates, relevances):
            age = memory.age_days(now)
            recency = math.exp(-math.log(2) * age / recency_half_life_days)
            score = (
                relevance_weight * relevance
                + recency_weight * recency
                + importance_weight * memory.importance
            )
            scored.append(ScoredMemory(memory=memory, score=score, relevance=relevance, recency=recency))

        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]
