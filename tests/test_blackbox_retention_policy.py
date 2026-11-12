"""Archive settings are durable, authorized and non-destructive."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from modules.auth import create_access_token
from modules.blackbox_routes import create_blackbox_router
from modules.blackbox_runtime import create_blackbox_witness
from modules.blackbox_retention_policy import ArchiveLimits,ArchivePolicyStore,PolicyUpdate,PolicyConflict
from blackbox_event_language.schema import decode_record


def auth(role='owner'):
    return {'Authorization':'Bearer '+create_access_token({'sub':f'test-{role}','role':role})}


def test_defaults_are_provisional_and_protection_is_not_editable(tmp_path):
    policy=ArchivePolicyStore(tmp_path).read()
    assert policy['storage_limit_bytes']==5_000_000_000
    assert policy['retention_value']==6 and policy['retention_unit']=='months'
    assert policy['flagged_records_never_delete'] and policy['active_and_pending_records_protected']
    assert not policy['automatic_cleanup_enabled'] and policy['defaults_provisional']
    with pytest.raises(ValueError):PolicyUpdate(expected_revision=0,flagged_records_never_delete=False)


def test_real_routes_persist_custom_limits_and_audit_across_restart(tmp_path):
    witness=create_blackbox_witness(tmp_path)
    app=FastAPI();app.include_router(create_blackbox_router(witness))
    with TestClient(app) as client:
        before=client.get('/api/operator/blackbox/archive-policy',headers=auth()).json()
        response=client.patch('/api/operator/blackbox/archive-policy',headers=auth(),json={
            'expected_revision':before['revision'],'storage_limit_bytes':12_000_000_000,
            'retention_value':45,'retention_unit':'days'})
        assert response.status_code==200,response.text
        result=response.json()
        assert result['revision']==1 and result['pending_audit_records']==0
        assert result['flagged_records_never_delete'] and not result['preallocated']
        assert result['disk_free_bytes']>=0
    witness.close()
    restarted=create_blackbox_witness(tmp_path)
    policy=restarted.archive_policy()
    assert policy['storage_limit_bytes']==12_000_000_000 and policy['retention_value']==45
    assert policy['retention_unit']=='days' and policy['revision']==1
    events=[decode_record(line) for path in (tmp_path/'blackbox').glob('*.bbx')
            for line in path.read_text().splitlines()]
    changes=[r for r in events if r['payload'].get('event_type')=='blackbox.archive_policy_changed']
    assert len(changes)==1
    data=json.loads(changes[0]['payload']['data_json'])
    assert data['actor']=='test-owner' and data['after']['retention_value']==45
    restarted.close()


@pytest.mark.parametrize('role',[None,'guest','mod','admin'])
def test_settings_require_authenticated_owner_even_when_dev_auth_is_relaxed(tmp_path,monkeypatch,role):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH','0')
    witness=create_blackbox_witness(tmp_path)
    app=FastAPI();app.include_router(create_blackbox_router(witness))
    with TestClient(app) as client:
        headers=auth(role) if role else {'X-Client-Id':'owner'}
        assert client.get('/api/operator/blackbox/archive-policy',headers=headers).status_code==403
        assert client.patch('/api/operator/blackbox/archive-policy',headers=headers,json={
            'expected_revision':0,'retention_value':1}).status_code==403
    witness.close()


@pytest.mark.parametrize('patch',[
    {},{'storage_limit_bytes':0},{'storage_limit_bytes':-1},{'storage_limit_bytes':True},
    {'storage_limit_bytes':1.2},{'storage_limit_bytes':2**63},{'retention_value':None},
    {'retention_value':0},{'retention_unit':'forever'},{'retention_value':True},
    {'retention_value':3_650_000,'retention_unit':'years'},{'delete_flagged':True}])
def test_invalid_changes_leave_saved_policy_unchanged(tmp_path,patch):
    witness=create_blackbox_witness(tmp_path)
    app=FastAPI();app.include_router(create_blackbox_router(witness))
    with TestClient(app) as client:
        response=client.patch('/api/operator/blackbox/archive-policy',headers=auth(),
                              json={'expected_revision':0,**patch})
        assert response.status_code==422,response.text
        assert client.get('/api/operator/blackbox/archive-policy',headers=auth()).json()['revision']==0
    witness.close()


def test_concurrent_edits_cannot_silently_overwrite_each_other(tmp_path):
    a=ArchivePolicyStore(tmp_path);b=ArchivePolicyStore(tmp_path)
    def save(store,value):
        try:return store.update(PolicyUpdate(expected_revision=0,retention_value=value),'owner')['revision']
        except PolicyConflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        x=pool.submit(save,a,12);y=pool.submit(save,b,3)
        assert sorted([str(x.result()),str(y.result())])==['1','conflict']
    assert a.read()['revision']==1


def test_calendar_months_are_not_silently_converted_to_thirty_day_periods():
    created=datetime(2024,8,31,15,20,tzinfo=timezone.utc)
    assert ArchiveLimits().expires_at(created)==datetime(2025,2,28,15,20,tzinfo=timezone.utc)
    leap=datetime(2024,2,29,tzinfo=timezone.utc)
    assert ArchiveLimits(retention_value=1,retention_unit='years').expires_at(leap)==datetime(2025,2,28,tzinfo=timezone.utc)
    assert ArchiveLimits(retention_value=2,retention_unit='weeks').expires_at(leap)==datetime(2024,3,14,tzinfo=timezone.utc)


def test_reducing_limit_never_deletes_files_or_weakens_protection(tmp_path):
    witness=create_blackbox_witness(tmp_path)
    protected=tmp_path/'blackbox'/'Never Delete'/'fixture.bin'
    protected.parent.mkdir();protected.write_bytes(b'protected fixture'*100)
    before=protected.read_bytes()
    result=witness.update_archive_policy(PolicyUpdate(expected_revision=0,storage_limit_bytes=1),'owner')
    assert result['storage_limit_bytes']==1 and result['flagged_records_never_delete']
    assert protected.read_bytes()==before
    witness.close()


def test_witness_failure_retains_settings_and_retries_only_the_audit(tmp_path,monkeypatch):
    witness=create_blackbox_witness(tmp_path);original=witness.record_event
    monkeypatch.setattr(witness,'record_event',lambda kind,**kw:None if kind=='blackbox.archive_policy_changed' else original(kind,**kw))
    result=witness.update_archive_policy(PolicyUpdate(expected_revision=0,retention_value=12),'owner')
    assert result['revision']==1 and result['pending_audit_records']==1
    monkeypatch.setattr(witness,'record_event',original)
    witness.recover_chat()
    assert witness.archive_policy()['revision']==1
    assert witness.archive_policy_store().deliver_audits(witness)==0
    witness.close()


def test_postcommit_audit_storage_fault_never_claims_settings_were_not_saved(tmp_path,monkeypatch):
    import sqlite3
    witness=create_blackbox_witness(tmp_path)
    store=witness.archive_policy_store()
    def fail(_):raise sqlite3.OperationalError('Injected audit storage failure')
    monkeypatch.setattr(store,'deliver_audits',fail)
    result=witness.update_archive_policy(PolicyUpdate(expected_revision=0,retention_value=2),'owner')
    assert result['revision']==1 and result['warnings'] and result['pending_audit_records'] is None
    assert store.read()['retention_value']==2
    witness.close()


def test_larger_allowance_reports_free_space_without_preallocating_it(tmp_path,monkeypatch):
    from collections import namedtuple
    from modules import blackbox_retention_policy as policy_module
    usage=namedtuple('Usage','total used free')(2_000_000_000,1_900_000_000,100_000_000)
    monkeypatch.setattr(policy_module.shutil,'disk_usage',lambda path:usage)
    witness=create_blackbox_witness(tmp_path)
    result=witness.update_archive_policy(PolicyUpdate(expected_revision=0,storage_limit_bytes=8_000_000_000),'owner')
    assert result['disk_free_bytes']==100_000_000 and result['limit_exceeds_current_free_space']
    assert result['capacity_scope']=='host_data_directory_volume'
    assert not result['preallocated'] and result['archive_usage_bytes'] is None
    witness.close()


def test_postcommit_capacity_fault_keeps_the_successful_settings_receipt(tmp_path,monkeypatch):
    witness=create_blackbox_witness(tmp_path);store=witness.archive_policy_store()
    def fail():raise OSError('Injected disk capacity failure')
    monkeypatch.setattr(store,'capacity',fail)
    result=witness.update_archive_policy(PolicyUpdate(expected_revision=0,retention_value=14,retention_unit='days'),'owner')
    assert result['revision']==1 and result['disk_free_bytes'] is None and result['warnings']
    assert store.read()['retention_value']==14
    witness.close()


def test_real_host_exposes_saved_policy_after_process_restart(tmp_path):
    from tests.host_lifespan_helpers import run_isolated_host
    run_isolated_host(r'''
from starlette.testclient import TestClient
from modules.auth import create_access_token
import main
with TestClient(main.app) as client:
    headers={'Authorization':'Bearer '+create_access_token({'sub':'test-owner','role':'owner'})}
    old=client.get('/api/operator/blackbox/archive-policy',headers=headers)
    assert old.status_code==200, old.text
    response=client.patch('/api/operator/blackbox/archive-policy',headers=headers,json={
        'expected_revision':old.json()['revision'],'storage_limit_bytes':8000000000,
        'retention_value':2,'retention_unit':'weeks'})
    assert response.status_code==200,response.text
    assert response.json()['pending_audit_records']==0
''',tmp_path)
    run_isolated_host(r'''
from starlette.testclient import TestClient
from modules.auth import create_access_token
import main
with TestClient(main.app) as client:
    headers={'Authorization':'Bearer '+create_access_token({'sub':'test-owner','role':'owner'})}
    response=client.get('/api/operator/blackbox/archive-policy',headers=headers)
    assert response.status_code==200,response.text
    data=response.json()
    assert data['storage_limit_bytes']==8000000000
    assert data['retention_value']==2 and data['retention_unit']=='weeks' and data['revision']==1
    assert data['flagged_records_never_delete'] and not data['automatic_cleanup_enabled']
''',tmp_path)
