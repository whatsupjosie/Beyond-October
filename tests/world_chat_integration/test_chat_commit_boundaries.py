"""A failed downstream AI/witness cannot turn persisted user text into a fake send failure."""
from __future__ import annotations

import asyncio
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.chat_rooms import create_chat_router
from modules.hub import Hub
from modules.route_security import current_identity


def test_http_receipt_reports_postcommit_failures_without_retry_trap(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    hub = Hub(tmp_path)

    class FailedWitness:
        def record_event(self, *args, **kwargs):
            raise RuntimeError('intentional test failure: witness offline')

    hub.blackbox_witness = FailedWitness()
    seen = []

    async def failed_ai(message):
        seen.append(message['message_id'])
        raise RuntimeError('intentional test failure: AI offline')

    hub.on_chat_callback = failed_ai
    app = FastAPI()
    app.include_router(create_chat_router(hub, current_identity))
    client = TestClient(app)
    token = create_access_token({'sub': 'sender', 'role': 'guest'})
    original = '  User text was saved, NOT an error.  \n'
    reply = client.post('/api/chat/rooms/world/send', json={'text': original},
                        headers={'Authorization': 'Bearer ' + token})
    assert reply.status_code == 200
    result = reply.json()
    assert result['ok'] is True and result['text'] == original
    assert uuid.UUID(result['message_id']).version == 4
    assert len(result['warnings']) == 2
    assert 'BlackBox' in result['warnings'][0] and 'AI response' in result['warnings'][1]
    history = asyncio.run(hub.get_recent_history('world', 10))
    assert len(history) == 1 and history[0]['text'] == original
    assert history[0]['message_id'] == result['message_id']
    assert seen == [result['message_id']]


def test_witness_receipt_and_no_ai_callback_still_acknowledge_message(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    hub = Hub(tmp_path)
    witnesses = []

    class SuccessfulWitness:
        def record_event(self, *args, **kwargs):
            witnesses.append((args, kwargs))
            return 'test-witness-id'

    hub.blackbox_witness = SuccessfulWitness()
    app = FastAPI()
    app.include_router(create_chat_router(hub, current_identity))
    reply = TestClient(app).post('/api/chat/rooms/world/send', json={'text': 'no AI needed'},
        headers={'Authorization': 'Bearer ' + create_access_token({'sub': 'sender', 'role': 'guest'})})
    assert reply.status_code == 200
    assert reply.json()['warnings'] == []
    assert witnesses[0][1]['data']['message_id'] == reply.json()['message_id']
