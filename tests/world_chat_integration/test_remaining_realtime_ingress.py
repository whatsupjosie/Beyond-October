"""Real mounted socket handlers must not expose production state before auth."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import pytest

import main
from modules.auth import create_access_token
from modules.pubworld_router import router, _connected


def token(user: str, role: str = 'guest') -> str:
    return create_access_token({'sub': user, 'role': role})


def ws_headers(user: str, role: str = 'guest') -> dict:
    return {'Authorization': 'Bearer ' + token(user, role)}


def denied(client: TestClient, path: str, headers=None) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(path, headers=headers or {}) as ws:
            ws.receive_json()
    assert exc.value.code == 1008


class UnityBridgeProbe:
    def __init__(self):
        self.calls = 0

    async def handle_connection(self, ws):
        self.calls += 1
        await ws.accept()
        await ws.send_json({'type': 'state_sync', 'state': {'private': 'test'}})
        try:
            await ws.receive_text()
        except WebSocketDisconnect:
            pass


def test_actual_unity_and_alias_require_crew_before_state_sync(monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    probe = UnityBridgeProbe()
    monkeypatch.setattr(main, 'unity_bridge', probe)
    app = FastAPI()
    app.add_api_websocket_route('/unity/ws/{client_id}', main.unity_ws)
    app.add_api_websocket_route('/ws/unity', main.unity_ws_alias)
    client = TestClient(app)
    for path in ('/unity/ws/camera', '/ws/unity'):
        denied(client, path)
        denied(client, path, ws_headers('viewer'))
        denied(client, path + '?token=forged')
    assert probe.calls == 0
    for path in ('/unity/ws/camera', '/ws/unity'):
        with client.websocket_connect(path, headers=ws_headers('camera-operator', 'crew')) as ws:
            assert ws.receive_json() == {'type': 'state_sync', 'state': {'private': 'test'}}
    assert probe.calls == 2


def test_pubworld_map_socket_rejects_anonymous_before_registration(monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    denied(client, '/pubworld/ws')
    denied(client, '/pubworld/ws?token=forged')
    assert not _connected
    with client.websocket_connect('/pubworld/ws', headers=ws_headers('viewer')) as ws:
        assert len(_connected) == 1
        ws.send_text('ping')
        assert ws.receive_text() == 'pong'
        # The socket registration and real ping above demonstrate that the
        # authorization check does not break an authenticated map viewer.
    assert not _connected


def test_explicit_auth_off_development_keeps_local_realtime_compat(monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '0')
    probe = UnityBridgeProbe()
    monkeypatch.setattr(main, 'unity_bridge', probe)
    app = FastAPI()
    app.add_api_websocket_route('/unity/ws/{client_id}', main.unity_ws)
    app.include_router(router)
    client = TestClient(app)
    with client.websocket_connect('/unity/ws/dev') as ws:
        assert ws.receive_json()['type'] == 'state_sync'
    with client.websocket_connect('/pubworld/ws') as ws:
        ws.send_text('ping')
        assert ws.receive_text() == 'pong'
