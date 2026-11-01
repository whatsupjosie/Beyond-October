from __future__ import annotations

from math import inf, nan

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules import bubble_routes
from modules.bubble_stack import BubbleGridConfig, BubbleStack


def _token(user_id: str, role: str) -> str:
    return create_access_token({"sub": user_id, "role": role})


@pytest.fixture(autouse=True)
def _clear_stacks():
    bubble_routes._stacks.clear()
    yield
    bubble_routes._stacks.clear()


def test_bubble_read_routes_remain_public_but_mutations_require_mod(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    app = FastAPI()
    app.include_router(bubble_routes.router)

    with TestClient(app) as client:
        assert client.get("/api/bubble-stack/schema").status_code == 200

        missing = client.post(
            "/api/bubble-stack/secure-room/configure",
            json={"room_id": "secure-room"},
        )
        assert missing.status_code == 401

        guest = client.post(
            "/api/bubble-stack/secure-room/configure",
            json={"room_id": "secure-room"},
            headers={"Authorization": f"Bearer {_token('guest-user', 'guest')}"},
        )
        assert guest.status_code == 403

        mod = client.post(
            "/api/bubble-stack/secure-room/configure",
            json={"room_id": "secure-room"},
            headers={"Authorization": f"Bearer {_token('mod-user', 'mod')}"},
        )
        assert mod.status_code == 200
        assert mod.json()["state"] == "CONFIGURED"


def test_bubble_relaxed_mode_preserves_existing_local_workflow(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    app = FastAPI()
    app.include_router(bubble_routes.router)

    with TestClient(app) as client:
        configured = client.post(
            "/api/bubble-stack/dev-room/configure",
            json={"room_id": "dev-room"},
        )
        assert configured.status_code == 200

        active = client.post(
            "/api/bubble-stack/dev-room/ai-presence",
            json={"actor_ids": ["ai-1"]},
        )
        assert active.status_code == 200
        assert active.json()["state"] == "ACTIVE"


def test_bubble_grid_rejects_non_finite_geometry():
    bad_configs = [
        BubbleGridConfig(room_id="bad", dimensions=(inf, 3.0, 10.0)),
        BubbleGridConfig(room_id="bad", origin=(nan, 0.0, 0.0)),
        BubbleGridConfig(room_id="bad", radius=inf),
        BubbleGridConfig(room_id="bad", spacing=nan),
    ]
    for config in bad_configs:
        with pytest.raises(ValueError, match="must be finite"):
            BubbleStack(config)


def test_bubble_grid_limit_blocks_eager_allocation_and_is_overrideable(monkeypatch):
    config = BubbleGridConfig(
        room_id="dense-room",
        dimensions=(10.0, 3.0, 10.0),
        spacing=0.5,
        radius=0.5,
    )
    assert config.estimated_bubble_count_upper_bound() == 3087

    monkeypatch.setenv("PUBCAST_BUBBLE_MAX_CELLS", "1000")
    with pytest.raises(ValueError, match="exceeds safe eager-grid limit"):
        BubbleStack(config)

    monkeypatch.setenv("PUBCAST_BUBBLE_MAX_CELLS", "4000")
    stack = BubbleStack(config)
    assert len(stack.bubbles) == 3087


def test_configure_route_returns_422_for_resource_unsafe_grid(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    monkeypatch.setenv("PUBCAST_BUBBLE_MAX_CELLS", "1000")
    app = FastAPI()
    app.include_router(bubble_routes.router)

    with TestClient(app) as client:
        response = client.post(
            "/api/bubble-stack/dense/configure",
            json={
                "room_id": "dense",
                "dimensions": [10.0, 3.0, 10.0],
                "spacing": 0.5,
                "radius": 0.5,
            },
        )
        assert response.status_code == 422
        assert "safe eager-grid limit" in response.json()["detail"]
        assert "dense" not in bubble_routes._stacks
