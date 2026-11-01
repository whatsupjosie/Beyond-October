from pathlib import Path

import pytest

from modules.cameras import create_default_cameras
from modules.program_audio import ProgramAudioState
from modules.recording import create_recording_service
from modules.studio_console_actions import execute_studio_action, list_studio_actions


def test_studio_actions_manifest_has_hotspot_ready_ids():
    ids = {item["action_id"] for item in list_studio_actions()}
    assert "studio.readiness" in ids
    assert "camera.switch.program" in ids
    assert "recording.preflight" in ids
    assert "audio.stop_all" in ids


def test_execute_camera_and_audio_actions(tmp_path: Path):
    cameras = create_default_cameras()
    recording = create_recording_service(tmp_path, cameras)
    audio = ProgramAudioState()

    switched = execute_studio_action("camera.switch.program", {"source_id": "medium_shot"}, cameras=cameras, recording=recording, audio_state=audio, actor="director")
    audio_result = execute_studio_action("audio.event", {"action": "play", "bus": "dialogue"}, cameras=cameras, recording=recording, audio_state=audio, actor="director")

    assert switched["result"]["source_id"] == "medium_shot"
    assert cameras.get_program_source().source_id == "medium_shot"
    assert audio_result["result"]["dialogue_active"] == 1


def test_recording_start_requires_confirmation(tmp_path: Path):
    cameras = create_default_cameras()
    recording = create_recording_service(tmp_path, cameras)
    audio = ProgramAudioState()

    with pytest.raises(ValueError, match="confirm"):
        execute_studio_action("recording.start", {}, cameras=cameras, recording=recording, audio_state=audio, actor="director")

    started = execute_studio_action("recording.start", {"confirm": True, "session_id": "rec_console"}, cameras=cameras, recording=recording, audio_state=audio, actor="director")
    assert started["result"]["session_id"] == "rec_console"
