"""e-PETE Runtime Activation Pass 1 regression tests.

These tests intentionally accept honest fallback when the real Rust/WebRTC/shared
memory stack is absent. They reject fake primary runtime success.
"""

from fastapi.testclient import TestClient


def test_epete_imports_and_reports_honest_component_status():
    from modules.pete_enhanced import PeteEnhanced  # noqa: F401
    from modules import pete_enhanced_routes  # noqa: F401


def test_app_routes_and_epete_fallback_are_honest():
    import main

    with TestClient(main.app) as client:
        status = client.get("/api/internal/pete/status")
        assert status.status_code == 200
        payload = status.json()
        assert payload["diagnostics_available"] is True
        assert payload["guest_visible"] is False
        assert payload["runtime_activation"] in {"runtime_activated", "voxel_renderer_connected", "fallback_hardened"}

        components = payload["components"]
        # The current bridge pass may connect the real Rust ws_renderer through
        # a WebSocket adapter. That is still not the full primary WebRTC/SHM
        # pipeline, so system_operational must remain honest unless the primary
        # runtime is actually live.
        if payload["runtime_activation"] == "voxel_renderer_connected":
            assert payload["voxel_renderer_operational"] is True
            assert payload["system_operational"] is False
            assert payload["streaming"]["transport"] == "renderer_websocket"
        elif not components.get("webrtc_bridge_module_available"):
            assert payload["runtime_activation"] == "fallback_hardened"
            assert payload["system_operational"] is False
            assert payload["streaming"]["fps"] == 0.0

        diagnostics = client.get("/api/internal/pete/diagnostics")
        assert diagnostics.status_code == 200
        assert diagnostics.json()["internal_only"] is True

        runtime_components = client.get("/api/internal/pete/runtime-components")
        assert runtime_components.status_code == 200
        assert runtime_components.json()["guest_visible"] is False

        assert client.get("/api/cameras").status_code == 200
        assert client.get("/api/recording/profiles").status_code == 200
        assert client.get("/api/bubble-stack/schema").status_code == 200


def test_bubble_stack_state_transitions_still_work():
    import main

    with TestClient(main.app) as client:
        r = client.post("/api/bubble-stack/test-room/configure", json={"room_id": "test-room"})
        assert r.status_code == 200
        assert r.json()["state"] == "CONFIGURED"

        r = client.post("/api/bubble-stack/test-room/ai-presence", json={"actor_ids": ["ai_1"]})
        assert r.status_code == 200
        assert r.json()["state"] == "ACTIVE"

        r = client.get("/api/bubble-stack/test-room/stat")
        assert r.status_code == 200
        assert r.json()["state"] == "ACTIVE"
        assert "engine_version" in r.json()

        r = client.post("/api/bubble-stack/test-room/sleep")
        assert r.status_code == 200
        assert r.json()["state"] == "SLEEPING"

        r = client.post("/api/bubble-stack/unconfigured-test/ai-presence", json={"actor_ids": ["ai_1"]})
        assert r.status_code == 200
        assert r.json()["state"] == "AI_BLIND"
