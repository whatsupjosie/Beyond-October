"""Durable DM permission lifecycle: restart, revocation and concurrent requests."""
from __future__ import annotations

import concurrent.futures
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from modules.auth import create_access_token
from modules.chat_rooms import (DMManager, create_chat_router, dm_room_id,
                                install_chat_websocket)
from modules.hub import Hub
from modules.route_security import current_identity


def auth(user, role='guest'):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': user, 'role': role})}


def ws_path(room):
    return '/ws/chat/' + room


def ws_headers(user, role='guest'):
    return auth(user, role)


def assert_rejected(client, url, headers=None):
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(url, headers=headers or {}) as socket:
            socket.receive_json()
    assert error.value.code == 1008


@pytest.fixture
def app_factory(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')

    def build():
        hub = Hub(tmp_path)
        app = FastAPI()
        app.include_router(create_chat_router(hub, current_identity))
        install_chat_websocket(app, hub, current_identity)
        return TestClient(app), hub

    return build


def test_dm_permission_survives_recreation_and_revocation_blocks_new_connections(app_factory):
    alice, bob, intruder = ('alice-' + uuid.uuid4().hex,
                           'bob-' + uuid.uuid4().hex,
                           'intruder-' + uuid.uuid4().hex)
    c1, _ = app_factory()
    assert_rejected(c1, ws_path(dm_room_id(alice, bob)), ws_headers(alice))
    request = c1.post('/api/chat/dm/request', json={'to_user': bob, 'message': 'private'},
                      headers=auth(alice))
    assert request.status_code == 200
    rid = request.json()['request_id']
    assert c1.get('/api/chat/dm/pending', headers=auth(intruder)).json()['count'] == 0
    assert c1.get('/api/chat/dm/pending', headers=auth(bob)).json()['requests'][0]['request_id'] == rid

    # Recreate BOTH API router and websocket adapter to simulate a server restart.
    c2, hub2 = app_factory()
    assert c2.get('/api/chat/dm/pending', headers=auth(bob)).json()['requests'][0]['message'] == 'private'
    assert_rejected(c2, ws_path(dm_room_id(alice, bob)), ws_headers(alice))
    assert c2.post('/api/chat/dm/accept/' + rid, headers=auth(intruder)).status_code == 403
    assert c2.post('/api/chat/dm/accept/' + rid, headers=auth(bob)).status_code == 200
    assert c2.post('/api/chat/dm/accept/' + rid, headers=auth(bob)).status_code == 409
    room = dm_room_id(alice, bob)
    assert c2.get('/api/chat/dm/active', headers=auth(intruder)).json()['rooms'] == []
    assert c2.get('/api/chat/dm/active', headers=auth(alice)).json()['rooms'] == [
        {'other_user': bob, 'dm_room': room, 'status': 'accepted',
         'accepted_at': c2.get('/api/chat/dm/active', headers=auth(alice)).json()['rooms'][0]['accepted_at']}
    ]
    assert_rejected(c2, ws_path(room), ws_headers(intruder))
    with c2.websocket_connect(ws_path(room), headers=ws_headers(alice)) as socket:
        socket.receive_json()  # accepted room presence
        socket.send_json({'type': 'chat', 'text': 'Still private', 'user_id': intruder})
        seen = socket.receive_json()
        assert seen['type'] == 'chat' and seen['payload']['user_id'] == alice
        assert seen['payload']['text'] == 'Still private'
    c3, _ = app_factory()
    with c3.websocket_connect(ws_path(room), headers=ws_headers(bob)) as socket:
        assert socket.receive_json()['type'] == 'history'
    # Any participant can revoke. Not the bystander and not via caller fields.
    assert c3.post('/api/chat/dm/revoke', json={'other_user': alice},
                   headers=auth(intruder)).status_code == 409
    revoked = c3.post('/api/chat/dm/revoke', json={'other_user': alice, 'actor': intruder},
                      headers=auth(bob))
    assert revoked.status_code == 200
    assert revoked.json()['grants_revoked'] == 1
    c4, _ = app_factory()
    assert c4.get('/api/chat/dm/active', headers=auth(bob)).json()['rooms'] == []
    assert_rejected(c4, ws_path(room), ws_headers(alice))
    assert_rejected(c4, ws_path(room), ws_headers(bob))
    assert c4.post('/api/chat/dm/revoke', json={'other_user': bob}, headers=auth(alice)).status_code == 409
    assert c4.post('/api/chat/dm/request', json={'to_user': bob}, headers=auth(alice)).status_code == 200


def test_revocation_evicts_all_active_dm_sockets_and_leaves_other_rooms_open(app_factory):
    client, hub = app_factory()
    alice, bob = 'a-' + uuid.uuid4().hex, 'b-' + uuid.uuid4().hex
    request = client.post('/api/chat/dm/request', json={'to_user': bob}, headers=auth(alice)).json()
    assert client.post('/api/chat/dm/accept/' + request['request_id'], headers=auth(bob)).status_code == 200
    room = dm_room_id(alice, bob)
    with client.websocket_connect(ws_path('world'), headers=ws_headers(alice)) as public:
        public.receive_json()
        with client.websocket_connect(ws_path(room), headers=ws_headers(alice)) as a:
            a.receive_json()
            with client.websocket_connect(ws_path(room), headers=ws_headers(bob)) as b:
                b.receive_json()
                assert client.post('/api/chat/dm/revoke', json={'other_user': bob}, headers=auth(alice)).status_code == 200
                # The close may follow an already queued presence frame.
                for socket in (a, b):
                    with pytest.raises(WebSocketDisconnect) as error:
                        for _ in range(5):
                            socket.receive_json()
                    assert error.value.code in (1000, 1008)
                assert not hub.rooms.get(room)
                public.send_json({'type': 'chat', 'text': 'public still works'})
                for _ in range(5):
                    message = public.receive_json()
                    if message.get('type') == 'chat':
                        assert message['payload']['text'] == 'public still works'
                        break
                else:
                    pytest.fail('public socket died when private grant was revoked')


def test_dm_request_state_transition_is_atomic_with_multiple_managers(tmp_path):
    db_path = tmp_path / 'global' / 'dm.sqlite3'
    first, second = DMManager(db_path), DMManager(db_path)
    one = first.request_dm('ALICE', 'guest', 'Alice', 'Bob', 'welcome')
    assert second.pending_for_user('bob')[0].request_id == one.request_id
    assert not second.can_open_dm('Alice', 'BOB')
    with pytest.raises(ValueError):
        second.request_dm('alice', 'guest', 'Alice', 'bob', 'duplicate')
    with pytest.raises(PermissionError):
        second.accept(one.request_id, 'Charlie')
    assert second.accept(one.request_id, 'BOB').status.value == 'accepted'
    assert first.can_open_dm('alice', 'bob')
    with pytest.raises(ValueError):
        first.decline(one.request_id, 'bob')
    assert first.revoke('alice', 'bob') == 1
    assert not second.can_open_dm('alice', 'bob')

    def issue(_):
        try:
            return second.request_dm('Alice', 'guest', 'Alice', 'Bob').request_id
        except ValueError:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        issued = list(pool.map(issue, range(12)))
    assert len([request_id for request_id in issued if request_id]) == 1
    assert len(first.pending_for_user('BOB')) == 1


def test_dm_http_input_validation(app_factory):
    client, _ = app_factory()
    for body in ([], None, {}, {'to_user': 123}, {'to_user': ' '},
                 {'to_user': 'b', 'message': []}, {'to_user': 'b', 'message': 'x' * 281}):
        assert client.post('/api/chat/dm/request', json=body, headers=auth('a')).status_code == 400
    for body in (None, [], {}, {'other_user': 45}, {'other_user': ''}, {'other_user': 'x' * 101}):
        assert client.post('/api/chat/dm/revoke', json=body, headers=auth('a')).status_code == 400
