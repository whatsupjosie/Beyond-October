"""e-PETE ↔ voxel renderer bridge pass 1 tests.

These tests prove the current build connects e-PETE to the real Rust
``bin/ws_renderer`` WebSocket adapter without pretending that full WebRTC,
shared-memory, or physics consequence routing is already finished.
"""

from fastapi.testclient import TestClient


def test_renderer_bridge_modules_import():
    from modules.voxel_webrtc_bridge import VoxelWebRTCBridge  # noqa: F401
    from modules.pubcast_voxel_integration import PubCastVoxelIntegration  # noqa: F401
    from modules.pete_enhanced import PeteEnhanced  # noqa: F401


def test_app_connects_epete_to_real_voxel_renderer_honestly():
    import main

    with TestClient(main.app) as client:
        status = client.get("/api/internal/pete/status")
        assert status.status_code == 200
        payload = status.json()

        assert payload["guest_visible"] is False
        assert payload["diagnostics_available"] is True
        assert payload["runtime_activation"] in {
            "runtime_activated",
            "voxel_renderer_connected",
            "fallback_hardened",
        }

        components = payload["components"]
        assert components["renderer_websocket_adapter_available"] is True
        assert components["rust_renderer_binary_exists"] is True
        assert components["rust_renderer_binary_executable"] is True

        # Current pass goal: connect e-PETE to the existing Rust ws_renderer.
        assert payload["runtime_activation"] == "voxel_renderer_connected"
        assert payload["voxel_renderer_operational"] is True
        assert payload["rust_engine"]["alive"] is True
        assert payload["streaming"]["transport"] == "renderer_websocket"
        assert payload["streaming"]["renderer_connected"] is True
        assert payload["streaming"]["fps"] > 0

        # Still honest: not full browser WebRTC / SHM / primary pipeline yet.
        assert payload["system_operational"] is False
        assert payload["streaming"]["webrtc_signaling_available"] is False
        assert payload["streaming"]["shared_memory_available"] is False
        assert components["shared_memory_path_available"] is False
        assert components["physics_consequence_hooks_available"] is False


def test_existing_core_routes_survive_voxel_bridge_activation():
    import main

    with TestClient(main.app) as client:
        assert client.get("/api/cameras").status_code == 200
        assert client.get("/api/recording/profiles").status_code == 200
        assert client.get("/api/bubble-stack/schema").status_code == 200

        r = client.post("/api/bubble-stack/voxel-bridge-room/configure", json={"room_id": "voxel-bridge-room"})
        assert r.status_code == 200
        assert r.json()["state"] == "CONFIGURED"

        r = client.post("/api/bubble-stack/voxel-bridge-room/ai-presence", json={"actor_ids": ["ai_1"]})
        assert r.status_code == 200
        assert r.json()["state"] == "ACTIVE"

        r = client.post("/api/bubble-stack/unconfigured-voxel-bridge/ai-presence", json={"actor_ids": ["ai_1"]})
        assert r.status_code == 200
        assert r.json()["state"] == "AI_BLIND"
