"""Owner-scoped, revisioned speech choices; included in the host-data checkpoint."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class PreferenceConflict(ValueError):
    pass


class SpeechPreferences:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "speech" / "preferences.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as database:
            version = database.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise ValueError("Speech preferences require a newer application")
            database.execute("CREATE TABLE IF NOT EXISTS preferences (owner TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)")
            database.execute("PRAGMA user_version=1")

    @contextmanager
    def _connection(self):
        database = sqlite3.connect(self.path, timeout=3)
        try:
            database.execute("PRAGMA journal_mode=WAL")
            with database:
                yield database
        finally:
            database.close()

    @staticmethod
    def _row(row) -> dict:
        if row is None:
            return {"revision": 0, "voice_id": "default", "speed": 1.0, "language": "en"}
        payload = json.loads(row[1])
        if not isinstance(payload, dict):
            raise ValueError("Speech preferences are malformed")
        return {**payload, "revision": row[0]}

    def get(self, owner: str) -> dict:
        with self._connection() as database:
            return self._row(database.execute("SELECT revision,payload FROM preferences WHERE owner=?", (owner,)).fetchone())

    def put(self, owner: str, payload: dict, expected_revision: int) -> dict:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        with self._connection() as database:
            database.execute("BEGIN IMMEDIATE")
            row = database.execute("SELECT revision,payload FROM preferences WHERE owner=?", (owner,)).fetchone()
            revision = row[0] if row else 0
            if revision != expected_revision:
                raise PreferenceConflict("Speech preferences changed; reload before saving")
            revision += 1
            database.execute("INSERT INTO preferences(owner,revision,payload) VALUES (?,?,?) ON CONFLICT(owner) DO UPDATE SET revision=excluded.revision,payload=excluded.payload",
                             (owner, revision, encoded))
        return {**payload, "revision": revision}
