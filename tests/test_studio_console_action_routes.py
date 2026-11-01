from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.cameras import create_default_cameras
from modules.production_routes import create_production_router
from modules.recording import create_recording_service


class FakeBlackBox:
    def __init__(self):
        self.events = []

    def record_event(self, event_type, *, source, actor, data):
        self.events.append({"event_type": event_type, "source": source, "actor": actor, "data": data})


class FakeHub:
    def __init__(self):
        self.events = []

    async def broadcast_system_event(self, event):
        self.events.append(event)


def make_client(tmp_path: Path):
    cameras = create_default_cameras()
    recording = create_recording_service(tmp_path, cameras)
    blackbox = FakeBlackBox()
    hub = FakeHub()
    app = FastAPI()
    app.include_router(create_production_router(cameras, recording, hub=hub, blackbox=blackbox))
    return TestClient(app), cameras, blackbox, hub


def test_studio_actions_manifest_is_hotspot_ready(tmp_path: Path):
    client, _, _, _ = make_client(tmp_path)

    response = client.get("/api/studio/actions", headers={"X-Client-Id": "director"})

    assert response.status_code == 200
    ids = {item["action_id"] for item in response.json()["actions"]}
    assert "camera.switch.program" in ids
    assert "recording.preflight" in ids
    assert "audio.stop_all" in ids


def test_studio_action_route_executes_and_records_blackbox(tmp_path: Path):
    client, cameras, blackbox, hub = make_client(tmp_path)

    response = client.post(
        "/api/studio/actions/camera.switch.program",
        json={"source_id": "medium_shot"},
        headers={"X-Client-Id": "director"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["source_id"] == "medium_shot"
    assert cameras.get_program_source().source_id == "medium_shot"
    assert blackbox.events[-1]["event_type"] == "studio.action"
    assert blackbox.events[-1]["data"]["action_id"] == "camera.switch.program"
    assert hub.events[-1]["type"] == "studio_action"
    assert hub.events[-1]["payload"]["action_id"] == "camera.switch.program"


def test_studio_action_route_rejects_unconfirmed_recording_start(tmp_path: Path):
    client, _, _, _ = make_client(tmp_path)

    response = client.post(
        "/api/studio/actions/recording.start",
        json={},
        headers={"X-Client-Id": "director"},
    )

    assert response.status_code == 400
    assert "confirm" in response.json()["detail"]
