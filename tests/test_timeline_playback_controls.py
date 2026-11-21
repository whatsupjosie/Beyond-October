import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import timeline_routes as routes
from modules.timeline import EventType, TimelineDefinition, TimelineEvent, TimelinePlayer


def test_http_play_pause_seek_resume_stop(tmp_path, monkeypatch):
    player = TimelinePlayer()
    monkeypatch.setattr(routes, "player", player)
    monkeypatch.setattr(routes, "TIMELINES_DIR", tmp_path)
    (tmp_path / "shoot.json").write_text(json.dumps({
        "name": "shoot", "duration": 60, "events": [{"t": 45, "type": "camera"}],
    }))
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        def post(action, **kwargs):
            return client.post("/api/timeline/" + action, **kwargs)

        assert post("play").status_code == 400
        assert post("load", json={"name": "shoot"}).status_code == 200
        assert post("play").json().get("state") == "running"
        assert post("pause").status_code == 200
        assert client.get("/api/timeline/status").json()["state"] == "paused"
        assert post("seek", params={"time": 20}).json()["elapsed"] == pytest.approx(20)
        assert post("resume").json()["state"] == "running"
        assert post("stop").status_code == 200
        assert client.get("/api/timeline/status").json()["state"] == "idle"


async def test_critical_failure_stops_sibling_cues_and_is_logged():
    calls = []
    def reject(event):
        calls.append(event.label)
        raise ValueError("unavailable camera")

    player = TimelinePlayer()
    player.register_handler(EventType.CAMERA, reject)
    player.load_timeline(TimelineDefinition("shoot", duration=0.01, events=[
        TimelineEvent(0, EventType.CAMERA, label="first", critical=True),
        TimelineEvent(0, EventType.CAMERA, label="second"),
    ]))
    await player.start()
    await asyncio.wait_for(player._task, 1)
    assert calls == ["first"]
    assert player.status()["state"] == "failed"
    assert player.get_log()[0]["error"] == "unavailable camera"


def test_live_host_timeline_records_and_leaves_operator_countdown_alone(client, tmp_path, monkeypatch):
    import shutil
    import subprocess
    import time
    from pathlib import Path

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe are required for encoded take verification")
    monkeypatch.setattr(routes, "TIMELINES_DIR", tmp_path)
    (tmp_path / "take.json").write_text(json.dumps({
        "name": "take", "duration": 3, "events": [
            {"t": 0, "type": "record", "critical": True, "params": {"action": "start", "sources": ["wide_shot"]}},
            {"t": 3, "type": "record", "critical": True, "params": {"action": "stop"}},
        ],
    }))
    def sessions():
        return client.get("/api/recording/sessions").json()

    previous = {s["session_id"] for s in sessions()}
    assert client.post("/api/timeline/load", json={"name": "take"}).is_success
    assert client.post("/api/timeline/play").is_success
    deadline = time.monotonic() + 15
    while not any(s["session_id"] not in previous for s in sessions()):
        assert time.monotonic() < deadline
        time.sleep(.05)
    other = client.post("/api/recording/start", json={"sources": ["wide_shot"], "countdown_seconds": 30})
    assert other.is_success
    operator = other.json()["session_id"]
    try:
        while client.get("/api/timeline/status").json()["state"] == "running":
            assert time.monotonic() < deadline
            time.sleep(.1)
        assert client.get("/api/timeline/status").json()["state"] == "complete"
        after = {s["session_id"]: s for s in sessions() if s["session_id"] not in previous}
        assert after.pop(operator)["state"] == "countdown"
        (take,) = after.values()
        assert take["state"] == "stopped"
        (artifact,) = take["artifacts"]
        file = Path(artifact["file_path"])
        assert file.stat().st_size == artifact["size_bytes"] > 0
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(file)],
                               text=True, capture_output=True, check=True, timeout=10)
        assert probe.stdout.strip() == "h264"
    finally:
        client.post("/api/recording/" + operator + "/stop")
