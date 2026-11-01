"""Durable outcomes for targeted invitations and host-required generated turns."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path


class TurnRequests:
    def __init__(self, root: Path):
        self.path = Path(root) / 'turn_requests.sqlite3'
        with closing(self._connect()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            for request_id, body in db.execute('SELECT id,body FROM requests').fetchall():
                item = json.loads(body)
                if item['state'] in {'requested', 'considering', 'accepted', 'speaking'}:
                    item.update(state='interrupted', error='Program restarted during turn', updated_at=time.time())
                    db.execute('UPDATE requests SET body=? WHERE id=?', (json.dumps(item), request_id))

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=8)
        db.execute('PRAGMA synchronous=FULL')
        return db

    def create(self, *, bot_id, room, actor, required):
        item = {'request_id': uuid.uuid4().hex, 'bot_id': bot_id, 'room': room,
                'actor': actor, 'required': required, 'state': 'requested',
                'created_at': time.time(), 'updated_at': time.time()}
        with closing(self._connect()) as db, db:
            db.execute('INSERT INTO requests VALUES (?,?)', (item['request_id'], json.dumps(item)))
        return item

    def update(self, item, state, **details):
        item = {**item, **details, 'state': state, 'updated_at': time.time()}
        with closing(self._connect()) as db, db:
            db.execute('UPDATE requests SET body=? WHERE id=?', (json.dumps(item), item['request_id']))
        return item

    def get(self, request_id):
        with closing(self._connect()) as db:
            row = db.execute('SELECT body FROM requests WHERE id=?', (request_id,)).fetchone()
        return json.loads(row[0]) if row else None
