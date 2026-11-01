"""A mounted router must not bypass the identity/role policy of its main app.

Tests use ephemeral local FastAPI apps and data, not any owner installation.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from modules.auth import create_access_token
from modules.hub import Hub
from modules.structured_log_routes import router as log_router
from modules.stage_compat_routes import create_stage_compat_router
from modules.timeline_routes import router as timeline_router
from modules.pubcast_vision_routes import create_vision_router


def auth(role, user="participant"):
    return {"Authorization": "Bearer " + create_access_token({"sub": user, "role": role})}


def socket_headers(role, user="participant"):
    return auth(role, user)


def denied(client, path, headers=None):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(path, headers=headers or {}) as socket:
            socket.receive_json()
    assert exc.value.code == 1008


@pytest.fixture
def enforced(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")


def test_production_logs_rest_and_alternate_socket_require_security(enforced, monkeypatch):
    # The global production log is initialized by other full-app tests. Make
    # this local-router test independent of suite order: the successful
    # security-level handshake then returns a finite unavailable response.
    monkeypatch.setattr("modules.structured_log_routes.get_production_log", lambda: None)
    app = FastAPI()
    app.include_router(log_router)
    client = TestClient(app)
    for path in ("/api/logs/recent", "/api/logs/systems"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=auth("crew")).status_code == 403
        assert client.get(path, headers=auth("security")).status_code == 200
    denied(client, "/api/logs/ws")
    denied(client, "/api/logs/ws", socket_headers("guest"))
    denied(client, "/api/logs/ws", socket_headers("crew"))
    with client.websocket_connect("/api/logs/ws", headers=socket_headers("security")) as ws:
        assert ws.receive_json().get("error") == "Production log not initialized"


def test_standalone_stage_compat_requires_verified_identity_and_roles(enforced, tmp_path):
    app = FastAPI()
    hub = Hub(tmp_path)
    app.include_router(create_stage_compat_router(hub=hub))
    client = TestClient(app)
    for route in ("/api/state/production", "/api/switcher"):
        assert client.get(route).status_code == 401
        assert client.get(route, headers=auth("guest")).status_code == 403
        assert client.get(route, headers=auth("crew")).status_code == 200
        assert client.post(route, json={"on_air": True}).status_code == 401
        assert client.post(route, json={"on_air": True}, headers=auth("crew")).status_code == 403
    assert client.get("/api/state/user").status_code == 401
    assert client.get("/api/state/user", headers={**auth("guest", "real-user"),
                                              "X-Client-Id": "owner",
                                              "X-Display-Name": "The owner"}).json()["user"] == {
        "user_id": "real-user", "display_name": "real-user", "roles": [], "authenticated": True,
    }
    denied(client, "/ws/control")
    denied(client, "/ws/control", socket_headers("guest"))
    denied(client, "/ws/control?room=governance", socket_headers("owner"))
    with client.websocket_connect("/ws/control", headers=socket_headers("crew")) as ws:
        # A verified crew member can still use the historical control protocol.
        frame = ws.receive_json()
        assert frame.get("type") in ("presence", "control_ready")


def test_timeline_status_socket_requires_crew(enforced):
    app = FastAPI()
    app.include_router(timeline_router)
    client = TestClient(app)
    denied(client, "/api/timeline/ws")
    denied(client, "/api/timeline/ws", socket_headers("guest"))


class CameraProbe:
    def __init__(self):
        self.stream_clients = set()
        self.primary_camera = "a"
    async def add_stream_client(self, client):
        self.stream_clients.add(client)
    async def remove_stream_client(self, client):
        self.stream_clients.discard(client)
    def get_all_cameras_status(self):
        return {"cameras": [], "primary_camera": self.primary_camera}
    def set_primary_camera(self, camera):
        self.primary_camera = camera


def test_vision_stream_separates_view_from_camera_control(enforced):
    manager = CameraProbe()
    app = FastAPI()
    app.include_router(create_vision_router(manager))
    client = TestClient(app)
    denied(client, "/api/vision/stream")
    denied(client, "/api/vision/stream", socket_headers("guest"))
    with client.websocket_connect("/api/vision/stream", headers=socket_headers("crew")) as ws:
        ws.send_json({"type": "get_status"})
        assert ws.receive_json()["type"] == "status"
        ws.send_json({"type": "switch_camera", "camera_id": "b"})
        assert ws.receive_json()["type"] == "error"
        assert manager.primary_camera == "a"
    with client.websocket_connect("/api/vision/stream", headers=socket_headers("mod")) as ws:
        ws.send_json({"type": "switch_camera", "camera_id": "b"})
        assert ws.receive_json() == {"type": "camera_switched", "camera_id": "b"}
    assert manager.primary_camera == "b"
    assert not manager.stream_clients
