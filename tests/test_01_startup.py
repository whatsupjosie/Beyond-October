"""
test_01_startup.py — Lifespan boot sequence and service initialisation
═══════════════════════════════════════════════════════════════════════
These tests run the REAL lifespan via TestClient and verify that every
service the app depends on is properly initialised before the server
accepts traffic. A test failure here means a service is None when it
should have a live instance — which causes 503s or AttributeErrors in
production.

Tests are ordered from lowest-level (Hub) to orchestration and studio services
matching the actual startup sequence in main.py.
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Core singletons — must be non-None after lifespan
# ─────────────────────────────────────────────────────────────────────────────

def test_hub_initialised(main_module):
    """Hub is the backbone. Everything else depends on it."""
    assert main_module.hub is not None, \
        "hub is None after startup — nothing can broadcast or receive WebSocket messages"


def test_camera_manager_initialised(main_module):
    assert main_module.cam is not None, \
        "CameraManager is None — /api/cameras/* will all return 503"


def test_recording_service_initialised(main_module):
    assert main_module.rec is not None, \
        "RecordingService is None — /api/recording/* will all return 503"


def test_bot_manager_initialised(main_module):
    assert main_module.bot_mgr is not None, \
        "BotManager is None — /api/bots/* will all return errors"


def test_room_manager_initialised(main_module):
    assert main_module.room_mgr is not None, \
        "RoomManager is None — room lifecycle is broken"


def test_credential_store_initialised(main_module):
    assert main_module.cred_store is not None, \
        "CredentialStore is None — /api/credentials/* will all fail"


def test_byok_manager_initialised(main_module):
    assert main_module.byok_mgr is not None, \
        "BYOKManager is None — BYOK key management is broken"


# ─────────────────────────────────────────────────────────────────────────────
# New services (3/18 additions)
# ─────────────────────────────────────────────────────────────────────────────

def test_jeremy_cricket_initialised(main_module):
    """CricketKeeper provides per-character persistent memory for bots."""
    assert main_module.cricket_keeper is not None, \
        "CricketKeeper is None — bot memory system is offline"


def test_sir_purfluous_character_registry_available(main_module):
    """The canonical story registry exposes Sir Purfluous as a character."""
    from modules.pubcast_story_bible import CHARACTER_ROOTS
    assert "sir_purfluous" in CHARACTER_ROOTS


# ─────────────────────────────────────────────────────────────────────────────
# Studio and rendering services
# ─────────────────────────────────────────────────────────────────────────────

def test_studio_control_initialised(main_module):
    assert main_module.studio_ctrl is not None, \
        "StudioControl is None — /api/studio/* and /ws/studio will fail"


def test_studio_ws_handler_initialised(main_module):
    """Without this, /ws/studio closes every connection with 1013."""
    assert main_module.studio_ws_handler is not None, \
        "studio_ws_handler is None — Studio Control Room WebSocket is dead"


def test_voxel_asset_manager_initialised(main_module):
    assert main_module.voxel_asset_mgr is not None, \
        "VoxelAssetManager is None — /api/voxel/* will return 503"


def test_unity_bridge_initialised(main_module):
    assert main_module.unity_bridge_mgr is not None, \
        "UnityBridge is None — /ws/unity and /api/unity/* will fail"


# ─────────────────────────────────────────────────────────────────────────────
# Wiring between services
# ─────────────────────────────────────────────────────────────────────────────

def test_hub_has_chat_callback(main_module):
    """The on_chat_callback must be set so legitimate chat turns reach bots."""
    assert callable(main_module.hub.on_chat_callback), \
        "hub.on_chat_callback is not set — chat messages will not trigger bots"


def test_bot_manager_knows_hub(main_module):
    """BotManager needs the hub to broadcast replies."""
    assert main_module.bot_mgr.hub is main_module.hub, \
        "BotManager.hub is not the same hub instance — bot replies will not broadcast"


def test_bot_manager_has_cricket_keeper(main_module):
    """BotManager must have the CricketKeeper injected so memory enrichment works."""
    assert main_module.bot_mgr._cricket_keeper is main_module.cricket_keeper, \
        "BotManager._cricket_keeper is not set — bot memory is offline"


def test_bot_manager_has_byok_manager(main_module):
    assert main_module.bot_mgr._byok_mgr is main_module.byok_mgr, \
        "BotManager._byok_mgr is not set — BYOK credential lookup for bots will fail"


def test_hub_stored_on_app_state(main_module):
    """mic_routes and audio_devices access hub via request.app.state.hub."""
    assert main_module.app.state.hub is main_module.hub, \
        "app.state.hub is not set — mic cough broadcast and audio device routes will fail"


def test_data_dir_stored_on_app_state(main_module):
    """mic_routes and audio_devices access data_dir via request.app.state.data_dir."""
    assert hasattr(main_module.app.state, "data_dir"), \
        "app.state.data_dir is not set — mic profile storage will fail"


def test_conductor_has_hub(main_module):
    conductor = getattr(main_module.app.state, "room_conductor", None)
    assert conductor is not None, "Active room conductor failed to start"
    assert conductor._hub is main_module.hub, \
        "RoomConductor._hub is not the live hub"


def test_conductor_has_bot_manager(main_module):
    conductor = getattr(main_module.app.state, "room_conductor", None)
    assert conductor is not None, "Active room conductor failed to start"
    assert conductor._bm is main_module.bot_mgr, \
        "RoomConductor is not wired to the live bot manager"


# ─────────────────────────────────────────────────────────────────────────────
# Avatar performer — graceful degradation (Rust bridge may not be running)
# ─────────────────────────────────────────────────────────────────────────────

def test_performer_manager_initialised(main_module):
    """AvatarPerformerManager must be created even if Rust crate is absent."""
    assert main_module.performer_mgr is not None, \
        "AvatarPerformerManager is None — /api/performer/* will return 503"


def test_performer_manager_fails_gracefully_without_rust(main_module):
    """If Rust bridge isn't running, performer_mgr should still exist (fallback mode)."""
    # _running=False is acceptable; the manager must exist so endpoints can report status.
    assert hasattr(main_module.performer_mgr, "_running"), \
        "AvatarPerformerManager missing _running attribute — startup did not complete correctly"


