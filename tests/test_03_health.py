"""
test_03_health.py — HTTP endpoint smoke tests (post-startup)
════════════════════════════════════════════════════════════
Every endpoint tested here runs against the fully-booted app (lifespan
complete). Tests verify:
  - Status codes are correct (200, not 500/503)
  - Response JSON has the expected top-level shape
  - No endpoint crashes the server (no unhandled exceptions)

These are smoke tests — we're not testing business logic, we're verifying
the startup left every endpoint in a working state.
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1. The health endpoint — ground truth
# ─────────────────────────────────────────────────────────────────────────────

def test_health_returns_200(client):
    r = client.get("/api/health")
    assert r.status_code == 200

def test_health_status_ok(client):
    r = client.get("/api/health")
    body = r.json()
    assert body.get("status") == "ok", f"Expected status=ok, got: {body}"

def test_health_has_timestamp(client):
    r = client.get("/api/health")
    assert "timestamp" in r.json()

def test_health_has_cameras(client):
    r = client.get("/api/health")
    assert "cameras" in r.json()

def test_health_has_ai_providers(client):
    r = client.get("/api/health")
    assert "ai_providers" in r.json()

def test_health_has_ws_rooms(client):
    r = client.get("/api/health")
    assert "ws_rooms" in r.json()

def test_health_ai_providers_shape(client):
    providers = client.get("/api/health").json()["ai_providers"]
    for key in ("anthropic", "openai", "gemini"):
        assert key in providers, f"ai_providers missing key: {key}"
        assert isinstance(providers[key], bool)


# ─────────────────────────────────────────────────────────────────────────────
# 2. New service health endpoints
# ─────────────────────────────────────────────────────────────────────────────

def test_jeremy_health_200(client):
    r = client.get("/api/jeremy/health")
    assert r.status_code == 200, f"Jeremy Cricket health check failed: {r.text}"

def test_jeremy_health_has_characters(client):
    r = client.get("/api/jeremy/health")
    assert "characters" in r.json(), "Jeremy health response missing 'characters' key"


def test_active_room_conductor_has_stats(client):
    r = client.get("/api/internal/room-conductor/status")
    assert r.status_code == 200, f"Active room-conductor diagnostics failed: {r.text}"
    assert isinstance(r.json().get("stats"), dict)

def test_health_breakers_200(client):
    r = client.get("/api/health/breakers")
    assert r.status_code == 200, f"Circuit breaker health check failed: {r.text}"

def test_health_breakers_shape(client):
    r = client.get("/api/health/breakers")
    assert "breakers" in r.json()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Camera system
# ─────────────────────────────────────────────────────────────────────────────

def test_cameras_200(client):
    r = client.get("/api/cameras")
    assert r.status_code == 200, f"Camera list failed: {r.text}"

def test_cameras_has_sources(client):
    r = client.get("/api/cameras")
    assert "cameras" in r.json()

def test_cameras_program_200(client):
    r = client.get("/api/cameras/program")
    assert r.status_code == 200

def test_cameras_preview_200(client):
    r = client.get("/api/cameras/preview")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 4. Recording system
# ─────────────────────────────────────────────────────────────────────────────

def test_recording_profiles_200(client):
    r = client.get("/api/recording/profiles")
    assert r.status_code == 200

def test_recording_profiles_has_three(client):
    r = client.get("/api/recording/profiles")
    profiles = r.json().get("profiles", [])
    assert len(profiles) >= 3, f"Expected ≥3 encoding profiles, got {len(profiles)}"

def test_recording_sessions_200(client):
    r = client.get("/api/recording/sessions")
    assert r.status_code == 200

def test_recording_storage_200(client):
    r = client.get("/api/recording/storage")
    assert r.status_code == 200

def test_recording_privacy_200(client):
    r = client.get("/api/recording/privacy")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 5. Avatar system
# ─────────────────────────────────────────────────────────────────────────────

def test_avatar_presets_200(client):
    r = client.get("/api/avatars/presets")
    assert r.status_code == 200

def test_avatar_presets_has_presets(client):
    r = client.get("/api/avatars/presets")
    assert "presets" in r.json()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Production state
# ─────────────────────────────────────────────────────────────────────────────

def test_production_state_get_200(client):
    r = client.get("/api/state/production")
    assert r.status_code == 200

def test_production_state_post_200(client):
    r = client.post("/api/state/production", json={"mode": "LIVE"})
    assert r.status_code == 200
    # The endpoint returns the updated production-state dict directly
    # (not an {"ok": true} wrapper) — verify the posted field actually
    # landed in the returned state.
    assert r.json().get("mode") == "LIVE"


# ─────────────────────────────────────────────────────────────────────────────
# 7. PubWorld voxel system
# ─────────────────────────────────────────────────────────────────────────────

def test_pubworld_scenes_200(client):
    r = client.get("/api/pubworld/scenes")
    assert r.status_code == 200

def test_pubworld_props_200(client):
    r = client.get("/api/pubworld/props")
    assert r.status_code == 200

def test_pubworld_prototypes_200(client):
    r = client.get("/api/pubworld/prototypes")
    assert r.status_code == 200

def test_pubworld_generate_status_200(client):
    r = client.get("/api/pubworld/generate/status")
    assert r.status_code == 200

def test_pubworld_presets_200(client):
    r = client.get("/api/pubworld/builder/presets")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 8. Studio Control Room
# ─────────────────────────────────────────────────────────────────────────────

def test_studio_status_200(client):
    r = client.get("/api/studio/status")
    assert r.status_code == 200, f"Studio status failed: {r.text}"

def test_studio_status_has_state(client):
    r = client.get("/api/studio/status")
    assert "state" in r.json()


# ─────────────────────────────────────────────────────────────────────────────
# 9. Performer / Rust bridge status (graceful even if Rust not running)
# ─────────────────────────────────────────────────────────────────────────────

def test_performer_status_200(client):
    r = client.get("/api/performer/status")
    assert r.status_code == 200

def test_performer_status_has_running(client):
    r = client.get("/api/performer/status")
    assert "running" in r.json()


# ─────────────────────────────────────────────────────────────────────────────
# 10. Unity bridge
# ─────────────────────────────────────────────────────────────────────────────

def test_unity_status_200(client):
    r = client.get("/api/unity/status")
    assert r.status_code == 200, f"Unity status failed: {r.text}"

def test_unity_world_brain_200(client):
    r = client.get("/api/unity/world-brain")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 11. Lighting system
# ─────────────────────────────────────────────────────────────────────────────

def test_lighting_presets_200(client):
    r = client.get("/api/lighting/presets")
    assert r.status_code == 200

def test_lighting_active_200(client):
    r = client.get("/api/lighting/active")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 12. Voxel assets
# ─────────────────────────────────────────────────────────────────────────────

def test_voxel_assets_200(client):
    r = client.get("/api/voxel/assets")
    assert r.status_code == 200

# NOTE: there is no separate "voxel scenes" concept distinct from PubWorld
# scenes anywhere in the codebase — /api/pubworld/scenes (tested above under
# section 7) is the real, single scene store. A stale test_voxel_scenes_200
# targeting a nonexistent /api/voxel/scenes route was removed.


# ─────────────────────────────────────────────────────────────────────────────
# 13. Engine and bridge status
# ─────────────────────────────────────────────────────────────────────────────

def test_engine_status_200(client):
    r = client.get("/api/engine/status")
    assert r.status_code == 200

def test_bridge_status_200(client):
    r = client.get("/api/bridge/status")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 14. Mic pipeline (router-mounted)
# ─────────────────────────────────────────────────────────────────────────────

def test_mic_cough_status_200(client):
    r = client.get("/api/mic/cough/status")
    assert r.status_code == 200

def test_mic_profiles_get_200(client):
    r = client.get("/api/mic/profiles")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 15. Audio devices (router-mounted)
# ─────────────────────────────────────────────────────────────────────────────

def test_audio_devices_200(client):
    r = client.get("/api/audio/devices")
    # May be 200 (devices found) or 200 with empty list if no audio hardware
    assert r.status_code == 200

def test_audio_devices_active_200(client):
    r = client.get("/api/audio/devices/active")
    assert r.status_code == 200

def test_audio_install_guide_200(client):
    r = client.get("/api/audio/devices/install-guide")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 16. Page routes — all HTML pages must return 200
# ─────────────────────────────────────────────────────────────────────────────

PAGE_ROUTES = [
    "/", "/control", "/stage", "/dressing", "/dressing-foundry",
    "/bar", "/world", "/builder", "/gallery", "/analytics",
    "/launch", "/byok", "/studio",
]

@pytest.mark.parametrize("path", PAGE_ROUTES)
def test_page_route_returns_200(client, path):
    r = client.get(path)
    assert r.status_code == 200, f"Page {path} returned {r.status_code} — template may be missing"


# ─────────────────────────────────────────────────────────────────────────────
# 17. User identity endpoint
# ─────────────────────────────────────────────────────────────────────────────

def test_api_me_200(client):
    r = client.get("/api/me")
    assert r.status_code == 200

def test_api_me_has_user_id(client):
    r = client.get("/api/me")
    assert "user_id" in r.json()

def test_state_user_get_200(client):
    r = client.get("/api/state/user")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 18. PubWorld router state (pubworld prefix)
# ─────────────────────────────────────────────────────────────────────────────

def test_pubworld_state_200(client):
    r = client.get("/pubworld/state")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 19. Choreo controller
# ─────────────────────────────────────────────────────────────────────────────

def test_choreo_status_200(client):
    r = client.get("/api/choreo/status")
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 20. VOD and upload system
# ─────────────────────────────────────────────────────────────────────────────

def test_vod_list_200(client):
    r = client.get("/api/vod")
    assert r.status_code == 200
    assert "files" in r.json()
