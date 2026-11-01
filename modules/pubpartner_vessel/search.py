"""Derived full-text indexes and bounded recall; never a storage-retention policy."""
from __future__ import annotations

import sqlite3
import time
import threading
from contextlib import contextmanager

from .store import VesselStore


class SearchBudgetExceeded(RuntimeError):
    pass


class MemorySearch:
    CANDIDATES = 256
    MAX_QUERY_TERMS = 32
    MAX_SQL_STEPS = 2_000_000
    MAX_SECONDS = 0.5

    def __init__(self, store: VesselStore):
        self.store = store
        self._local = threading.local()
        with store.reader() as connection:
            self.available = self._ready(connection)
        if not self.available and not store.read_only:
            self._install()
            self.available = True

    @staticmethod
    def _ready(connection):
        required = {'memory_search_ready_v1'}
        for kind in ('claims', 'events'):
            required.add(f'memory_{kind}_fts')
            required.update(f'memory_{kind}_search_{action}' for action in ('insert', 'update', 'delete'))
        actual = {row[0] for row in connection.execute('SELECT name FROM sqlite_master')}
        return required <= actual

    @property
    def status(self):
        if not hasattr(self._local, "status"):
            self._local.status = {}
        return self._local.status

    def _install(self):
        # Additive derived indexes: original signed records and schema version
        # remain unchanged. Creation/backfill is atomic and never runs per turn.
        with self.store.transaction() as connection:
            if self._ready(connection):
                return
            # Rebuild incomplete derived indexes, never the source records.
            for kind in ('events', 'claims'):
                for action in ('insert', 'update', 'delete'):
                    connection.execute(f'DROP TRIGGER IF EXISTS memory_{kind}_search_{action}')
                connection.execute(f'DROP TABLE IF EXISTS memory_{kind}_fts')
            connection.execute('DROP TABLE IF EXISTS memory_search_ready_v1')
            for kind, columns in (("events", "content"), ("claims", "normalized_text, predicate")):
                table = 'memory_' + kind
                index = table + '_fts'
                fields = columns.split(', ')
                new = ', '.join('new.' + field for field in fields)
                old = ', '.join('old.' + field for field in fields)
                connection.execute(f"CREATE VIRTUAL TABLE {index} USING fts5({columns}, content='{table}', content_rowid='rowid')")
                connection.execute(f"CREATE TRIGGER {table}_search_insert AFTER INSERT ON {table} BEGIN INSERT INTO {index}(rowid, {columns}) VALUES(new.rowid, {new}); END")
                connection.execute(f"CREATE TRIGGER {table}_search_delete AFTER DELETE ON {table} BEGIN INSERT INTO {index}({index}, rowid, {columns}) VALUES('delete', old.rowid, {old}); END")
                connection.execute(f"CREATE TRIGGER {table}_search_update AFTER UPDATE ON {table} BEGIN INSERT INTO {index}({index}, rowid, {columns}) VALUES('delete', old.rowid, {old}); INSERT INTO {index}(rowid, {columns}) VALUES(new.rowid, {new}); END")
                connection.execute(f"INSERT INTO {index}({index}) VALUES('rebuild')")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_memory_events_source ON memory_events(subject_id, source_kind, source_ref, source_hash)")
            connection.execute("CREATE TABLE memory_search_ready_v1 (ready INTEGER NOT NULL)")
            connection.execute("INSERT INTO memory_search_ready_v1 VALUES (1)")

    @contextmanager
    def budget(self, connection):
        started = time.monotonic()
        steps = 0
        def exhausted():
            nonlocal steps
            steps += 1000
            return int(steps > self.MAX_SQL_STEPS or time.monotonic() - started > self.MAX_SECONDS)
        connection.set_progress_handler(exhausted, 1000)
        try:
            yield
        except sqlite3.OperationalError as exc:
            if 'interrupted' in str(exc).lower():
                raise SearchBudgetExceeded('Memory search budget exhausted; recall is incomplete.') from exc
            raise
        finally:
            connection.set_progress_handler(None, 0)

    def candidates(self, connection, *, kind, subject_id, viewer_id, audience,
                   room_id, project_id, session_id, tokens, always_types=(),
                   include_nonproactive=False):
        if kind not in {'claims', 'events'}:
            raise ValueError('unknown memory search kind')
        if not self.available:
            self.status[kind] = {'status': 'index_unavailable', 'complete': False}
            return []
        terms = sorted(tokens)
        query_limited = len(terms) > self.MAX_QUERY_TERMS
        terms = terms[:self.MAX_QUERY_TERMS]
        # Quoted FTS terms cannot become query operators or SQL syntax.
        query = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms)
        table = 'memory_' + kind
        index = table + '_fts'
        result = []
        eligible = (" AND m.status IN ('confirmed','corroborated')"
                    " AND (m.expires_at IS NULL OR m.expires_at > ?)"
                    if kind == "claims" else "")
        eligibility_args = (time.time(),) if kind == "claims" else ()
        # Eligibility must precede LIMIT. Otherwise private, wrong-project or
        # prohibited rows can consume every candidate slot before filtering.
        scope = ("m.scope" if kind == "claims" else
                 "CASE WHEN m.visibility='room_scoped' THEN 'room:' || m.room_id ELSE 'global' END")
        eligible += (" AND (m.visibility='public' OR "
                     "(m.visibility IN ('private_owner','private_relationship') AND ?=1) OR "
                     f"(m.visibility='room_scoped' AND {scope}=? AND ?<>''))")
        eligibility_args += (int(audience == 'private' and bool(viewer_id) and viewer_id == subject_id),
                             'room:' + room_id, room_id)
        scopes = ['', 'global']
        scopes += ['room:' + room_id] if room_id else []
        scopes += ['project:' + project_id] if project_id else []
        scopes += ['session:' + session_id] if session_id else []
        eligible += f" AND {scope} IN ({','.join('?' for _ in scopes)})"
        eligibility_args += tuple(scopes)
        if kind == 'claims' and not include_nonproactive:
            eligible += ' AND m.proactive_use=1'
        try:
            with self.budget(connection):
                if query:
                    result = connection.execute(
                        f"SELECT m.* FROM {index} JOIN {table} m ON m.rowid={index}.rowid "
                        f"WHERE {index} MATCH ? AND m.subject_id=?" + eligible + " ORDER BY rank LIMIT ?",
                        (query, subject_id, *eligibility_args, self.CANDIDATES + 1),
                    ).fetchall()
                # Standing instructions can be relevant without lexical overlap.
                if always_types:
                    marks = ','.join('?' for _ in always_types)
                    standing = connection.execute(
                        f"SELECT m.* FROM {table} m WHERE subject_id=? AND scope='global' "
                        f"AND claim_type IN ({marks})" + eligible + " ORDER BY updated_at DESC LIMIT ?",
                        (subject_id, *sorted(always_types), *eligibility_args, self.CANDIDATES + 1),
                    ).fetchall()
                    seen = {row['claim_id'] for row in standing}
                    result = list(standing) + [row for row in result if row['claim_id'] not in seen]
        except SearchBudgetExceeded:
            self.status[kind] = {'status': 'budget_exhausted', 'complete': False}
            return []
        limited = len(result) > self.CANDIDATES or query_limited
        self.status[kind] = {'status': 'bounded' if limited else 'ok', 'complete': not limited,
                             'candidates': min(len(result), self.CANDIDATES), 'candidate_limit': self.CANDIDATES}
        return result[:self.CANDIDATES]
