"""One canonical character provider with private durable direct-chat transcripts.

Shared PubChat participation belongs to BotManager/Hub. Direct Foresight chat
MUST NOT read arbitrary Hub room logs or put personal dialogue into publicly
joinable room names. Private transcripts live in a separate SQLite database.
"""
from __future__ import annotations

import asyncio
from contextlib import closing
import hashlib
import json
import logging
import weakref
import os
from pathlib import Path
import sqlite3
import time

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# In-process generation ordering: never interleave two model turns in the same
# owner/character/conversation stream. Multi-worker scheduling needs a separate
# durable lease; do not claim this lock handles multiple server processes.
_active_turn_locks: weakref.WeakValueDictionary = weakref.WeakValueDictionary()


def _turn_lock(data_dir: Path, thread_id: str) -> asyncio.Lock:
    key = str(Path(data_dir).resolve()) + ':' + thread_id
    lock = _active_turn_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _active_turn_locks[key] = lock
    return lock



def _private_thread(user_id: str, bot_id: str, label: str) -> str:
    identity = json.dumps([user_id, bot_id, label], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(identity.encode('utf-8')).hexdigest()


class CharacterTranscriptStore:
    """Owner/character scoped chat archive, not served by public Hub room APIs.

    SQLite transactions are safe across concurrent requests and processes; the
    store is attached to the host's authoritative data directory, not the ZIP.
    """
    def __init__(self, data_dir: str | Path):
        self.root = Path(data_dir) / 'private_character_transcripts'
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name == 'posix':
            self.root.chmod(0o700)
        self.path = self.root / 'conversations.sqlite3'

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=8)
        conn.execute('PRAGMA busy_timeout = 8000')
        conn.execute("""CREATE TABLE IF NOT EXISTS messages
                     (seq INTEGER PRIMARY KEY AUTOINCREMENT,
                      thread_id TEXT NOT NULL, user TEXT NOT NULL,
                      text TEXT NOT NULL, ts REAL NOT NULL)""")
        conn.execute('CREATE INDEX IF NOT EXISTS idx_character_history ON messages(thread_id, seq)')
        conn.execute("""CREATE TABLE IF NOT EXISTS threads
                     (thread_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                      bot_id TEXT NOT NULL, label TEXT NOT NULL)""")
        conn.execute('CREATE INDEX IF NOT EXISTS idx_character_threads_owner ON threads(owner_id)')
        if os.name == 'posix':
            self.path.chmod(0o600)
        return conn

    def register_thread(self, owner_id: str, bot_id: str, label: str):
        thread = _private_thread(owner_id, bot_id, label)
        with closing(self._connect()) as conn:
            with conn:
                conn.execute('INSERT OR IGNORE INTO threads(thread_id,owner_id,bot_id,label) '
                             'VALUES(?,?,?,?)', (thread, owner_id, bot_id, label))

    def owner_export(self, owner_id: str) -> dict:
        """Export only threads bound to this verified owner, in stable order.

        Older installs did not retain thread metadata. Previously opened threads
        acquire metadata on their next authenticated read/write; unknown custom
        legacy room labels cannot be enumerated from one-way hashes.
        """
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT thread_id,bot_id,label FROM threads '
                                'WHERE owner_id=? ORDER BY bot_id,label', (owner_id,)).fetchall()
            threads = []
            for row in rows:
                messages = conn.execute('SELECT user,text,ts FROM messages WHERE thread_id=? '
                                        'ORDER BY seq', (row['thread_id'],)).fetchall()
                threads.append({'bot_id': row['bot_id'], 'conversation_id': row['label'],
                                'messages': [dict(m) for m in messages]})
        return {'schema': 'pubcast.private-characters.export.v1', 'owner_id': owner_id,
                'threads': threads}

    def append(self, thread: str, speaker: str, text: str):
        with closing(self._connect()) as conn:
            with conn:
                conn.execute('INSERT INTO messages(thread_id,user,text,ts) VALUES (?,?,?,?)',
                             (thread, speaker, text, time.time()))

    def recent(self, thread: str, limit: int = 30) -> list[dict]:
        limit = max(1, min(int(limit), 100))
        with closing(self._connect()) as conn:
            rows = conn.execute('SELECT user,text,ts FROM messages WHERE thread_id=? '
                                'ORDER BY seq DESC LIMIT ?', (thread, limit)).fetchall()
        return [{'user': who, 'text': text, 't': ts} for who, text, ts in reversed(rows)]


