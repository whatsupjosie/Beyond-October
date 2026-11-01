"""Cross-transport keyed retries and bounded room history; real route and disk tests."""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.chat_rooms import create_chat_router, install_chat_websocket
from modules.hub import Hub
from modules.route_security import current_identity


def _client(hub):
    app = FastAPI()
    app.include_router(create_chat_router(hub, current_identity))
    install_chat_websocket(app, hub, current_identity)
    return TestClient(app)


def _uri():
    return '/ws/chat/world'


def _ws_headers(sender):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': sender, 'role': 'guest'})}


def _next_type(ws, typ):
    for _ in range(6):
        frame = ws.receive_json()
        if frame.get('type') == typ:
            return frame
    raise AssertionError(f'Never received expected {typ} frame')


def test_keyed_room_websocket_retry_is_one_persisted_message_after_reconnect(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    hub = Hub(tmp_path)
    seen = []

    async def callback(entry):
        seen.append(entry['message_id'])

    hub.on_chat_callback = callback
    key = str(uuid.uuid4())
    message = '  Exact text across a dropped response.\n'
    with _client(hub).websocket_connect(_uri(), headers=_ws_headers('alice')) as ws:
        _next_type(ws, 'presence')
        ws.send_json({'type': 'chat', 'text': message, 'client_message_id': key,
                      'user_id': 'owner', 'user': 'Forged owner'})
        first = _next_type(ws, 'chat')['payload']
        receipt = _next_type(ws, 'chat_receipt')['payload']
        assert receipt['message_id'] == first['message_id']
        assert receipt['duplicate'] is False
        assert first['user_id'] == 'alice' and first['text'] == message
    # A different hub/process now owns the connection; all receipt state is on disk.
    hub2 = Hub(tmp_path)
    hub2.on_chat_callback = callback
    with _client(hub2).websocket_connect(_uri(), headers=_ws_headers('alice')) as ws:
        _next_type(ws, 'history')
        _next_type(ws, 'presence')
        ws.send_json({'type': 'chat', 'text': message, 'client_message_id': key})
        second = _next_type(ws, 'chat_receipt')['payload']
        assert second['message_id'] == first['message_id']
        assert second['duplicate'] is True
        ws.send_json({'type': 'chat', 'text': 'changed text', 'client_message_id': key})
        assert 'different' in _next_type(ws, 'error')['message']
        ws.send_json({'type': 'chat', 'text': message, 'client_message_id': 'not-a-uuid'})
        assert 'UUID' in _next_type(ws, 'error')['message']
    history = asyncio.run(hub2.get_recent_history('world', 20))
    assert len(history) == 1 and history[0]['message_id'] == first['message_id']
    assert seen == [first['message_id']]


def test_keyed_websocket_and_rest_same_uuid_are_one_message(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    hub = Hub(tmp_path)
    client = _client(hub)
    key = str(uuid.uuid4())
    headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'writer', 'role': 'guest'})}
    receipt = client.post('/api/chat/rooms/world/send', headers=headers,
        json={'text': 'one across transports', 'client_message_id': key})
    assert receipt.status_code == 200 and receipt.json()['duplicate'] is False
    with client.websocket_connect(_uri(), headers=_ws_headers('writer')) as ws:
        _next_type(ws, 'history')
        _next_type(ws, 'presence')
        ws.send_json({'type': 'chat', 'text': 'one across transports', 'client_message_id': key})
        replay = _next_type(ws, 'chat_receipt')['payload']
        assert replay['duplicate'] is True
        assert replay['message_id'] == receipt.json()['message_id']
    assert len(asyncio.run(hub.get_recent_history('world', 10))) == 1


def test_room_join_reads_bounded_tail_not_entire_archive(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    hub = Hub(tmp_path)
    path = tmp_path / 'logs' / 'world.jsonl'
    path.parent.mkdir(parents=True)
    with path.open('w', encoding='utf-8') as stream:
        for i in range(1003):
            stream.write(json.dumps({'message_id': str(i), 'text': f'line {i}',
                                     'room': 'world', 'user_id': 'alice'}) + '\n')
    # If connect() regresses to readlines() on the complete archive this test
    # will not see the tail-reader call and must fail, rather than pass on size.
    original = Hub._read_history_sync
    seen = []

    def bounded(self, filename: Path, limit: int):
        seen.append((filename, limit))
        return original(self, filename, limit)

    monkeypatch.setattr(Hub, '_read_history_sync', bounded)
    with _client(hub).websocket_connect(_uri(), headers=_ws_headers('alice')) as ws:
        frame = _next_type(ws, 'history')['payload']
        assert len(frame) == 50
        assert frame[0]['message_id'] == '953'
        assert frame[-1]['message_id'] == '1002'
    assert seen and seen[0] == (path, 50)
