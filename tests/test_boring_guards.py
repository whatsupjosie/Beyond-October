from __future__ import annotations

import json
from pathlib import Path

from modules import session_runtime
from modules.pubworld import create_scene, get_scene
from modules.recording_pipeline import ServerRecordingSession
from modules.structured_log import ProductionLog


def test_session_runtime_recovers_from_corrupt_json(tmp_path: Path):
    data_dir = tmp_path / "data"
    session_path = data_dir / "sessions" / "demo.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text("{ definitely not json", encoding="utf-8")

    payload = session_runtime.load_session(data_dir, "demo")
    assert payload["session_id"] == "demo"
    assert payload["participants"] == {}

    session_runtime.register_participant(
        data_dir,
        session_id="demo",
        user_id="user_1",
        display_name="User One",
    )
    saved = json.loads(session_path.read_text(encoding="utf-8"))
    assert saved["participants"]["user_1"]["display_name"] == "User One"


def test_structured_log_subscriber_failure_does_not_block_write(tmp_path: Path):
    log = ProductionLog(tmp_path)

    def bad_subscriber(_entry):
        raise RuntimeError("boom")

    log.subscribe(bad_subscriber)
    entry = log.emit("system", "event", {"text": "héllo"})
    assert entry["event"] == "event"
    payload = (tmp_path / "production.jsonl").read_text(encoding="utf-8")
    assert "héllo" in payload


def test_pubworld_create_scene_writes_valid_json(tmp_path: Path):
    scene = create_scene(tmp_path, "Test Scene", "boring check")
    loaded = get_scene(tmp_path, scene.scene_id)
    assert loaded is not None
    assert loaded.name == "Test Scene"


def test_recording_pipeline_flush_writes_utf8_files(tmp_path: Path):
    session = ServerRecordingSession("boring_session", tmp_path)
    session.record_chat("tester", "héllo world", "u1")
    summary = session.stop()
    assert summary["chat_messages"] == 1
    session_dir = tmp_path / "boring_session"
    assert json.loads((session_dir / "session.json").read_text(encoding="utf-8"))["chat"][0]["text"] == "héllo world"
    assert (session_dir / "edit_list.edl").exists()
