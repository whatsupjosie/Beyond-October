"""PubWorld's dedicated socket cannot bypass the enforced-auth entry boundary."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main
from modules.auth import create_access_token


def token(username: str, role: str = 'guest') -> str:
    return create_access_token({'sub': username, 'role': role})


@pytest.fixture
def world_app(monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    app = FastAPI()
    app.add_api_websocket_route('/pubworld/ws/{client_id}', main.pubworld_ws)
    return TestClient(app)


def reject(client, path, first_message=None, expected_code=4401):
    with pytest.raises(WebSocketDisconnect) as failure:
        with client.websocket_connect(path) as socket:
            if first_message is not None:
                socket.send_json(first_message)
            response = socket.receive_json()
            assert response.get("type") == "auth_error"
            socket.receive_json()
    assert failure.value.code == expected_code


def test_pubworld_requires_in_band_identity_and_rejects_path_tricks(world_app):
    reject(world_app, '/pubworld/ws/pw_guest', {'type':'ping'})
    reject(world_app, '/pubworld/ws/pw_guest?token='+token('guest'), {'type':'ping'})
    with pytest.raises(WebSocketDisconnect) as invalid_path:
        with world_app.websocket_connect('/pubworld/ws/pw_guest.bad') as socket:
            socket.receive_json()
    assert invalid_path.value.code == 1008

    with world_app.websocket_connect('/pubworld/ws/pw_guest') as socket:
        socket.send_json({'type':'auth','token':token('guest')})
        assert socket.receive_json()['type'] == 'auth_ok'
        assert socket.receive_json()['type'] == 'welcome'
        socket.send_json(['not', 'an', 'event'])
        assert socket.receive_json()['type'] == 'error'
        socket.send_json({'type':'ping'})
        assert socket.receive_json()['type'] == 'pong'


def test_pubworld_client_id_collision_is_rejected_without_evicting_original(world_app):
    with world_app.websocket_connect('/pubworld/ws/pw_unique') as first:
        first.send_json({'type':'auth','token':token('first')})
        assert first.receive_json()['type']=='auth_ok'
        assert first.receive_json()['type']=='welcome'
        with pytest.raises(WebSocketDisconnect) as collision:
            with world_app.websocket_connect('/pubworld/ws/pw_unique') as second:
                second.send_json({'type':'auth','token':token('second')})
                assert second.receive_json()['type']=='auth_ok'
                second.receive_json()
        assert collision.value.code == 1008
        first.send_json({'type':'ping'})
        assert first.receive_json()['type']=='pong'
    with world_app.websocket_connect('/pubworld/ws/pw_unique') as second:
        second.send_json({'type':'auth','token':token('second')})
        assert second.receive_json()['type']=='auth_ok'
        assert second.receive_json()['type']=='welcome'
