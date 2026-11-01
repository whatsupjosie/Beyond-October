"""Private room IDs must be unambiguous and revocation must reach other Hub workers."""
from __future__ import annotations

import asyncio
import json

from starlette.websockets import WebSocketState
from modules.chat_rooms import DMManager, dm_room_id, create_chat_router, install_chat_websocket
from modules.hub import Hub
from modules.route_security import current_identity
from fastapi import FastAPI
from fastapi.testclient import TestClient
from modules.auth import create_access_token


def test_legacy_pair_delimiter_does_not_collide_or_break_private_room(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    one = ('a____b', 'c')
    two = ('a', 'b____c')
    assert dm_room_id(*one) != dm_room_id(*two)
    assert dm_room_id('ALICE', 'Bob') == 'dm____alice____bob'  # existing logs survive
    hub = Hub(tmp_path)
    app = FastAPI()
    app.include_router(create_chat_router(hub, current_identity))
    install_chat_websocket(app, hub, current_identity)
    client = TestClient(app)
    auth = lambda user: {'Authorization': 'Bearer ' + create_access_token({'sub': user, 'role': 'guest'})}
    requested = client.post('/api/chat/dm/request', json={'to_user': one[1]}, headers=auth(one[0]))
    assert requested.status_code == 200
    approved = client.post('/api/chat/dm/accept/' + requested.json()['request_id'], headers=auth(one[1]))
    assert approved.status_code == 200
    room = approved.json()['dm_room']
    assert room == dm_room_id(*one)
    with client.websocket_connect('/ws/chat/' + room, headers=auth(one[0])) as ws:
        assert ws.receive_json()['type'] == 'presence'
        ws.send_json({'type': 'chat', 'text': 'Private: the real participants only'})
        assert ws.receive_json()['payload']['text'] == 'Private: the real participants only'


class Socket:
    application_state = WebSocketState.CONNECTED

    def __init__(self):
        self.frames = []
        self.closed = False

    async def accept(self):
        pass

    async def send_text(self, frame):
        self.frames.append(json.loads(frame))

    async def close(self, *args, **kwargs):
        self.closed = True
        self.application_state = WebSocketState.DISCONNECTED


def test_other_worker_does_not_broadcast_after_dm_revocation(tmp_path):
    manager_a = DMManager(tmp_path / 'global' / 'dm_requests.sqlite3')
    manager_b = DMManager(tmp_path / 'global' / 'dm_requests.sqlite3')
    req = manager_a.request_dm('alice', 'guest', 'Alice', 'bob')
    manager_a.accept(req.request_id, 'bob')
    hub = Hub(tmp_path)
    room = dm_room_id('alice', 'bob')
    # Simulates an already-connected socket on worker A, while worker B
    # handles the revoke in the same persistent consent database.
    hub.dm_authorizer = manager_a.can_open_dm
    socket = Socket()
    asyncio.run(hub.connect(socket, room, uid='alice', username='Alice',
                            authenticated=True, dm_peer='bob'))
    socket.frames.clear()
    assert manager_b.revoke('bob', 'alice') == 1
    asyncio.run(hub._broadcast(room, {'type': 'chat', 'payload': {'text': 'SHOULD NOT LEAK'}}))
    assert not any(m.get('type') == 'chat' for m in socket.frames)
    assert socket.closed


def test_dm_delivery_fails_closed_when_consent_database_unavailable(tmp_path):
    manager = DMManager(tmp_path / 'global' / 'dm_requests.sqlite3')
    request = manager.request_dm('alice', 'guest', 'Alice', 'bob')
    manager.accept(request.request_id, 'bob')
    room = dm_room_id('alice', 'bob')
    hub = Hub(tmp_path)
    hub.dm_authorizer = manager.can_open_dm
    socket = Socket()
    asyncio.run(hub.connect(socket, room, uid='alice', username='Alice',
                            authenticated=True, dm_peer='bob'))
    socket.frames.clear()
    def unavailable(*args):
        raise OSError('simulated database outage')
    hub.dm_authorizer = unavailable
    asyncio.run(hub._broadcast(room, {'type': 'chat', 'payload': {'text': 'private'}}))
    assert socket.closed
    assert not any(item.get('type') == 'chat' for item in socket.frames)


def test_hashed_dm_room_denies_other_accepted_pair(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    manager = DMManager(tmp_path / 'global' / 'dm_requests.sqlite3')
    one = manager.request_dm('a____b', 'guest', 'A', 'c')
    two = manager.request_dm('a', 'guest', 'A', 'b____c')
    manager.accept(one.request_id, 'c')
    manager.accept(two.request_id, 'b____c')
    room = dm_room_id('a____b', 'c')
    assert manager.peer_for_room(room, 'a____b') == 'c'
    assert manager.peer_for_room(room, 'a') is None
    assert manager.peer_for_room(dm_room_id('a', 'b____c'), 'a') == 'b____c'
    assert manager.peer_for_room(room, 'stranger') is None
    hub = Hub(tmp_path)
    app = FastAPI()
    app.include_router(create_chat_router(hub, current_identity))
    install_chat_websocket(app, hub, current_identity)
    client = TestClient(app)
    from starlette.websockets import WebSocketDisconnect
    import pytest
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/ws/chat/' + room, headers={'Authorization': 'Bearer ' + create_access_token({'sub': 'a', 'role': 'guest'})}) as ws:
            ws.receive_json()


def test_private_dm_consent_database_permissions(tmp_path):
    import os
    import stat
    import pytest
    if os.name != 'posix':
        pytest.skip('POSIX permissions; Windows ACL review is a separate platform gate')
    path = tmp_path / 'global' / 'dm_requests.sqlite3'
    old_umask = os.umask(0o022)
    try:
        manager = DMManager(path)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        manager.request_dm('alice', 'guest', 'Alice', 'bob', message='Confidential invitation')
        for suffix in ('-wal', '-shm'):
            sidecar = path.with_name(path.name + suffix)
            if sidecar.exists():
                assert stat.S_IMODE(sidecar.stat().st_mode) & 0o077 == 0
    finally:
        os.umask(old_umask)