# ─────────────────────────────────────────────────────────────────────────────
# Startup order: hub must exist before dependent services
# ─────────────────────────────────────────────────────────────────────────────

def test_hub_initialised_before_bot_manager(main_module):
    """If BotManager exists, hub must too — ordering guarantee."""
    if main_module.bot_mgr is not None:
        assert main_module.hub is not None, \
            "BotManager exists but hub is None — startup order is broken"


def test_cricket_keeper_initialised_before_injection(main_module):
    """cricket_keeper must be initialised before being injected into bot_mgr."""
    assert main_module.cricket_keeper is not None
    assert main_module.bot_mgr._cricket_keeper is not None


# ─────────────────────────────────────────────────────────────────────────────
# Recording profiles — must be registered at startup
# ─────────────────────────────────────────────────────────────────────────────

def test_recording_profiles_registered(main_module):
    """Four encoding profiles must be registered: broadcast_mp4, prores_hq, web_stream, audio_only."""
    profiles = {p.profile_id for p in main_module.rec.list_profiles()}
    assert "broadcast_mp4" in profiles, "broadcast_mp4 encoding profile not registered"
    assert "prores_hq"     in profiles, "prores_hq encoding profile not registered"
    assert "web_stream"    in profiles, "web_stream encoding profile not registered"
    assert "audio_only"    in profiles, "audio_only encoding profile not registered"


# ─────────────────────────────────────────────────────────────────────────────
# Shutdown (implicit — if TestClient context exits cleanly, shutdown ran)
# ─────────────────────────────────────────────────────────────────────────────

def test_lifespan_runs_without_exception(client):
    """If we got here, the lifespan completed without raising. Belt-and-suspenders check."""
    # A health check after full startup
    r = client.get("/api/health")
    assert r.status_code == 200, \
        f"Health check failed post-startup: {r.status_code} {r.text}"
    assert r.json()["status"] == "ok"
