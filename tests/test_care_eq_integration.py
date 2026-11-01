"""CARE reference merge integration: masking, restart, owner boundaries, bridge."""
import asyncio
import json
import pytest
from fastapi import HTTPException
from modules.care_eq import CareCoordinator, CareMode, CareSession, Ambiguator
from modules import alex_routes


def test_care_session_matches_reference_semantics():
    session = CareSession('owner')
    with pytest.raises(PermissionError):
        session.activate('another')
    session.activate('owner')
    assert 'meaning unknown' in session.receive('hello')
    assert session.receive('paRAchute') == '[SAFEWORD: PARACHUTE]'
    assert session.mode == CareMode.ORDINARY
    assert session.receive('ordinary') == 'ordinary'
    assert all('hello' not in str(e) for e in session.monitor.events)


def test_persistent_private_observation_and_isolation(tmp_path):
    care = CareCoordinator(tmp_path)
    care.activate('u')
    assert 'vocalization' in care.receive('u', 'private message')
    event = care.observe('u', 'observation', {'response': 'calmer'},
                         hypothesis='care helped', alternatives=['time passed'], outcome='unknown')
    assert event['status'] == 'unreviewed'
    assert not care.is_active('different')
    saved = (tmp_path/'care_eq_private').glob('*.json')
    assert all('private message' not in p.read_text() for p in saved)
    loaded = CareCoordinator(tmp_path)
    assert loaded.is_active('u')
    assert loaded.export('u')['events'][-1]['alternatives'] == ['time passed']
    assert loaded.receive('u', 'parachute') == '[SAFEWORD: PARACHUTE]'
    assert not loaded.is_active('u')
    assert not CareCoordinator(tmp_path).is_active('u')


def test_routes_owner_scoped_and_disabled_without_auth(tmp_path):
    care = CareCoordinator(tmp_path)
    alex_routes.set_care_eq(care)
    u = {'user_id': 'u', 'role': 'owner', 'authenticated': True}
    other = {'user_id': 'other', 'role': 'guest', 'authenticated': True}
    anon = {'user_id': 'u', 'role': 'owner', 'authenticated': False}
    try:
        with pytest.raises(HTTPException):
            asyncio.run(alex_routes.activate_care(identity=anon))
        assert asyncio.run(alex_routes.activate_care(identity=u))['mode'] == 'baby'
        with pytest.raises(HTTPException):
            asyncio.run(alex_routes.care_events(identity=other, user_id='u'))
        assert asyncio.run(alex_routes.deactivate_care(identity=u))['mode'] == 'ordinary'
    finally:
        alex_routes.set_care_eq(None)


@pytest.mark.asyncio
async def test_bridge_masks_care_facing_text_without_breaking_system_alex(tmp_path):
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    bridge = AlexJeremyBridge(data_dir=tmp_path)
    care = CareCoordinator(tmp_path)
    bridge.care_eq = care
    care.activate('u')
    try:
        packet = await bridge.process_user_turn(user_id='u', session_id='s', text='classified adult paragraph xyz')
        assert packet['alex_state']
        alex = bridge.alex_for('u')
        assert all('classified adult paragraph' not in m.content for m in alex.memory._recent_memories)
        assert 'classified adult paragraph' not in json.dumps(care.export('u'))
        assert care.is_active('u')
    finally:
        bridge.shutdown()


def test_care_and_backup_http_boundaries_use_real_jwt(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from modules.auth import create_access_token
    from modules.alex_memory_backup import AlexMemoryBackup, LocalFolderBackend
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    care = CareCoordinator(tmp_path)
    backup = AlexMemoryBackup(tmp_path, LocalFolderBackend(tmp_path / 'backup'))
    alex_routes.set_care_eq(care)
    alex_routes.set_alex_backup(backup)
    app = FastAPI(); app.include_router(alex_routes.router)
    client = TestClient(app)
    def token(name, role='guest'):
        return {'Authorization': 'Bearer ' + create_access_token({'sub': name, 'role': role})}
    try:
        assert client.post('/api/alex/care/activate').status_code == 401
        assert client.post('/api/alex/care/activate', headers=token('u')).status_code == 403
        assert client.post('/api/alex/care/activate', headers=token('u', 'owner')).status_code == 200
        assert client.get('/api/alex/care/events?user_id=u', headers=token('other', 'owner')).status_code == 403
        assert client.get('/api/alex/backup/search?q=anything').status_code == 401
        assert client.get('/api/alex/backup/search?q=anything&user_id=u', headers=token('other')).status_code == 403
        assert client.get('/api/alex/backup/search?q=anything&user_id=u', headers=token('u')).status_code == 200
    finally:
        alex_routes.set_care_eq(None)
        alex_routes.set_alex_backup(None)
