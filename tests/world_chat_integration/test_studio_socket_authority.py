"""Dedicated studio and log sockets must not bypass room-role security."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main
from modules.auth import create_access_token


def socket_headers(role: str):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': 'test-'+role, 'role': role})}


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    application = FastAPI()
    application.add_api_websocket_route('/studio/ws', main.studio_control_ws)
    application.add_api_websocket_route('/ws/studio', main.studio_control_ws_alias)
    application.add_api_websocket_route('/api/logs/ws', main.logs_websocket_direct)
    return TestClient(application)


def denied(app, route, headers=None):
    with pytest.raises(WebSocketDisconnect) as failure:
        with app.websocket_connect(route, headers=headers or {}) as socket:
            socket.receive_json()
    assert failure.value.code == 1008


def test_studio_control_both_routes_reject_anonymous_and_guest_before_initial_state(app):
    for route in ('/ws/studio', '/studio/ws'):
        denied(app, route)
        denied(app, route, socket_headers('guest'))
        denied(app, route, socket_headers('friend'))


def test_production_logs_are_private_and_cannot_be_seen_by_unverified_role(app):
    denied(app, '/api/logs/ws')
    denied(app, '/api/logs/ws', socket_headers('guest'))
    denied(app, '/api/logs/ws', socket_headers('crew'))
    denied(app, '/api/logs/ws?token=invalid')
