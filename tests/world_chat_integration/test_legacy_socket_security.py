"""Real legacy-route security regression: no bypass of chat-room role or sender."""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main
from modules.auth import create_access_token
from modules.hub import Hub


def token(user: str, role: str = 'guest') -> str:
    return create_access_token({'sub': user, 'role': role})


def receive_type(ws, typ: str, limit: int = 5):
    for _ in range(limit):
        message = ws.receive_json()
        if message.get('type') == typ:
            return message
    pytest.fail(f'{typ} not received after {limit} frames')


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    hub = Hub(tmp_path)
    # Exercise the actual exported route functions, without booting the whole
    # stateful app or writing to the owner's data directory.
    monkeypatch.setattr(main, 'hub', hub)
    monkeypatch.setattr(main, 'governance', None)
    app = FastAPI()
    app.add_api_websocket_route('/ws/control', main.control_websocket)
    app.add_api_websocket_route('/ws/{room}', main.websocket_room)
    return TestClient(app), hub


def ws_headers(user: str, role: str = 'guest'):
    return {'Authorization': 'Bearer ' + token(user, role)}


def reject(client, path, code=1008, headers=None):
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(path, headers=headers or {}) as ws:
            ws.receive_json()
    assert error.value.code == code


def test_enforced_legacy_requires_auth_and_blocks_unknown_private_and_world_rooms(legacy):
    client, hub = legacy
    guest = token('test-guest')
    for path in ('/ws/main', '/ws/studio', '/ws/control', '/ws/controlroom', '/ws/world',
                 '/ws/dm____test-guest____other', '/ws/private_unknown'):
        reject(client, path)
    # Production rejects query-string JWTs even when the credential itself is valid.
    for path in ('/ws/world?token=' + guest, '/ws/main?token=' + guest, '/ws/main?token=forged'):
        reject(client, path)
    # Role/room authorization is tested separately through the supported header transport.
    for path in ('/ws/world', '/ws/dm____test-guest____other', '/ws/studio', '/ws/control', '/ws/private_unknown'):
        reject(client, path, headers=ws_headers('test-guest'))
    assert not any(hub.rooms.values())
    assert list((hub.data_dir / 'logs').glob('*')) == [] if (hub.data_dir / 'logs').exists() else True


def test_legacy_role_and_authenticated_author_cannot_be_forged(legacy):
    client, hub = legacy
    actor = 'crew-' + uuid.uuid4().hex
    crew = token(actor, 'crew')
    with client.websocket_connect('/ws/studio?user_id=owner', headers=ws_headers(actor, 'crew')) as ws:
        receive_type(ws, 'presence')
        ws.send_json({'type': 'chat', 'text': '  authenticated speaker  ',
                      'user_id': 'owner', 'user': 'Owner', 'role': 'owner'})
        message = receive_type(ws, 'chat')['payload']
        assert message['text'] == '  authenticated speaker  '
        assert message['user_id'] == actor
        assert message['user'] == actor
        ws.send_json({'type': 'production_state', 'payload': {'on_air': True}})
        assert receive_type(ws, 'error')['payload']['msg'] == 'Production control requires mod or owner'
    history = __import__('asyncio').run(hub.get_recent_history('studio', 10))
    assert len(history) == 1
    assert history[0]['user_id'] == actor
    assert hub.get_production_state()['on_air'] is False


def test_legacy_owner_production_and_control_room_access(legacy):
    client, hub = legacy
    with client.websocket_connect('/ws/main', headers=ws_headers('owner', 'owner')) as ws:
        receive_type(ws, 'presence')
        ws.send_json({'type': 'production_state', 'payload': {'on_air': True}})
        assert receive_type(ws, 'production_state')['payload']['on_air'] is True
    with client.websocket_connect('/ws/control', headers=ws_headers('stage-tech', 'crew')) as ws:
        assert receive_type(ws, 'control_ready')['payload']['room'] == 'control'
        ws.send_json({'type': 'production_state', 'payload': {'on_air': False}})
        assert receive_type(ws, 'error')['payload']['msg'] == 'Production control requires mod or owner'
    assert hub.get_production_state()['on_air'] is True
    reject(client, '/ws/control?room=world', headers=ws_headers('owner', 'owner'))


def test_authenticated_legacy_payload_validation_and_local_dev_compatibility(legacy, monkeypatch):
    client, hub = legacy
    with client.websocket_connect('/ws/pub', headers=ws_headers('guest-1')) as ws:
        receive_type(ws, 'presence')
        for invalid in ('', '  ', None, ['not text'], 'x' * 10001):
            ws.send_json({'type': 'chat', 'text': invalid})
            assert receive_type(ws, 'error')['payload']['msg'] == 'Invalid chat text'
        ws.send_text('[1, 2, 3]')
        assert receive_type(ws, 'error')['payload']['msg'] == 'JSON object required'
    assert __import__('asyncio').run(hub.get_recent_history('pub')) == []
    # Historical stage pages connect without JWT when explicitly running the
    # local-development configuration. Do not silently break that workflow.
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '0')
    with client.websocket_connect('/ws/studio') as ws:
        assert receive_type(ws, 'presence')['payload']['room'] == 'studio'


def test_legacy_keyed_websocket_retry_is_durable_and_author_bound(legacy):
    """Actual legacy route must neither duplicate a lost reply nor trust frame actor."""
    client, hub = legacy
    sender = 'legacy-keyed-' + uuid.uuid4().hex
    key = str(uuid.uuid4())
    path = '/ws/main'
    headers = ws_headers(sender)
    with client.websocket_connect(path, headers=headers) as ws:
        receive_type(ws, 'presence')
        ws.send_json({'type': 'chat', 'text': '  original legacy payload  ',
                      'client_message_id': key, 'user_id': 'owner', 'user': 'Owner'})
        chat = receive_type(ws, 'chat')['payload']
        ack = receive_type(ws, 'chat_receipt')['payload']
        assert ack['duplicate'] is False
        assert chat['user_id'] == sender and chat['message_id'] == ack['message_id']
    with client.websocket_connect(path, headers=headers) as ws:
        receive_type(ws, 'history')
        receive_type(ws, 'presence')
        ws.send_json({'type': 'chat', 'text': '  original legacy payload  ', 'client_message_id': key})
        retry = receive_type(ws, 'chat_receipt')['payload']
        assert retry['duplicate'] is True and retry['message_id'] == ack['message_id']
        ws.send_json({'type': 'chat', 'text': 'malicious key conflict', 'client_message_id': key})
        assert 'different' in receive_type(ws, 'error')['payload']['msg']
    history = __import__('asyncio').run(hub.get_recent_history('main', 10))
    assert len(history) == 1 and history[0]['message_id'] == ack['message_id']
