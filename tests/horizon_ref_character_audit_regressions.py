"""Regression coverage for defects found during the character-level audit."""

import json
from unittest.mock import Mock
from zipfile import ZIP_DEFLATED, ZipFile

import pytest


def test_byok_character_packet_uses_canonical_prompt_lookup():
    from modules.byok_manager import BYOKManager

    manager = object.__new__(BYOKManager)
    packet = manager.build_character_packet("purfluous")

    assert packet.character_id == "purfluous"
    assert "Sir Purfluous" in packet.system_prompt


def test_recording_service_constructs_pipeline_registry(tmp_path):
    from modules.cameras import CameraManager
    from modules.recording import RecordingService

    service = RecordingService(tmp_path, CameraManager())

    assert service._pipeline_sessions == {}


def test_recording_service_rejects_path_escaping_session_id(tmp_path):
    from modules.cameras import CameraManager, CameraSource, CameraTransport
    from modules.recording import (
        ContainerFormat,
        EncodingProfile,
        RecordingService,
    )

    cameras = CameraManager()
    cameras.register(
        CameraSource(
            source_id="camera",
            name="Camera",
            location="studio",
            description="",
            transport=CameraTransport.VIRTUAL,
            endpoint="virtual://camera",
        )
    )
    service = RecordingService(tmp_path / "data", cameras)
    service.register_profile(
        EncodingProfile(
            profile_id="test",
            name="Test",
            container=ContainerFormat.MP4,
            video_codec=None,
            audio_codec=None,
            video_bitrate=None,
            audio_bitrate=None,
            resolution=None,
            frame_rate=None,
        )
    )

    with pytest.raises(ValueError, match="session_id"):
        service.start_session(
            "../../outside",
            ["camera"],
            profile_id="test",
            operator="owner",
        )
    assert not (tmp_path / "outside").exists()


def test_recording_import_rejects_path_escaping_metadata_id(tmp_path):
    from modules.cameras import CameraManager
    from modules.recording import RecordingService

    service = RecordingService(tmp_path / "data", CameraManager())
    archive = tmp_path / "hostile.zip"
    payload = {
        "session_id": "../../outside",
        "sources": [],
        "profile_id": "test",
        "operator": "owner",
        "state": "stopped",
    }
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        bundle.writestr("metadata.json", json.dumps(payload))

    with pytest.raises(ValueError, match="session_id"):
        service.import_session(archive)
    assert not (tmp_path / "outside").exists()


def test_storage_key_preserves_safe_ids_and_separates_hostile_ids():
    from modules.persistence import storage_key

    assert storage_key("owner-1") == "owner-1"
    assert "/" not in storage_key("../../owner")
    assert storage_key("a/b") != storage_key("a\\b")
    assert storage_key("a" * 121) != storage_key("a" * 120 + "b")
    with pytest.raises(ValueError, match="at least 24"):
        storage_key("owner", maximum=12)


def test_user_state_route_cannot_escape_data_root(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import main
    from modules.persistence import storage_key

    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "hub", None)
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    hostile_id = "../../outside"

    with TestClient(main.app) as client:
        response = client.post(
            "/api/state/user",
            headers={"X-Client-Id": hostile_id},
            json={"display_name": "Contained"},
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == hostile_id
    assert (
        tmp_path / "data" / "users" / f"{storage_key(hostile_id)}.json"
    ).is_file()
    assert not (tmp_path / "outside.json").exists()


def test_byok_credentials_do_not_collide_for_unsafe_user_ids(tmp_path):
    from modules.credentials import CredentialStore, StoredModel

    store = CredentialStore(tmp_path)
    first = StoredModel(
        model_id="model",
        provider="openai",
        display_name="First",
    )
    second = StoredModel(
        model_id="model",
        provider="openai",
        display_name="Second",
    )
    store.upsert_model("a/b", first, {"api_key": "first-secret"})
    store.upsert_model("a\\b", second, {"api_key": "second-secret"})

    assert store.get_secret("a/b", "model", "api_key") == "first-secret"
    assert store.get_secret("a\\b", "model", "api_key") == "second-secret"
    assert store._creds_path("a/b") != store._creds_path("a\\b")


def test_room_conductor_helpers_accept_declared_configuration():
    from modules.room_conductor import (
        ConversationOrchestrator,
        RoomConductorConfig,
        RoomSceneState,
        _calculate_drama_necessity,
        _derive_phase,
    )

    config = RoomConductorConfig()
    scene = RoomSceneState(room_id="audit-room")

    assert 0.0 <= _calculate_drama_necessity(scene, config) <= 1.0
    assert _derive_phase(scene, config).name == "OPENING"
    assert ConversationOrchestrator(config)._cfg is config


def test_vault_watch_loop_logs_integrity_exceptions(monkeypatch):
    import modules.vault_engine as vault_module

    engine = object.__new__(vault_module.VaultEngine)
    engine._watching = True
    engine._verify_vault_integrity = Mock(side_effect=RuntimeError("audit failure"))

    def stop_after_first_iteration(_seconds):
        engine._watching = False

    logged = Mock()
    monkeypatch.setattr(vault_module.logger, "error", logged)
    monkeypatch.setattr(vault_module.time, "sleep", stop_after_first_iteration)

    engine._watch_loop()

    logged.assert_called_once()
    assert logged.call_args.args[:2] == (
        "Vault integrity check failed: %s",
        engine._verify_vault_integrity.side_effect,
    )


def test_bubble_stack_public_exports_are_unique_and_complete():
    import modules.bubble_stack_pikpc as bubble

    assert len(bubble.__all__) == len(set(bubble.__all__))
    assert bubble.ActorPhysicalProfile is not None
    assert bubble.EnvironmentConfig is not None
