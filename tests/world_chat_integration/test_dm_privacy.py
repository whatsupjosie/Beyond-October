"""Private DM notifications cannot escape into a public or legacy Hub room."""
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketState

from modules.auth import create_access_token
from modules.chat_rooms import create_chat_router
from modules.hub import Hub
from modules.route_security import current_identity


def headers(user: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + create_access_token({"sub": user, "role": "guest"})}


@pytest.fixture
def private_app(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    hub = Hub(tmp_path)
    recipients = []
    original_private = hub.send_private_event

    async def private(users, event):
        recipients.append((set(users), event))
        return await original_private(users, event)

    async def forbidden_global_broadcast(event):
        raise AssertionError("DM metadata was sent to the global room broadcast")

    monkeypatch.setattr(hub, "send_private_event", private)
    monkeypatch.setattr(hub, "broadcast_system_event", forbidden_global_broadcast)
    app = FastAPI()
    app.include_router(create_chat_router(hub, current_identity))
    return TestClient(app), recipients


def test_dm_request_accept_decline_do_not_broadcast_to_every_room(private_app):
    client, recipients = private_app
    run = uuid.uuid4().hex
    alice, bob, charlie = (f"{name}-{run}" for name in ("alice", "bob", "charlie"))
    assert client.post('/api/chat/dm/request', json={'to_user': bob}).status_code == 401
    requested = client.post('/api/chat/dm/request', json={
        'to_user': bob, 'message': 'A private invitation', 'from_user': charlie,
    }, headers=headers(alice))
    assert requested.status_code == 200
    req = requested.json()['request_id']
    assert recipients[-1][0] == {alice, bob}
    assert recipients[-1][1]['payload']['from_user'] == alice
    assert recipients[-1][1]['payload']['message'] == 'A private invitation'
    assert client.post(f'/api/chat/dm/accept/{req}', headers=headers(charlie)).status_code == 403
    assert client.post(f'/api/chat/dm/accept/{req}', headers=headers(bob)).status_code == 200
    assert recipients[-1][0] == {alice, bob}
    assert recipients[-1][1]['type'] == 'dm_accepted'

    pending = client.post('/api/chat/dm/request', json={
        'to_user': charlie, 'message': 'Not for everyone',
    }, headers=headers(alice))
    assert pending.status_code == 200
    assert client.post(f"/api/chat/dm/decline/{pending.json()['request_id']}",
                       headers=headers(charlie)).status_code == 200
    assert recipients[-1][0] == {alice, charlie}
    assert recipients[-1][1]['type'] == 'dm_declined'
    assert len(recipients) == 4


class Socket:
    application_state = WebSocketState.CONNECTED

    def __init__(self):
        self.received = []

    async def send_text(self, data):
        self.received.append(data)


def test_private_event_only_verified_addressees_even_with_shared_public_room(tmp_path):
    hub = Hub(tmp_path)
    alice, bob, bystander, impersonator = [Socket() for _ in range(4)]
    hub.rooms = {'world': {alice, bob, bystander, impersonator}, 'bar': {alice, bystander}}
    hub._ws_meta = {
        id(alice): {'uid': 'Alice', 'authenticated': True},
        id(bob): {'uid': 'bob', 'authenticated': True},
        id(bystander): {'uid': 'uninvited', 'authenticated': True},
        id(impersonator): {'uid': 'alice', 'authenticated': False},
    }
    event = {'type': 'dm_request', 'payload': {'message': 'confidential'}}
    delivered = asyncio.run(hub.send_private_event({'alice', 'BOB'}, event))
    assert delivered == 2
    assert len(alice.received) == len(bob.received) == 1
    assert 'confidential' in alice.received[0] and 'confidential' in bob.received[0]
    assert bystander.received == []
    assert impersonator.received == []
