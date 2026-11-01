from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from modules import alex_routes, auth_routes, character_routes, memory_routes
from modules.governance_routes import create_governance_router
from modules.production_routes import create_production_router
from modules.recording_pipeline_routes import router as recording_pipeline_router, register_pipeline_session, unregister_pipeline_session
from modules.structured_log_routes import router as structured_log_router


class DummyGov:
    def get_terms_of_service(self):
        return "terms"

    def get_ai_disclosure(self, bot_names):
        return "disclosure"

    def list_waiting(self, room=None):
        return []

    def list_active_bans(self):
        return []

    def list_frozen_avatars(self):
        return []

    def list_muted_users(self):
        return []


class DummyHub:
    async def broadcast_system_event(self, payload):
        return None

    def update_production_state(self, payload):
        return None


class DummyCameras:
    def list_sources(self):
        return []

    def list_status(self):
        return []

    def get_program_source(self):
        return None

    def get_preview_source(self):
        return None

    def set_program_source(self, source_id):
        return False

    def set_preview_source(self, source_id):
        return False

    def register(self, source):
        return None


class DummyRecording:
    def __init__(self, base: Path):
        self.imports_dir = base
        self.captured_import_path = None

    def list_profiles(self):
        return []

    def list_sessions(self):
        return []

    def storage_status(self):
        return {"ok": True}

    def privacy_matrix(self):
        return {"ok": True}

    def import_session(self, path: Path):
        self.captured_import_path = path
        return SimpleNamespace(to_dict=lambda: {"session_id": "imported"})


class DummyPipeline:
    def __init__(self):
        self._markers = []
        self._events = []

    def export_edl(self):
        return "edl"

    def export_fcpxml(self):
        return "<xml/>"

    def summary(self):
        return {"ok": True}

    def record_marker(self, label, operator):
        self._markers.append((label, operator))


class DummyAuth:
    def create_access_token(self, payload):
        return "token"

    def decode_access_token(self, token):
        return {"sub": "josie"}


class DummyCharacterEngine:
    async def speak(self, character_id, message, context=None):
        return f"{character_id}:{message}"

    def get_character_context(self, character_id):
        return {"id": character_id}


class DummyCharacterProfiles:
    def list_characters(self):
        return ["pete"]

    def get_character(self, character_id):
        return {"id": character_id}


class DummyMemory:
    async def store(self, character_id, content, memory_type="conversation", importance=0.5):
        return "mem-1"

    def get_recent(self, character_id, limit):
        return []

    def search(self, character_id, query, limit):
        return []


class DummyAlex:
    async def process_message(self, text, typing_speed=60.0, metadata=None, **kwargs):
        return {"ok": True, "text": text}

    def get_state(self):
        return {"state": "guide", "battery": "charged", "engagement_score": 1.0}

    async def grounding_check(self):
        return "ground"

    def get_recent_memories(self, limit=10):
        return []

    def reset(self):
        return None


@pytest.fixture
def governance_client():
    app = FastAPI()
    app.include_router(create_governance_router(DummyGov(), DummyHub()))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def production_client(tmp_path):
    app = FastAPI()
    recording = DummyRecording(tmp_path)
    app.state.recording = recording
    app.include_router(create_production_router(DummyCameras(), recording, DummyHub()))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def module_clients():
    auth_routes.set_auth_instance(DummyAuth())
    character_routes.set_character_instances(DummyCharacterEngine(), DummyCharacterProfiles())
    memory_routes.set_memory_instance(DummyMemory())
    alex_routes.set_alex_instance(DummyAlex())

    app = FastAPI()
    app.include_router(auth_routes.router)
    app.include_router(character_routes.router)
    app.include_router(memory_routes.router)
    app.include_router(alex_routes.router)
    with TestClient(app) as client:
        yield client


