from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.runtime_compat_bootstrap import mount_runtime_compat_routes


class FakePerformanceManager:
    def status(self):
        return {"active_profile": "low", "profiles": {"low": {}}}

    def set_profile(self, profile: str):
        return {"profile": profile, "settings": {}}


class FakeChoreoController:
    def status(self):
        return {"running": False}

    def list_actions(self):
        return {"idle": {"label": "Idle", "category": "base"}}

    def get_constraints(self):
        return {"enabled": True}

    def set_constraints(self, patch):
        return patch

    async def cue_action(self, *, room, avatar_id, action, intensity=1.0, duration=None, props=None):
        return {"room": room, "avatar_id": avatar_id, "action": action}


class FakeCameraSource:
    def __init__(self, source_id: str):
        self.source_id = source_id


class FakeCameras:
    def get_program_source(self):
        return FakeCameraSource("program_cam")

    def get_preview_source(self):
        return FakeCameraSource("preview_cam")


def test_bootstrap_mounts_runtime_and_stage_compat_routes():
    app = FastAPI()
    mount_runtime_compat_routes(
        app,
        cameras=FakeCameras(),
        performance_manager=FakePerformanceManager(),
        choreo_controller=FakeChoreoController(),
    )
    client = TestClient(app)

    assert client.get("/api/performance/status").status_code == 200
    assert client.get("/api/choreo/actions").status_code == 200
    assert client.get("/api/state/user").status_code == 200
    assert client.get("/api/switcher").status_code == 200
    assert client.get("/api/switcher").json()["switcher"]["program"] == "program_cam"
