"""Durable canonical-chat recovery, including interrupted acknowledgements."""
import asyncio
import json
import uuid
import os
import subprocess
import sys
from pathlib import Path

import pytest

from blackbox_event_language.schema import decode_record
from modules.blackbox_runtime import create_blackbox_witness
from modules.hub import Hub


def chat_records(root):
    return [decode_record(line) for path in (root/'blackbox').glob('*.bbx')
            for line in path.read_text().splitlines()
            if decode_record(line)['payload'].get('event_type')=='chat.message']


@pytest.mark.asyncio
async def test_saved_chat_is_recovered_after_restart_without_rebroadcast_or_ai(tmp_path):
    hub=Hub(tmp_path)
    first=await hub.post_chat_message('world','owner','Exact, replay text.\n☕|%')
    calls=[]
    async def callback(message):calls.append(message)
    restarted=Hub(tmp_path);restarted.on_chat_callback=callback
    witness=create_blackbox_witness(tmp_path);restarted.blackbox_witness=witness
    status=witness.recover_chat()
    assert status['pending']==0 and status['replayed']==1
    witness.recover_chat(); witness.close()
    rows=chat_records(tmp_path)
    assert len(rows)==1 and rows[0]['payload']['message_id']==first['message_id']
    assert rows[0]['payload']['text']==first['text']
    assert rows[0]['payload']['delivery_mode']=='replay'
    assert not calls
    from tools.blackbox_inspect import inspect
    audit=inspect(tmp_path)
    assert audit['ok'] and audit['coverage_complete'], audit


@pytest.mark.asyncio
async def test_retry_repairs_missing_witness_without_duplicate_chat_or_ai(tmp_path, monkeypatch):
    hub=Hub(tmp_path);witness=create_blackbox_witness(tmp_path);hub.blackbox_witness=witness
    original=witness.record_event
    monkeypatch.setattr(witness,'record_event',lambda kind,**kw:None if kind=='chat.message' else original(kind,**kw))
    key=str(uuid.uuid4());calls=[]
    async def callback(message):calls.append(message['message_id'])
    hub.on_chat_callback=callback
    first=await hub.post_chat_message('world','owner','One exact message.',key)
    assert first['warnings']
    assert witness.health()['coverage']=='degraded'
    assert witness.health()['chat_replay']['pending']==1
    monkeypatch.setattr(witness,'record_event',original)
    second=await hub.post_chat_message('world','owner','One exact message.',key)
    assert second['duplicate']
    assert len(chat_records(tmp_path))==1
    assert len(await hub.get_recent_history('world',10))==1 and calls==[first['message_id']]
    witness.close()


@pytest.mark.asyncio
async def test_periodic_worker_recovers_without_another_send(tmp_path, monkeypatch):
    hub=Hub(tmp_path);witness=create_blackbox_witness(tmp_path);hub.blackbox_witness=witness
    await witness.start_chat_replay(interval=.02)
    original=witness.record_event
    try:
        monkeypatch.setattr(witness,'record_event',lambda kind,**kw:None if kind=='chat.message' else original(kind,**kw))
        first=await hub.post_chat_message('world','owner','Recovery without another click.')
        assert first['warnings']
        monkeypatch.setattr(witness,'record_event',original)
        for _ in range(200):
            if witness._chat_replay.get('pending')==0 and chat_records(tmp_path):break
            await asyncio.sleep(.01)
        assert len(chat_records(tmp_path))==1 and witness._chat_replay['pending']==0
    finally:
        await witness.stop_chat_replay();witness.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('after_append',[False,True])
async def test_process_death_at_delivery_boundary_is_recovered_once(tmp_path, after_append):
    hub=Hub(tmp_path)
    message=await hub.post_chat_message('world','owner','Survive abrupt exit, exactly once.')
    script=r'''
import os,sys
from modules.blackbox_runtime import create_blackbox_witness
w=create_blackbox_witness(sys.argv[1])
original=w.record_event
def interrupted(kind,**kwargs):
    if kind=='chat.message' and sys.argv[2]=='before':os._exit(23)
    result=original(kind,**kwargs)
    if kind=='chat.message':os._exit(23)
    return result
w.record_event=interrupted
w.recover_chat()
os._exit(24)
'''
    result=subprocess.run([sys.executable,'-c',script,str(tmp_path),'after' if after_append else 'before'],
        cwd=Path(__file__).resolve().parents[1],capture_output=True,timeout=20)
    assert result.returncode==23, result.stderr
    witness=create_blackbox_witness(tmp_path)
    assert witness.recover_chat()['pending']==0
    witness.recover_chat();witness.close()
    rows=chat_records(tmp_path)
    assert len(rows)==1 and rows[0]['payload']['message_id']==message['message_id']


