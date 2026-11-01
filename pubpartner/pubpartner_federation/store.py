from __future__ import annotations
import json, sqlite3, threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
from .protocol import Change, Entity, VectorClock, canonical_json
class SyncStore:
    def __init__(self,path:str|Path):
        self.path=str(path); self.lock=threading.RLock(); self.db=sqlite3.connect(self.path,check_same_thread=False); self.db.row_factory=sqlite3.Row; self._transaction_depth=0; self._init()
    def _commit(self):
        if self._transaction_depth == 0:
            self.db.commit()

    @contextmanager
    def transaction(self):
        """Atomically persist a change batch and its causal acknowledgments."""
        with self.lock:
            outermost = self._transaction_depth == 0
            if outermost:
                self.db.execute("BEGIN IMMEDIATE")
            else:
                savepoint = f"pubpartner_nested_{self._transaction_depth}"
                self.db.execute(f"SAVEPOINT {savepoint}")
            self._transaction_depth += 1
            try:
                yield
                if outermost:
                    self.db.commit()
                else:
                    self.db.execute(f"RELEASE SAVEPOINT {savepoint}")
            except BaseException:
                if outermost:
                    self.db.rollback()
                else:
                    self.db.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    self.db.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            finally:
                self._transaction_depth -= 1

    def _init(self):
        with self.lock:
            self.db.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS entities(entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,payload TEXT NOT NULL,version TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(entity_type,entity_id));
            CREATE TABLE IF NOT EXISTS field_versions(entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,field_name TEXT NOT NULL,version TEXT NOT NULL,PRIMARY KEY(entity_type,entity_id,field_name));
            CREATE TABLE IF NOT EXISTS changes(change_id TEXT PRIMARY KEY,node_id TEXT NOT NULL,entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,fields TEXT NOT NULL,version TEXT NOT NULL,base_version TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS applied_changes(change_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS conflicts(conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,local_payload TEXT NOT NULL,remote_payload TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);'''); self._commit()
    def load_clock(self)->VectorClock:
        """Recover the node's causal frontier from disk.

        Without this the engine started every process with an empty clock, so a
        restarted node advertised a cursor claiming it had seen nothing. Peers
        then resent their entire change log, and the node's own history looked
        as though it had reset — which is exactly what section 24 forbids.
        """
        with self.lock:
            r=self.db.execute('SELECT value FROM meta WHERE key=?',('clock',)).fetchone()
            return VectorClock.from_dict(json.loads(r['value'])) if r else VectorClock()
    def save_clock(self,clock:VectorClock)->None:
        with self.lock:
            self.db.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('clock',canonical_json(clock.to_dict()))); self._commit()
    def close(self):
        with self.lock: self.db.close()
    def get(self,entity_type,entity_id)->Optional[Entity]:
        with self.lock:
            r=self.db.execute('SELECT payload,version,deleted FROM entities WHERE entity_type=? AND entity_id=?',(entity_type,entity_id)).fetchone()
            if not r:return None
            return Entity(entity_type,entity_id,json.loads(r['payload']),VectorClock.from_dict(json.loads(r['version'])),bool(r['deleted']))
    def put(self,e:Entity,changed_fields=None):
        with self.lock:
            self.db.execute('''INSERT INTO entities(entity_type,entity_id,payload,version,deleted) VALUES(?,?,?,?,?) ON CONFLICT(entity_type,entity_id) DO UPDATE SET payload=excluded.payload,version=excluded.version,deleted=excluded.deleted''',(e.entity_type,e.entity_id,canonical_json(e.fields),canonical_json(e.version.to_dict()),int(e.deleted)))
            if changed_fields is not None:
                for field in changed_fields:self.db.execute('''INSERT INTO field_versions(entity_type,entity_id,field_name,version) VALUES(?,?,?,?) ON CONFLICT(entity_type,entity_id,field_name) DO UPDATE SET version=excluded.version''',(e.entity_type,e.entity_id,field,canonical_json(e.version.to_dict())))
            self._commit()
    def field_version(self,entity_type,entity_id,field_name):
        with self.lock:
            r=self.db.execute('SELECT version FROM field_versions WHERE entity_type=? AND entity_id=? AND field_name=?',(entity_type,entity_id,field_name)).fetchone()
            return VectorClock.from_dict(json.loads(r['version'])) if r else VectorClock()
    def record_change(self,c):
        with self.lock:
            self.db.execute('''INSERT OR IGNORE INTO changes(change_id,node_id,entity_type,entity_id,fields,version,base_version,deleted) VALUES(?,?,?,?,?,?,?,?)''',(c.change_id,c.node_id,c.entity_type,c.entity_id,canonical_json(c.fields),canonical_json(c.version.to_dict()),canonical_json(c.base_version.to_dict()),int(c.deleted))); self._commit()
    def has_change(self,change_id):
        with self.lock:return self.db.execute('SELECT 1 FROM applied_changes WHERE change_id=?',(change_id,)).fetchone() is not None
    def mark_change(self,change_id):
        with self.lock:self.db.execute('INSERT OR IGNORE INTO applied_changes(change_id) VALUES(?)',(change_id,)); self._commit()
    def add_conflict(self,local,remote,reason):
        with self.lock:self.db.execute('INSERT INTO conflicts(entity_type,entity_id,local_payload,remote_payload,reason) VALUES(?,?,?,?,?)',(local.entity_type,local.entity_id,canonical_json(local.to_dict()),canonical_json(remote.to_dict()),reason)); self._commit()
    def conflicts(self):
        with self.lock:return [dict(r) for r in self.db.execute('SELECT * FROM conflicts ORDER BY conflict_id').fetchall()]
    def all_entities(self):
        with self.lock:
            rows=self.db.execute('SELECT entity_type,entity_id,payload,version,deleted FROM entities').fetchall(); return [Entity(r['entity_type'],r['entity_id'],json.loads(r['payload']),VectorClock.from_dict(json.loads(r['version'])),bool(r['deleted'])) for r in rows]
    def export_changes(self,known):
        with self.lock:
            rows=self.db.execute('SELECT * FROM changes').fetchall(); out=[]
            for r in rows:
                version=VectorClock.from_dict(json.loads(r['version']))
                if known.dominates(version):continue
                out.append(Change(r['change_id'],r['node_id'],r['entity_type'],r['entity_id'],json.loads(r['fields']),version,VectorClock.from_dict(json.loads(r['base_version'])),bool(r['deleted'])))
            return out
