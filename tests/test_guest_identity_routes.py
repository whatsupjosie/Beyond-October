"""Real HTTP and socket boundaries with a separately owned visiting identity."""
import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from modules import auth, auth_routes, userdb
from modules.chat_rooms import _websocket_identity
from modules.credentials import CredentialStore
from modules.governance import GovernanceEngine
from modules.guest_identity import GuestAdmission, sign_visit
from modules.guest_identity_routes import create_guest_identity_router
from modules.guest_session_guard import GuestSessionGuardMiddleware
from modules.production_notes import create_production_notes_router
from tests.test_guest_identity import profile, CONSENTS


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    monkeypatch.setattr(userdb, '_DB_PATH', tmp_path/'users.db')
    userdb._sync_init_db()
    userdb._sync_create_owner_via_setup('host-owner', 'strong-password-A19!')
    admission = GuestAdmission(GovernanceEngine(tmp_path))
    monkeypatch.setattr(auth, '_guest_admission', admission)
    auth_routes.set_auth_instance(auth)
    app = FastAPI()
    app.add_middleware(GuestSessionGuardMiddleware)
    app.include_router(auth_routes.router)
    app.include_router(create_guest_identity_router(admission, CredentialStore(tmp_path)))
    app.include_router(create_production_notes_router(tmp_path, Path(__file__).resolve().parents[1]/'static/world/note_spots.json'))
    outgoing = asyncio.Event()

    @app.post('/trigger-test-frame')
    async def trigger():
        outgoing.set()
        return {'ok': True}

    @app.websocket('/outgoing')
    async def outgoing_probe(ws: WebSocket):
        _websocket_identity(ws)
        await ws.accept()
        await ws.send_text('ready')
        await outgoing.wait()
        await ws.send_text('must not be delivered')

    @app.websocket('/probe')
    async def probe(ws: WebSocket):
        try:
            identity = _websocket_identity(ws)
            await ws.accept()
            await ws.send_json(identity)
            while True:
                await ws.receive_text()
                await ws.send_text('accepted')
        except (ValueError, WebSocketDisconnect):
            return

    with TestClient(app) as client:
        owner = {'Authorization': 'Bearer ' + auth.create_access_token({'sub': 'host-owner', 'role': 'owner'})}
        yield client, owner, admission, CredentialStore(tmp_path/'own-copy')


def join(rig):
    client, owner, admission, home = rig
    code = client.post('/api/guests/invites', headers=owner, json={}).json()['invite_code']
    challenge = client.post('/api/guests/challenge', json={'invite_code': code}).json()
    proof = sign_visit(home, profile(), challenge['challenge'], CONSENTS)
    submitted = client.post('/api/guests/request', json=proof)
    assert submitted.status_code == 201, submitted.text
    return challenge


def test_guest_has_own_id_private_notes_and_no_local_account(rig):
    client, owner, admission, _ = rig
    challenge = join(rig)
    status = {'poll_token': challenge['poll_token']}
    assert 'access_token' not in client.post('/api/guests/status', json=status).json()
    pending = client.get('/api/guests/pending', headers=owner).json()['pending'][0]
    approved = client.post('/api/guests/entries/'+pending['entry_id']+'/approve', headers=owner,
                           json={'fingerprint': pending['fingerprint']})
    assert approved.status_code == 200
    lease = client.post('/api/guests/status', json=status)
    assert lease.status_code == 200, lease.text
    assert 'HttpOnly' in lease.headers['set-cookie']
    guest = {'Authorization': 'Bearer ' + lease.json()['access_token']}
    assert lease.json()['user_id'] == profile()['user_id']
    assert userdb._sync_count_users() == 1
    assert userdb._sync_get_user(profile()['user_id']) is None
    me = client.get('/api/profile/me', headers=guest).json()
    assert me['visiting'] and me['details']['about'] == {'pronouns': 'they/them'}
    assert client.patch('/api/profile/me', headers=guest, json={'display_name': 'local change'}).status_code == 403
    assert client.post('/api/profile/password', headers=guest, json={}).status_code == 403
    assert client.post('/api/guests/invites', headers=guest, json={}).status_code == 403
    assert client.get('/api/guests/pending', headers=guest).status_code == 403
    assert client.post('/api/guests/entries/'+pending['entry_id']+'/revoke', headers=guest).status_code == 403
    people = client.get('/api/production/people', headers=owner).json()['people']
    owner_id = next(p['user_id'] for p in people if p['username'] == 'host-owner')
    note = client.post('/api/notes', headers=owner, json={'subject': 'A private production note', 'to': [me['user_id']]}).json()
    inbox = client.get('/api/notes', headers=guest).json()
    assert inbox['notes'][0]['subject'] == 'A private production note'
    assert client.get('/api/auth/verify', headers=guest).json()['user_id'] == me['user_id']
    with client.websocket_connect('/probe', headers=guest) as ws:
        assert ws.receive_json()['user_id'] == me['user_id']
        assert client.post('/api/guests/entries/'+pending['entry_id']+'/revoke', headers=owner).status_code == 200
        ws.send_text('must be refused')
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_text()
        assert error.value.code == 1008
    assert client.get('/api/profile/me', headers=guest).status_code == 401
    assert client.get('/api/auth/verify', headers=guest).status_code == 401


def test_approval_requires_reviewed_key_and_challenge_does_not_allow_local_id_claim(rig):
    client, owner, admission, home = rig
    challenge = join(rig)
    pending = client.get('/api/guests/pending', headers=owner).json()['pending'][0]
    assert pending['known_key'] is False
    assert client.post('/api/guests/entries/'+pending['entry_id']+'/approve', headers=owner,
                       json={'fingerprint': 'wrong'}).status_code == 409
    assert client.post('/api/guests/request', json=[]).status_code == 400
    assert client.post('/api/guests/challenge', json={'invite_code': 'fake'}).status_code == 400
    assert client.post('/api/guests/status', json={'poll_token': 'fake'}).status_code == 400
    assert client.post('/api/guests/entries/'+pending['entry_id']+'/deny', headers=owner).status_code == 200
    assert client.post('/api/guests/status', json={'poll_token': challenge['poll_token']}).json()['status'] == 'denied'


def test_revoked_guest_cannot_receive_unsolicited_frames_on_idle_socket(rig):
    client, owner, admission, home = rig
    challenge = join(rig)
    pending = client.get('/api/guests/pending', headers=owner).json()['pending'][0]
    client.post('/api/guests/entries/'+pending['entry_id']+'/approve', headers=owner,
                json={'fingerprint': pending['fingerprint']})
    lease = client.post('/api/guests/status', json={'poll_token': challenge['poll_token']}).json()
    guest = {'Authorization': 'Bearer ' + lease['access_token']}
    with client.websocket_connect('/outgoing', headers=guest) as ws:
        assert ws.receive_text() == 'ready'
        assert client.post('/api/guests/entries/'+pending['entry_id']+'/revoke', headers=owner).status_code == 200
        client.post('/trigger-test-frame')
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_text()
        assert error.value.code == 1008
