"""Durable idempotency for authenticated, client-keyed shared-room chat sends.

The room JSONL remains the message archive. A SQLite ledger reserves each
(room, author, client UUID) before append and publishes completion afterward.
If an append succeeds but the ledger completion is interrupted, retry recovers
its exact message from JSONL instead of appending another copy. This does not
make independent BlackBox or AI callbacks atomic with the room-log commit.
"""
from __future__ import annotations

# Copyright © 2024–2026 Josie Curtsey Cobbley — Rearview Foresight LLC.
# PubCast source; no packaged runtime user data is required by this module.

import hashlib
import json
import logging
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple

logger = logging.getLogger('pubcast.chat_commit_store')


class ChatCommitStore:
    """Cross-process, restart-durable identity-keyed deduplication for HTTP chat."""

    def __init__(self, data_dir: Path):
        self.root = Path(data_dir)
        self.db_path = self.root / 'global' / 'chat_commit_receipts.sqlite3'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # A chat receipt stores the user's exact text. SQLite's ordinary file
        # creation can inherit a world-readable umask (e.g. 0644). Create the
        # database with private permissions before SQLite ever opens it.
        if os.name == 'posix':
            try:
                fd = os.open(self.db_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(fd)
            os.chmod(self.db_path, 0o600)
        # The REST route constructs independent managers in different workers.
        # WAL initialization on a newly created DB can race another worker's
        # schema transaction; only retry the transient SQLite lock case.
        for attempt in range(5):
            try:
                with self._connection() as db:
                    if db.execute('PRAGMA journal_mode').fetchone()[0].lower() != 'wal':
                        db.execute('PRAGMA journal_mode=WAL')
                    self._create_schema(db)
                break
            except sqlite3.OperationalError as exc:
                if 'locked' not in str(exc).lower() or attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))

    @staticmethod
    def _create_schema(db: sqlite3.Connection) -> None:
        db.execute('''CREATE TABLE IF NOT EXISTS chat_commit_receipts (
            room TEXT NOT NULL, author TEXT NOT NULL, client_id TEXT NOT NULL,
            text_hash TEXT NOT NULL, payload_json TEXT NOT NULL,
            attempt_id TEXT NOT NULL, committed INTEGER NOT NULL
                CHECK(committed IN (0, 1)), created_at REAL NOT NULL,
            PRIMARY KEY (room, author, client_id)
        )''')

    @contextmanager
    def _connection(self, *, writing: bool = False) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA busy_timeout=10000')
            db.execute('PRAGMA synchronous=FULL')
            if writing:
                db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def validate_client_id(client_id: str) -> str:
        if not isinstance(client_id, str) or len(client_id) > 36:
            raise ValueError('client_message_id must be a version-4 UUID')
        try:
            parsed = uuid.UUID(client_id)
        except (ValueError, AttributeError):
            raise ValueError('client_message_id must be a version-4 UUID') from None
        if parsed.version != 4 or str(parsed) != client_id.lower():
            raise ValueError('client_message_id must be a canonical version-4 UUID')
        return str(parsed)

    @staticmethod
    def _verify_text(row: sqlite3.Row, text_hash: str) -> None:
        if row['text_hash'] != text_hash:
            raise ValueError('client_message_id was already used for different message text')

    @staticmethod
    def _replay(row: sqlite3.Row) -> Dict[str, Any]:
        return json.loads(row['payload_json'])

    def _recover_appended(self, path: Path, room: str, author: str,
                          client_id: str, reserved_message_id: str) -> Dict[str, Any] | None:
        """Expensive scan is *only* necessary after an interrupted/contended reservation.

        Reject a malformed entry rather than silently append onto a torn log
        or call it a clean, complete archive.
        """
        if not path.exists():
            return None
        with path.open('rb') as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    raise RuntimeError(f'Chat archive contains a damaged line in room {room}; repair before sending') from None
                if not isinstance(entry, dict):
                    raise RuntimeError(f'Chat archive contains a non-object entry in room {room}')
                if (entry.get('room') == room and entry.get('user_id') == author
                        and entry.get('client_message_id') == client_id):
                    if entry.get('message_id') != reserved_message_id:
                        raise RuntimeError('Chat receipt and room archive disagree on message identity')
                    return entry
        return None

    @staticmethod
    def _append_durable(path: Path, entry: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(entry, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
        # A single O_APPEND write avoids interleaving two ordinary messages on
        # supported local filesystems. A short write is a real storage failure:
        # do not write another message onto a potentially damaged line.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            # Pre-existing room logs may have been created by the old 0644
            # append helper. Keep new and subsequently-written archives private.
            if os.name == "posix":
                os.fchmod(fd, 0o600)
            written = os.write(fd, line)
            if written != len(line):
                os.fsync(fd)
                raise OSError(f'Chat append wrote {written} of {len(line)} bytes; archive requires recovery')
            os.fsync(fd)
        finally:
            os.close(fd)
        # SQLite must never publish "committed" while the first creation of
        # this archive could still disappear from an unsynced directory entry.
        if os.name == 'posix':
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)

    def commit(self, room: str, author: str, text: str, client_id: str,
               display_name: str) -> Tuple[Dict[str, Any], bool]:
        client_id = self.validate_client_id(client_id)
        if not isinstance(text, str) or not text.strip() or len(text) > 10000:
            raise ValueError('Message must be 1–10000 characters')
        if (not isinstance(room, str) or
                not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,240}', room)):
            raise ValueError('Invalid chat room identifier')
        if not isinstance(author, str) or not author.strip():
            raise ValueError('Authenticated author is required')
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        attempt_id = uuid.uuid4().hex  # new per execution, not supplied by the client
        message = {
            'message_id': uuid.uuid4().hex, 't': time.time(), 'room': room,
            'user': display_name, 'user_id': author, 'text': text,
            'client_message_id': client_id,
        }
        select = '''SELECT * FROM chat_commit_receipts
                    WHERE room=? AND author=? AND client_id=?'''
        key = (room, author, client_id)
        # Phase 1: persist a stable message identity before touching JSONL.
        # On a crash after append, another attempt sees the old reservation and
        # searches the archive for the original receipt before writing again.
        with self._connection(writing=True) as db:
            row = db.execute(select, key).fetchone()
            if row:
                self._verify_text(row, text_hash)
                if row['committed']:
                    return self._replay(row), True
            else:
                db.execute('''INSERT INTO chat_commit_receipts
                    (room, author, client_id, text_hash, payload_json,
                     attempt_id, committed, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?)''',
                    (*key, text_hash, json.dumps(message, ensure_ascii=False),
                     attempt_id, time.time()))

        # Phase 2: exclusive DB transaction serializes all attempts *for this
        # key* across instances/workers. A new owner scans only when a prior
        # attempt could have appended before crashing or losing its receipt.
        path = self.root / 'logs' / f'{room}.jsonl'
        with self._connection(writing=True) as db:
            row = db.execute(select, key).fetchone()
            if row is None:
                raise RuntimeError('Chat reservation disappeared before commit')
            self._verify_text(row, text_hash)
            if row['committed']:
                return self._replay(row), True
            if row['attempt_id'] != attempt_id:
                recovered = self._recover_appended(
                    path, room, author, client_id, self._replay(row)['message_id'])
                if recovered is not None:
                    db.execute('''UPDATE chat_commit_receipts SET committed=1, payload_json=?
                                  WHERE room=? AND author=? AND client_id=?''',
                               (json.dumps(recovered, ensure_ascii=False), *key))
                    return recovered, True
                db.execute('''UPDATE chat_commit_receipts SET attempt_id=?
                              WHERE room=? AND author=? AND client_id=?''', (attempt_id, *key))
            # Reuse the originally reserved message ID even if the first
            # attempt ended before the append; never mint a new receipt here.
            reserved = self._replay(row)
            self._append_durable(path, reserved)
            db.execute('''UPDATE chat_commit_receipts SET committed=1
                          WHERE room=? AND author=? AND client_id=?''', key)
            return reserved, False
