"""
test_05_services.py — Service interface contracts
══════════════════════════════════════════════════
Verifies that each service object has the exact methods and attributes
that the rest of the system calls on it. These tests catch the class
of bug where a service is initialised but its interface changed
(renamed method, removed attribute) without updating callers.

Think of these as compile-time checks that Python can't do for us.
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Hub interface
# ─────────────────────────────────────────────────────────────────────────────

def test_hub_has_connect(main_module):
    assert callable(getattr(main_module.hub, "connect", None))

def test_hub_has_disconnect(main_module):
    assert callable(getattr(main_module.hub, "disconnect", None))

def test_hub_has_handle_message(main_module):
    assert callable(getattr(main_module.hub, "handle_message", None))

def test_hub_has_broadcast_system_event(main_module):
    assert callable(getattr(main_module.hub, "broadcast_system_event", None))

def test_hub_has_broadcast_presence_update(main_module):
    assert callable(getattr(main_module.hub, "broadcast_presence_update", None))

def test_hub_has_post_chat_message(main_module):
    assert callable(getattr(main_module.hub, "post_chat_message", None))

def test_hub_has_get_production_state(main_module):
    assert callable(getattr(main_module.hub, "get_production_state", None))

def test_hub_has_update_production_state(main_module):
    assert callable(getattr(main_module.hub, "update_production_state", None))

def test_hub_has_rooms(main_module):
    assert hasattr(main_module.hub, "rooms")
    assert isinstance(main_module.hub.rooms, dict)

def test_hub_has_is_user_in_room(main_module):
    assert callable(getattr(main_module.hub, "is_user_in_room", None))

def test_hub_has_get_recent_history(main_module):
    assert callable(getattr(main_module.hub, "get_recent_history", None))

def test_hub_on_chat_callback_is_callable(main_module):
    assert callable(main_module.hub.on_chat_callback)


# ─────────────────────────────────────────────────────────────────────────────
# BotManager interface
# ─────────────────────────────────────────────────────────────────────────────

def test_bot_manager_has_on_chat_message(main_module):
    assert callable(getattr(main_module.bot_mgr, "on_chat_message", None))

def test_bot_manager_has_list_configs(main_module):
    assert callable(getattr(main_module.bot_mgr, "list_configs", None))

def test_bot_manager_has_upsert_config(main_module):
    assert callable(getattr(main_module.bot_mgr, "upsert_config", None))

def test_bot_manager_has_delete_config(main_module):
    assert callable(getattr(main_module.bot_mgr, "delete_config", None))

def test_bot_manager_has_set_cricket_keeper(main_module):
    assert callable(getattr(main_module.bot_mgr, "set_cricket_keeper", None))

def test_bot_manager_has_set_byok_manager(main_module):
    assert callable(getattr(main_module.bot_mgr, "set_byok_manager", None))


# ─────────────────────────────────────────────────────────────────────────────
# CricketKeeper interface
# ─────────────────────────────────────────────────────────────────────────────

def test_cricket_keeper_has_init(main_module):
    assert callable(getattr(main_module.cricket_keeper, "init", None))

def test_cricket_keeper_has_get(main_module):
    assert callable(getattr(main_module.cricket_keeper, "get", None))

def test_cricket_keeper_has_health_all(main_module):
    assert callable(getattr(main_module.cricket_keeper, "health_all", None))


# ─────────────────────────────────────────────────────────────────────────────
# Active room-conductor interface
# ─────────────────────────────────────────────────────────────────────────────

def test_room_conductor_has_watch_room(main_module):
    assert callable(getattr(main_module.app.state.room_conductor, "watch_room", None))

def test_room_conductor_has_release_room(main_module):
    assert callable(getattr(main_module.app.state.room_conductor, "release_room", None))

def test_room_conductor_has_on_message(main_module):
    assert callable(getattr(main_module.app.state.room_conductor, "on_message", None))

def test_room_conductor_has_all_scene_states(main_module):
    assert callable(getattr(main_module.app.state.room_conductor, "all_scene_states", None))

def test_room_conductor_all_scene_states_returns_list(main_module):
    result = main_module.app.state.room_conductor.all_scene_states()
    assert isinstance(result, list)


# ─────────────────────────────────────────────────────────────────────────────
# StudioControl interface
# ─────────────────────────────────────────────────────────────────────────────

def test_studio_ctrl_has_state(main_module):
    assert hasattr(main_module.studio_ctrl, "state")

def test_studio_ctrl_has_audio_matrix(main_module):
    assert hasattr(main_module.studio_ctrl, "audio_matrix")

def test_studio_ctrl_has_run_preflight(main_module):
    assert callable(getattr(main_module.studio_ctrl, "run_preflight_sequence", None))


# ─────────────────────────────────────────────────────────────────────────────
# StudioWebSocketHandler interface
# ─────────────────────────────────────────────────────────────────────────────

def test_studio_ws_handler_has_connect(main_module):
    assert callable(getattr(main_module.studio_ws_handler, "connect", None))

def test_studio_ws_handler_has_disconnect(main_module):
    assert callable(getattr(main_module.studio_ws_handler, "disconnect", None))

def test_studio_ws_handler_has_handle_message(main_module):
    assert callable(getattr(main_module.studio_ws_handler, "handle_message", None))


# ─────────────────────────────────────────────────────────────────────────────
# RecordingService interface
# ─────────────────────────────────────────────────────────────────────────────

def test_recording_has_list_profiles(main_module):
    assert callable(getattr(main_module.rec, "list_profiles", None))

def test_recording_has_list_sessions(main_module):
    assert callable(getattr(main_module.rec, "list_sessions", None))

def test_recording_has_start_session(main_module):
    assert callable(getattr(main_module.rec, "start_session", None))

def test_recording_has_register_profile(main_module):
    assert callable(getattr(main_module.rec, "register_profile", None))

def test_recording_has_privacy_matrix(main_module):
    assert callable(getattr(main_module.rec, "privacy_matrix", None))


# ─────────────────────────────────────────────────────────────────────────────
# UnityBridge interface
# ─────────────────────────────────────────────────────────────────────────────

def test_unity_bridge_has_handle_connection(main_module):
    assert callable(getattr(main_module.unity_bridge_mgr, "handle_connection", None))

def test_unity_bridge_has_on_pubcast_event(main_module):
    assert callable(getattr(main_module.unity_bridge_mgr, "on_pubcast_event", None))

def test_unity_bridge_has_status(main_module):
    assert callable(getattr(main_module.unity_bridge_mgr, "status", None))

def test_unity_bridge_has_world_brain(main_module):
    assert hasattr(main_module.unity_bridge_mgr, "_world_brain")


# ─────────────────────────────────────────────────────────────────────────────
# AvatarPerformerManager interface
# ─────────────────────────────────────────────────────────────────────────────

def test_performer_has_start(main_module):
    assert callable(getattr(main_module.performer_mgr, "start", None))

def test_performer_has_stop(main_module):
    assert callable(getattr(main_module.performer_mgr, "stop", None))

def test_performer_has_create_performer(main_module):
    assert callable(getattr(main_module.performer_mgr, "create_performer", None))

def test_performer_has_remove_performer(main_module):
    assert callable(getattr(main_module.performer_mgr, "remove_performer", None))

def test_performer_has_running_attribute(main_module):
    assert hasattr(main_module.performer_mgr, "_running")

def test_performer_has_performers_dict(main_module):
    assert hasattr(main_module.performer_mgr, "_performers")
    assert isinstance(main_module.performer_mgr._performers, dict)


# ─────────────────────────────────────────────────────────────────────────────
# CredentialStore interface
# ─────────────────────────────────────────────────────────────────────────────

def test_cred_store_has_upsert_model(main_module):
    assert callable(getattr(main_module.cred_store, "upsert_model", None))

def test_cred_store_has_list_models(main_module):
    assert callable(getattr(main_module.cred_store, "list_models", None))

def test_cred_store_has_delete_model(main_module):
    assert callable(getattr(main_module.cred_store, "delete_model", None))
