from __future__ import annotations
import json, sqlite3, time, uuid, threading
from pathlib import Path
class MemoryGate:
    def __init__(self,path):
        self.lock=threading.RLock(); self.db=sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        self._init()
    def _init(self):
        self.db.executescript('''CREATE TABLE IF NOT EXISTS candidates(candidate_id TEXT PRIMARY KEY,text TEXT NOT NULL,metadata TEXT NOT NULL,created_at REAL NOT NULL,promoted_at REAL);'''); self.db.commit()
    def capture(self,text,metadata=None):
        with self.lock:
            cid=uuid.uuid4().hex
            with self.db:
                self.db.execute('INSERT INTO candidates VALUES(?,?,?,?,NULL)',(cid,text,json.dumps(metadata or {},sort_keys=True),time.time()))
            return cid
    def list(self):
        with self.lock:
            return [dict(r) for r in self.db.execute('SELECT candidate_id,text,metadata,created_at,promoted_at FROM candidates ORDER BY created_at').fetchall()]
    def promote(self,cid):
        with self.lock:
            with self.db:
                r=self.db.execute('SELECT * FROM candidates WHERE candidate_id=?',(cid,)).fetchone()
                if not r: return None
                if r['promoted_at'] is None: self.db.execute('UPDATE candidates SET promoted_at=? WHERE candidate_id=?',(time.time(),cid))
                return dict(self.db.execute('SELECT * FROM candidates WHERE candidate_id=?',(cid,)).fetchone())