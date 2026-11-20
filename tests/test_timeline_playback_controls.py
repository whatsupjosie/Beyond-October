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
