"""Durable delivery of canonical room chat to the independent Blackbox witness.

Room JSONL is the source of truth. SQLite coordinates delivery, not chat sends.
Committed attempt reservations survive a process dying after BBX append but
before acknowledgement; the next worker verifies that ledger before retrying.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import uuid
from pathlib import Path

from blackbox_event_language.schema import decode_record
from blackbox_recorder import AppendOnlyBlackBoxRecorder
from .chat_commit_store import ChatCommitStore


def canonical_chat(message):
    payload = {key:message[key] for key in ('message_id','room','user_id','text','t')}
    if not all(isinstance(payload[k], str) and payload[k] for k in ('message_id','room','user_id')):
        raise ValueError('Chat recovery requires stable message, room and sender identities')
    if not isinstance(payload['text'], str):
        raise ValueError('Chat recovery requires exact text')
    if not isinstance(payload['t'], (int,float)) or not math.isfinite(payload['t']):
        raise ValueError('Chat recovery requires a finite original timestamp')
    wire = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return payload, wire, hashlib.sha256(wire.encode('utf-8')).hexdigest()


class ChatWitnessOutbox:
    def __init__(self, witness):
        self.witness = witness
        self.root = witness.data_dir
        # Share the existing private, FULL-synchronous SQLite connection policy.
        self.store = ChatCommitStore(self.root)
        with self.store._connection(writing=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS blackbox_chat_outbox (
                message_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0 CHECK(delivered IN (0,1)),
                attempt TEXT, ledger_sid TEXT, record_hash TEXT,
                queued_at REAL NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS blackbox_chat_pending ON blackbox_chat_outbox(delivered, queued_at)')
        self.initialized = False
        self.cursors = {}
        self.unidentified = 0

    def _receipts(self, path):
        if path.is_symlink():raise ValueError('Ledger symlink refused during recovery')
        recorder = AppendOnlyBlackBoxRecorder(path, path.stem)
        verification = recorder.verify()
        if not verification.ok:
            raise OSError('Chat replay blocked by an unverifiable ledger: '+path.name)
        # A prior fsync/ack failure may have left complete bytes. Make them
        # durable before promoting the recovered delivery receipt to success.
        with path.open('r+b') as source:
            os.fsync(source.fileno())
        with path.open(encoding='utf-8') as source:
            for line in source:
                if not line.strip():continue
                record = decode_record(line)
                data = record['payload']
                if data.get('event_type')!='chat.message' or not data.get('message_id'):
                    continue
                details = json.loads(data['data_json']) if 'data_json' in data else dict(data)
                if not isinstance(details, dict):raise ValueError('Malformed chat receipt')
                details['user_id'] = record['actor']
                if isinstance(details.get('t'), str):details['t']=float(details['t'])
                payload, wire, digest = canonical_chat(details)
                yield payload,wire,digest,record['hash']

    def bootstrap(self):
        if self.initialized:return
        # One transaction excludes all cooperating delivery writers while
        # reconciling their journals, including receipts predating this queue.
        with self.store._connection(writing=True) as db:
            seen = set()
            for path in sorted((self.root/'blackbox').glob('*.bbx')):
                for payload, wire, digest, record_hash in self._receipts(path):
                    identity = payload['message_id']
                    if identity in seen:raise ValueError('Duplicate chat witness identity; replay stopped')
                    seen.add(identity)
                    row = db.execute('SELECT fingerprint FROM blackbox_chat_outbox WHERE message_id=?', (identity,)).fetchone()
                    if row and row['fingerprint']!=digest:
                        raise ValueError('Chat witness disagrees with queued original')
                    db.execute('''INSERT INTO blackbox_chat_outbox
                        (message_id,fingerprint,payload_json,delivered,ledger_sid,record_hash,queued_at)
                        VALUES (?,?,?,1,?,?,?) ON CONFLICT(message_id) DO UPDATE SET
                        delivered=1,ledger_sid=excluded.ledger_sid,record_hash=excluded.record_hash''',
                        (identity,digest,wire,path.stem,record_hash,time.time()))
            delivered = {row[0] for row in db.execute('SELECT message_id FROM blackbox_chat_outbox WHERE delivered=1')}
            if delivered-seen:
                raise OSError('Previously acknowledged chat witness is unavailable; replay stopped')
        self.initialized = True

    def enqueue(self, message):
        payload, wire, digest = canonical_chat(message)
        with self.store._connection(writing=True) as db:
            row = db.execute('SELECT fingerprint FROM blackbox_chat_outbox WHERE message_id=?',
                             (payload['message_id'],)).fetchone()
            if row and row['fingerprint']!=digest:
                raise ValueError('Message identity was reused with different canonical contents')
            db.execute('''INSERT OR IGNORE INTO blackbox_chat_outbox
                (message_id,fingerprint,payload_json,queued_at) VALUES (?,?,?,?)''',
                (payload['message_id'],digest,wire,time.time()))
        return payload['message_id']

    def deliver(self, message_id, *, replay):
        self.bootstrap()
        for _ in range(5):
            attempt = uuid.uuid4().hex
            with self.store._connection(writing=True) as db:
                row = db.execute('SELECT * FROM blackbox_chat_outbox WHERE message_id=?',(message_id,)).fetchone()
                if row is None:raise ValueError('Unknown queued chat identity')
                if row['delivered']:return True
                if row['ledger_sid']:
                    sid = row['ledger_sid']
                    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}', sid):
                        raise ValueError('Unsafe delivery ledger reference')
                    matches = [r for r in self._receipts(self.root/'blackbox'/(sid+'.bbx'))
                               if r[0]['message_id']==message_id]
                    if len(matches)>1:raise ValueError('Duplicate delivery receipt; replay stopped')
                    if matches:
                        if matches[0][2]!=row['fingerprint']:raise ValueError('Ambiguous receipt conflicts with original')
                        db.execute('UPDATE blackbox_chat_outbox SET delivered=1,record_hash=? WHERE message_id=?',
                                   (matches[0][3],message_id))
                        return True
                # Persist where this attempt could write BEFORE touching BBX.
                db.execute('UPDATE blackbox_chat_outbox SET attempt=?,ledger_sid=? WHERE message_id=?',
                           (attempt,self.witness.session_id,message_id))
            with self.store._connection(writing=True) as db:
                row = db.execute('SELECT * FROM blackbox_chat_outbox WHERE message_id=?',(message_id,)).fetchone()
                if row['delivered']:return True
                if row['attempt']!=attempt:continue  # A worker took over; verify its attempt before retrying.
                payload = json.loads(row['payload_json'])
                result = self.witness.record_event('chat.message', source='chat', actor=payload['user_id'],
                    data={k:payload[k] for k in ('room','text','t','message_id')} | {
                        'delivery_mode':'replay' if replay else 'live'})
                if not result:raise OSError('Chat witness not acknowledged; durable delivery remains pending')
                record = decode_record(result)
                db.execute('UPDATE blackbox_chat_outbox SET delivered=1,record_hash=? WHERE message_id=?',
                           (record['hash'],message_id))
                return True
        return False

    def scan_archives(self):
        unidentified = 0
        errors = []
        for path in sorted((self.root/'logs').glob('*.jsonl')):
            try:
                if path.is_symlink():raise ValueError('Chat archive symlink refused')
                with path.open('rb') as source:
                    stat = os.fstat(source.fileno())
                    identity = (stat.st_dev,stat.st_ino)
                    previous, offset = self.cursors.get(path.name,(identity,0))
                    if previous!=identity or stat.st_size<offset:
                        raise ValueError('Chat archive changed outside its append writer')
                    source.seek(offset)
                    while True:
                        line=source.readline()
                        if not line:break
                        if not line.endswith(b'\n'):raise ValueError('Incomplete chat archive line retained')
                        if line.strip():
                            payload=json.loads(line)
                            if not isinstance(payload,dict):raise ValueError('Malformed chat archive entry')
                            if payload.get('room')!=path.stem:raise ValueError('Chat archive room mismatch')
                            if not payload.get('message_id'):
                                unidentified += 1
                            else:
                                self.enqueue(payload)
                        self.cursors[path.name]=(identity,source.tell())
            except (OSError,ValueError,KeyError,TypeError) as error:
                errors.append({'file':path.name,'error_type':type(error).__name__})
        self.unidentified += unidentified
        return self.unidentified, errors

    def pending(self):
        with self.store._connection() as db:
            return db.execute('SELECT count(*) FROM blackbox_chat_outbox WHERE delivered=0').fetchone()[0]

    def recover(self, limit=64):
        self.bootstrap()
        unidentified, errors = self.scan_archives()
        with self.store._connection() as db:
            identities=[r[0] for r in db.execute('''SELECT message_id FROM blackbox_chat_outbox
                WHERE delivered=0 ORDER BY queued_at,message_id LIMIT ?''',(limit,))]
        replayed=0
        for identity in identities:
            if not self.deliver(identity,replay=True):break
            replayed += 1
        pending = self.pending()
        return {'state':'blocked' if errors or unidentified else ('backlog' if pending else 'running'), 'pending':pending,
                'replayed':replayed,'unidentified':unidentified,'archive_errors':errors}