def test_governance_rejects_malformed_json(governance_client):
    response = governance_client.post(
        "/api/governance/consent",
        content='{"user_id": ',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert "Malformed JSON body" in response.json()["detail"]


def test_governance_waiting_room_rejects_non_object_consents(governance_client):
    response = governance_client.post(
        "/api/governance/waiting-room/request",
        json={"user_id": "josie", "consents": ["bad"]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "consents must be an object"


def test_governance_ban_rejects_invalid_type_and_negative_duration(governance_client):
    bad_type = governance_client.post(
        "/api/governance/ban",
        json={"user_id": "josie", "ban_type": "forever"},
    )
    assert bad_type.status_code == 400
    assert "Invalid ban type" in bad_type.json()["detail"]

    bad_duration = governance_client.post(
        "/api/governance/ban",
        json={"user_id": "josie", "duration_hours": -1},
    )
    assert bad_duration.status_code == 400
    assert bad_duration.json()["detail"] == "duration_hours must be non-negative"


def test_production_switch_rejects_malformed_json(production_client):
    response = production_client.post(
        "/api/cameras/switch",
        content='{"target": ',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert "Malformed JSON body" in response.json()["detail"]


def test_production_register_rejects_bad_vectors_and_tags(production_client):
    response = production_client.post(
        "/api/cameras/register",
        json={
            "source_id": "cam1",
            "position": [0, 1],
            "rotation": [0, 0, 0],
            "tags": ["ok", 3],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "position must be a 3-item array"


def test_production_start_rejects_bad_shapes(production_client):
    non_list = production_client.post(
        "/api/recording/start",
        json={"sources": "cam1"},
    )
    assert non_list.status_code == 400
    assert non_list.json()["detail"] == "sources must be an array"

    bad_bool = production_client.post(
        "/api/recording/start",
        json={"sources": ["cam1"], "host_override": "yes"},
    )
    assert bad_bool.status_code == 400
    assert bad_bool.json()["detail"] == "host_override must be a boolean"


def test_production_pause_rejects_non_boolean(production_client):
    response = production_client.post(
        "/api/recording/sess-1/pause",
        json={"paused": "sometimes"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "paused must be a boolean"


def test_production_import_sanitizes_filename(tmp_path):
    app = FastAPI()
    recording = DummyRecording(tmp_path)
    app.include_router(create_production_router(DummyCameras(), recording, DummyHub()))
    with TestClient(app) as client:
        response = client.post(
            "/api/recording/import",
            files={"file": ("../../escape.zip", b"zip-bytes", "application/zip")},
        )
        assert response.status_code == 200
        assert recording.captured_import_path is not None
        assert recording.captured_import_path.parent == tmp_path
        assert recording.captured_import_path.name == "escape.zip"


def test_recording_pipeline_marker_and_event_limits(tmp_path):
    app = FastAPI()
    pipeline = DummyPipeline()
    register_pipeline_session("sess-1", pipeline)
    app.include_router(recording_pipeline_router)
    try:
        with TestClient(app) as client:
            blank = client.post("/api/recording/sess-1/marker", params={"label": ""})
            assert blank.status_code == 422

            too_many = client.get("/api/recording/sess-1/events", params={"limit": 5000})
            assert too_many.status_code == 422
    finally:
        unregister_pipeline_session("sess-1")


def test_structured_logs_limit_is_bounded(monkeypatch):
    class DummyLog:
        def recent(self, limit=50, system=None, severity=None):
            return []

    import modules.structured_log_routes as log_routes

    monkeypatch.setattr(log_routes, "get_production_log", lambda: DummyLog())

    app = FastAPI()
    app.include_router(structured_log_router)
    with TestClient(app) as client:
        response = client.get("/api/logs/recent", params={"limit": 5001})
        assert response.status_code == 422


def test_module_models_reject_empty_or_out_of_range_inputs(module_clients):
    login = module_clients.post("/api/auth/login", json={"username": "", "password": "x"})
    assert login.status_code == 422

    speak = module_clients.post("/api/characters/speak", json={"character_id": "pete", "message": ""})
    assert speak.status_code == 422

    memory = module_clients.post(
        "/api/memory/store",
        json={"character_id": "pete", "content": "hello", "importance": 2.0},
    )
    assert memory.status_code == 422

    alex = module_clients.get("/api/alex/memory/recent", params={"limit": 1000})
    assert alex.status_code == 422