def _validated(manager, hub, *, bot_id: str, user_id: str, room_id: str):
    if manager is None:
        raise HTTPException(503, 'BotManager not initialized')
    if hub is None or not getattr(hub, 'data_dir', None):
        raise HTTPException(503, 'Persistent private conversation storage unavailable')
    for name, value in [('character_id', bot_id), ('user_id', user_id), ('conversation_id', room_id)]:
        if not isinstance(value, str) or not value or len(value) > 128:
            raise HTTPException(400, f'Invalid {name}')
    cfg = manager.get_config(bot_id)
    if cfg is None:
        raise HTTPException(404, f"Bot '{bot_id}' not found")
    store = CharacterTranscriptStore(hub.data_dir)
    # Records identity metadata separately from messages for safe Save All.
    try:
        store.register_thread(user_id, bot_id, room_id)
    except (OSError, sqlite3.Error) as exc:
        logger.exception('Private character thread registration failed')
        raise HTTPException(503, 'Character archive unavailable') from exc
    return cfg, store, _private_thread(user_id, bot_id, room_id)


async def character_history(manager, hub, *, bot_id: str, room_id: str, user_id: str, limit: int = 30):
    _, store, thread = _validated(manager, hub, bot_id=bot_id, room_id=room_id, user_id=user_id)
    try:
        return await asyncio.to_thread(store.recent, thread, limit)
    except (OSError, sqlite3.Error) as exc:
        logger.exception('Character history retrieval failed')
        raise HTTPException(503, 'Character history unavailable') from exc


def _witness(hub, thread: str, speaker: str, text: str) -> None:
    """Attempt owner-only Blackbox witness without making provider success depend on it."""
    witness = getattr(hub, 'blackbox_witness', None)
    if witness is None:
        return
    try:
        witness.record_event('chat.message', source='character_private', actor=speaker,
                             data={'room': 'private_character_' + thread, 'text': text})
    except Exception:
        logger.exception('Blackbox witness unavailable for direct character conversation')


async def speak_to_character(manager, hub, *, bot_id: str, message: str,
                             room_id: str, user_id: str) -> dict:
    cfg, store, thread = _validated(manager, hub, bot_id=bot_id,
                                    user_id=user_id, room_id=room_id)
    async with _turn_lock(hub.data_dir, thread):
        return await _speak_serialized(manager, hub, cfg=cfg, store=store,
                                      thread=thread, bot_id=bot_id, message=message,
                                      room_id=room_id, user_id=user_id)


async def _speak_serialized(manager, hub, *, cfg, store, thread, bot_id, message,
                            room_id, user_id) -> dict:
    if not isinstance(message, str) or not message.strip() or len(message) > 10000:
        raise HTTPException(400, 'Message required (maximum 10000 characters)')
    clean = message.strip()
    try:
        await asyncio.to_thread(store.append, thread, user_id, clean)
        _witness(hub, thread, user_id, clean)
        history = await asyncio.to_thread(store.recent, thread, cfg.max_history)
    except (OSError, sqlite3.Error) as exc:
        logger.exception('Unable to persist direct character conversation')
        raise HTTPException(503, 'Character conversation storage unavailable') from exc
    from .bots import REPLY_WAS_OFFLINE
    REPLY_WAS_OFFLINE.set(False)
    try:
        keeper = getattr(manager, '_cricket_keeper', None)
        cricket = await keeper.get('private_' + thread) if keeper else None
        if cricket is not None:
            history = await cricket.enrich_context(clean, history)
        reply = await manager._call_provider(cfg, manager._build_prompt(cfg, history))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception('Character reply failed for %s', bot_id)
        raise HTTPException(500, 'Character provider failed') from exc
    if not isinstance(reply, str) or not reply.strip():
        raise HTTPException(502, 'Character returned an empty reply')
    result = reply.strip()
    try:
        await asyncio.to_thread(store.append, thread, cfg.name, result)
        _witness(hub, thread, manager.bot_user_id(bot_id), result)
    except (OSError, sqlite3.Error) as exc:
        logger.exception('Failed to archive generated character reply')
        raise HTTPException(503, 'Character reply generated but storage unavailable') from exc
    if cricket is not None:
        try:
            await cricket.remember(content=clean, source='conversation', importance=4)
            await cricket.remember(content=result, source='system', importance=5)
        except Exception:
            logger.exception('Private Cricket memory unavailable; durable transcript retained')
    provider_label = ('offline_character' if (
                          REPLY_WAS_OFFLINE.get() or (bot_id == 'pete' and (getattr(cfg, 'settings', None) or {}).get('offline_character')))
                      else cfg.provider.value)
    return {'bot_id': bot_id, 'bot_name': cfg.name, 'provider': provider_label,
            'model': cfg.model, 'room_id': room_id, 'reply': result}