@pytest.mark.asyncio
async def test_two_processes_recover_shared_archives_without_duplicate_receipts(tmp_path):
    hub=Hub(tmp_path)
    for i in range(10):await hub.post_chat_message('world','owner',f'Concurrent recovery {i}, exact.')
    script=r'''
import sys
from modules.blackbox_runtime import create_blackbox_witness
w=create_blackbox_witness(sys.argv[1])
for _ in range(3):
    status=w.recover_chat()
    assert status['state']!='blocked', status
assert status['pending']==0, status
w.close()
'''
    workers=[subprocess.Popen([sys.executable,'-c',script,str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
    try:
        for worker in workers:
            output,error=worker.communicate(timeout=30)
            assert worker.returncode==0, error.decode()
    finally:
        for worker in workers:
            if worker.poll() is None:worker.kill();worker.wait(timeout=5)
    rows=chat_records(tmp_path)
    assert len(rows)==10 and len({r['payload']['message_id'] for r in rows})==10


@pytest.mark.asyncio
async def test_failed_fsync_auto_recovers_without_duplicate_after_storage_returns(tmp_path, monkeypatch):
    if os.name!='posix':pytest.skip('Uses POSIX descriptor identity to target the injected fault')
    hub=Hub(tmp_path);witness=create_blackbox_witness(tmp_path);hub.blackbox_witness=witness
    original_fsync=os.fsync;baseline=witness.path.stat().st_size
    identity=witness.path.stat().st_ino
    def fail_chat_fsync(fd):
        stat=os.fstat(fd)
        if stat.st_ino==identity and stat.st_size>baseline:raise OSError('Injected BBX fsync failure')
        return original_fsync(fd)
    with monkeypatch.context() as patch:
        patch.setattr(os,'fsync',fail_chat_fsync)
        saved=await hub.post_chat_message('world','owner','An uncertain durable ack, not a second message.')
        assert saved['warnings'] and witness.recorder._write_failed
    assert witness.recover_chat()['pending']==0
    assert witness.health()['connection']=='running'
    witness.close()
    assert len(chat_records(tmp_path))==1


@pytest.mark.asyncio
async def test_commit_then_lost_ack_never_creates_second_witness(tmp_path, monkeypatch):
    hub=Hub(tmp_path);witness=create_blackbox_witness(tmp_path);hub.blackbox_witness=witness
    original=witness.record_event
    def lost_ack(kind,**kw):
        result=original(kind,**kw)
        return None if kind=='chat.message' else result
    monkeypatch.setattr(witness,'record_event',lost_ack)
    first=await hub.post_chat_message('world','owner','Written before the ack was lost.')
    assert first['warnings'] and len(chat_records(tmp_path))==1
    monkeypatch.setattr(witness,'record_event',original)
    witness.recover_chat();witness.close()
    restarted=create_blackbox_witness(tmp_path);restarted.recover_chat();restarted.close()
    assert len(chat_records(tmp_path))==1


@pytest.mark.asyncio
async def test_previously_witnessed_archive_backfill_is_idempotent(tmp_path):
    hub=Hub(tmp_path);witness=create_blackbox_witness(tmp_path);hub.blackbox_witness=witness
    await hub.post_chat_message('world','owner','Already journalled, exactly once.')
    witness.close()
    # Delivery receipts are a cache; journal evidence remains authoritative.
    restarted=create_blackbox_witness(tmp_path)
    restarted.recover_chat();restarted.recover_chat();restarted.close()
    assert len(chat_records(tmp_path))==1


def test_real_host_starts_replay_and_rearms_it_without_duplicate_records(tmp_path):
    from tests.host_lifespan_helpers import run_isolated_host
    run_isolated_host(r'''
import asyncio
from pathlib import Path
from starlette.testclient import TestClient
from modules.hub import Hub
from blackbox_event_language.schema import decode_record
import main

async def seed():
    return await Hub(main.DATA_DIR).post_chat_message('world','owner','Saved before the host started, exactly.')
message=asyncio.run(seed())
for _ in range(2):
    with TestClient(main.app) as client:
        witness=main.blackbox_witness
        assert witness._chat_task is not None
        assert witness._chat_replay['pending']==0, witness._chat_replay
        records=[decode_record(line) for p in (main.DATA_DIR/'blackbox').glob('*.bbx')
                 for line in p.read_text().splitlines()]
        chats=[r for r in records if r['payload'].get('event_type')=='chat.message']
        assert len(chats)==1 and chats[0]['payload']['message_id']==message['message_id']
    assert witness._chat_task is None and witness._closed
''', tmp_path)


@pytest.mark.asyncio
async def test_deleted_delivery_cache_rebuilds_from_journals_without_duplicates(tmp_path):
    import sqlite3
    hub=Hub(tmp_path);witness=create_blackbox_witness(tmp_path);hub.blackbox_witness=witness
    await hub.post_chat_message('world','owner','Original, before the cache is lost.')
    witness.close()
    with sqlite3.connect(tmp_path/'global'/'chat_commit_receipts.sqlite3') as db:
        db.execute('DROP TABLE blackbox_chat_outbox')
    restarted=create_blackbox_witness(tmp_path)
    assert restarted.recover_chat()['pending']==0
    restarted.close()
    assert len(chat_records(tmp_path))==1


@pytest.mark.asyncio
async def test_damaged_ledger_blocks_replay_without_changing_evidence(tmp_path):
    hub=Hub(tmp_path)
    await hub.post_chat_message('world','owner','Save while the witness is missing.')
    bad=create_blackbox_witness(tmp_path);bad.close()
    damaged=bad.path.read_bytes().replace(b'external_boundary',b'damaged_boundary')
    bad.path.write_bytes(damaged)
    witness=create_blackbox_witness(tmp_path)
    status=witness.recover_chat()
    assert status['state']=='blocked'
    assert bad.path.read_bytes()==damaged
    assert not any(decode_record(line)['payload'].get('event_type')=='chat.message'
                   for line in witness.path.read_text().splitlines())
    witness.close()


@pytest.mark.asyncio
async def test_altered_archive_is_not_replayed_as_if_it_were_the_original(tmp_path):
    hub=Hub(tmp_path);witness=create_blackbox_witness(tmp_path);hub.blackbox_witness=witness
    await hub.post_chat_message('world','owner','The immutable original, with punctuation.')
    witness.close()
    archive=tmp_path/'logs'/'world.jsonl'
    payload=json.loads(archive.read_text());payload['text']='An altered original.'
    damaged=json.dumps(payload)+'\n';archive.write_text(damaged)
    restarted=create_blackbox_witness(tmp_path)
    assert restarted.recover_chat()['state']=='blocked'
    assert archive.read_text()==damaged and len(chat_records(tmp_path))==1
    restarted.close()
