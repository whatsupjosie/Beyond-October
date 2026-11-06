"""Concurrent real SQLite startup and inherited worker-session moderation."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import multiprocessing
import pytest

from modules import userdb
from modules.governance import GovernanceEngine
from modules.production_notes import NotesStore


@pytest.mark.parametrize('kind',['profiles','notes','governance'])
def test_concurrent_schema_migration(kind,tmp_path,monkeypatch):
    for index in range(8):
        root=tmp_path/str(index);root.mkdir()
        if kind=='profiles':monkeypatch.setattr(userdb,'_DB_PATH',root/'users.db')
        def start(_):
            try:
                if kind=='profiles':userdb._sync_init_db()
                elif kind=='notes':NotesStore(root)
                else:GovernanceEngine(root)
            except Exception as error:return repr(error)
        with ThreadPoolExecutor(max_workers=12) as pool:
            errors=[error for error in pool.map(start,range(12)) if error]
        assert errors==[]


def _shared_ban_worker(directory,queue):
    authority=GovernanceEngine(Path(directory))
    queue.put((authority.is_banned('visitor')[0],authority.unban_user('visitor','owner')))


def test_spawned_worker_inherits_session_authority(tmp_path,monkeypatch):
    monkeypatch.delenv('PUBCAST_SESSION_ID',raising=False)
    authority=GovernanceEngine(tmp_path)
    authority.ban_user('visitor','Current production','owner')
    context=multiprocessing.get_context('spawn');queue=context.Queue()
    process=context.Process(target=_shared_ban_worker,args=(str(tmp_path),queue));process.start()
    try:
        assert queue.get(timeout=20)==(True,True)
        process.join(20);assert process.exitcode==0
        assert not authority.is_banned('visitor')[0]
    finally:
        if process.is_alive():process.terminate();process.join(5)
        queue.close();queue.join_thread()
