from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.runtime_control_routes import create_runtime_control_router


class FakePerformanceManager:
    def __init__(self):
        self.profile = "medium"

    def status(self):
        return {
            "available": True,
            "active_profile": self.profile,
            "profiles": {"low": {}, "medium": {}, "high": {}},
        }

    def set_profile(self, profile: str):
        if profile not in {"low", "medium", "high"}:
            raise ValueError(f"Unknown profile: {profile!r}")
        self.profile = profile
        return {"profile": profile, "settings": {"choreo_tick_hz": 20 if profile == "low" else 30}}


class FakeChoreoController:
    def __init__(self):
        self.constraints = {"enabled": True}
        self.cues = []

    def status(self):
        return {"running": False, "constraints": self.constraints}

    def list_actions(self):
        return {"idle": {"label": "Idle", "category": "base"}}

    def get_constraints(self):
        return dict(self.constraints)

    def set_constraints(self, patch):
        self.constraints.update(patch)
        return dict(self.constraints)

    async def cue_action(self, *, room, avatar_id, action, intensity=1.0, duration=None, props=None):
        if not avatar_id:
            raise ValueError("avatar_id is required")
        if action != "idle":
            raise ValueError(f"Unknown action: {action!r}")
        cue = {
            "room": room,
            "avatar_id": avatar_id,
            "action": action,
            "intensity": intensity,
            "duration": duration,
            "props": props or {},
        }
        self.cues.append(cue)
        return cue


def make_client(performance=None, choreo=None):
    app = FastAPI()
    app.include_router(create_runtime_control_router(performance_manager=performance, choreo_controller=choreo))
    return TestClient(app)


def test_unavailable_routes_return_payload_not_404():
    client = make_client()

    assert client.get("/api/performance/status").status_code == 200
    assert client.get("/api/performance/status").json()["status"] == "unavailable"
    assert client.get("/api/choreo/actions").status_code == 200
    assert client.get("/api/choreo/actions").json()["status"] == "unavailable"


def test_performance_profile_routes():
    perf = FakePerformanceManager()
    client = make_client(performance=perf)

    status = client.get("/api/performance/status")
    assert status.status_code == 200
    assert status.json()["active_profile"] == "medium"

    changed = client.post("/api/performance/profile", json={"profile": "low"})
    assert changed.status_code == 200
    assert changed.json()["profile"] == "low"
    assert perf.profile == "low"


def test_choreo_routes_cover_stage_panoramic_calls():
    choreo = FakeChoreoController()
    client = make_client(choreo=choreo)

    assert client.get("/api/choreo/actions").json()["actions"]["idle"]["label"] == "Idle"
    assert client.get("/api/choreo/constraints").json()["constraints"]["enabled"] is True

    updated = client.post("/api/choreo/constraints", json={"enabled": False})
    assert updated.status_code == 200
    assert updated.json()["constraints"]["enabled"] is False

    cue = client.post("/api/choreo/cue", json={"room": "main", "avatar_id": "Manny", "action": "idle"})
    assert cue.status_code == 200
    assert cue.json()["cue"]["avatar_id"] == "Manny"


def test_choreo_bad_cue_returns_400_not_500():
    choreo = FakeChoreoController()
    client = make_client(choreo=choreo)

    response = client.post("/api/choreo/cue", json={"avatar_id": "Manny", "action": "not_real"})
    assert response.status_code == 400
