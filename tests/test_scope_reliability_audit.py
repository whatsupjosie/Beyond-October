"""Failure-boundary regressions from the post-completion shortcut audit."""
import asyncio
import io
from pathlib import Path

from starlette.datastructures import UploadFile

from modules import production_notes as pn
from modules.governance import BanType, GovernanceEngine
from modules.guest_identity import GuestAdmission
from tests.test_guest_identity import rig, claims, profile
from tests.test_production_notes import env


def test_starting_another_notes_worker_preserves_inflight_attachment(env,monkeypatch):
    client,auth,people,tmp_path=env
    original=pn.NotesStore.create
    def second_worker(store,*args,**kwargs):
        pn.create_production_notes_router(tmp_path/'data',tmp_path/'note_spots.json')
        return original(store,*args,**kwargs)
    monkeypatch.setattr(pn.NotesStore,'create',second_worker)
    import json
    result=client.post('/api/notes',headers=auth('josie','owner'),data={'note':json.dumps({'subject':'Sound','to':[people['pete']['user_id']]})},files={'files':('sound.txt',b'original attachment','text/plain')})
    assert result.status_code==201,result.text
    note=client.get('/api/notes/'+result.json()['id'],headers=auth('pete','guest')).json()
    assert client.get(note['files'][0]['url'],headers=auth('pete','guest')).content==b'original attachment'


def test_guest_session_ban_expires_for_new_run_but_permanent_ban_does_not(rig,tmp_path,monkeypatch):
    host,home,challenge,proof=rig
    entry=host.submit(proof);host.governance.approve_entry(entry,'owner');host.status(challenge['poll_token'])
    token_claims=claims(host,entry)
    host.governance.ban_user(profile()['user_id'],'this session','owner',BanType.SESSION)
    assert not host.validate_claims(token_claims)
    monkeypatch.setenv('PUBCAST_SESSION_ID','new-audit-session')
    restarted=GuestAdmission(GovernanceEngine(tmp_path/'host'))
    assert not restarted.governance.is_banned(profile()['user_id'])[0]
    assert restarted.validate_claims(token_claims)
    restarted.governance.ban_user(profile()['user_id'],'permanent','owner',BanType.PERMANENT)
    monkeypatch.setenv('PUBCAST_SESSION_ID','third-audit-session')
    assert not GuestAdmission(GovernanceEngine(tmp_path/'host')).validate_claims(token_claims)


def test_group_limit_includes_automatically_retained_owner(tmp_path):
    import pytest
    from fastapi import HTTPException
    store=pn.NotesStore(tmp_path/'notes')
    known={'owner'}|{'member'+str(i) for i in range(200)}
    members=[{'user_id':'member'+str(i)} for i in range(200)]
    with pytest.raises(HTTPException) as error:
        store.groups.save('owner',True,{'name':'Too many','members':members},known)
    assert error.value.status_code==400
    assert store.groups.list('owner',True)==[]
    group=store.groups.save('owner',True,{'name':'At limit','members':members[:-1]},known)
    assert len(group['members'])==200


def _hold_batch(incoming,ready,release):
    batch=pn._UploadBatch(Path(incoming))
    (batch.path/'original').write_bytes(b'do not delete')
    ready.set()
    release.wait(30)
    # Simulate process death without the normal request finally cleanup.


def test_staging_reaps_dead_worker_but_never_a_live_worker(tmp_path):
    import multiprocessing
    context=multiprocessing.get_context('spawn')
    incoming=tmp_path/'incoming';incoming.mkdir()
    ready,release=context.Event(),context.Event()
    child=context.Process(target=_hold_batch,args=(str(incoming),ready,release))
    child.start()
    try:
        assert ready.wait(15)
        pn._clean_staging(incoming)
        files=list(incoming.glob('batch-*/original'))
        assert len(files)==1 and files[0].read_bytes()==b'do not delete'
        release.set();child.join(15)
        assert child.exitcode==0
        pn._clean_staging(incoming)
        assert not list(incoming.glob('batch-*'))
    finally:
        release.set();child.join(2)
        if child.is_alive():child.terminate();child.join(5)


def test_membership_change_during_attachment_staging_is_rejected_atomically(env,monkeypatch):
    import json
    client,auth,people,tmp_path=env;owner=auth('josie','owner')
    group=client.post('/api/production/groups',headers=owner,json={'name':'Race','members':[{'user_id':people['pete']['user_id']}]}).json()
    note={'subject':'Must not partially deliver','group_id':group['id'],'to':['@production']}
    note['preview']=client.post('/api/notes/preview',headers=owner,json=note).json()['preview']
    original=pn.NotesStore.create
    def change_after_preview(store,*args,**kwargs):
        store.groups.save(people['josie']['user_id'],True,{'name':'Changed','members':[],'revision':0},set(p['user_id'] for p in people.values()),group['id'])
        return original(store,*args,**kwargs)
    monkeypatch.setattr(pn.NotesStore,'create',change_after_preview)
    sent=client.post('/api/notes',headers=owner,data={'note':json.dumps(note)},files={'files':('private.txt',b'never publish partial bytes','text/plain')})
    assert sent.status_code==409,sent.text
    assert client.get('/api/notes?box=sent',headers=owner).json()['notes']==[]
    assert not list((tmp_path/'data/notes/incoming').glob('batch-*'))
    assert not list((tmp_path/'data/notes/files').iterdir())
