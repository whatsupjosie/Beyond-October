from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.program_audio import ProgramAudioState
from modules.program_audio_routes import create_program_audio_router


class FakeBlackBox:
    def __init__(self):
        self.events = []

    def record_event(self, event_type, *, source, actor, data):
        self.events.append({"event_type": event_type, "source": source, "actor": actor, "data": data})


def make_client():
    state = ProgramAudioState()
    blackbox = FakeBlackBox()
    app = FastAPI()
    app.include_router(create_program_audio_router(state, blackbox=blackbox))
    return TestClient(app), blackbox


def test_program_audio_event_updates_state_and_blackbox():
    client, blackbox = make_client()

    response = client.post("/api/program-audio/event", json={"action": "play", "bus": "dialogue"}, headers={"X-Client-Id": "director"})

    assert response.status_code == 200
    assert response.json()["status"]["dialogue_active"] == 1
    assert blackbox.events[-1]["event_type"] == "audio.state"
    assert blackbox.events[-1]["data"]["bus"] == "dialogue"


def test_program_audio_recovery_stop_all():
    client, _ = make_client()
    client.post("/api/program-audio/event", json={"action": "play", "bus": "music"}, headers={"X-Client-Id": "director"})
    response = client.post("/api/program-audio/recovery/program_audio.stop_all", headers={"X-Client-Id": "director"})

    assert response.status_code == 200
    assert response.json()["status"]["buses"]["music"]["active_sources"] == 0


def test_program_audio_rejects_bad_bus():
    client, _ = make_client()
    response = client.post("/api/program-audio/event", json={"action": "play", "bus": "nonsense"}, headers={"X-Client-Id": "director"})
    assert response.status_code == 400
