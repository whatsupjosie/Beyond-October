from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from modules import auth as auth_module
from modules import auth_routes, userdb
from modules.governance_routes import create_governance_router
from modules.production_routes import create_production_router


class GovWithModeration:
    def __init__(self):
        self.calls = []

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

    def ban_user(self, user_id, reason, issued_by, ban_type, duration):
        self.calls.append((user_id, issued_by, ban_type.value if hasattr(ban_type, 'value') else ban_type))
        return type("Ban", (), {"ban_id": "ban-1"})()

    def unban_user(self, user_id, lifted_by):
        self.calls.append((user_id, lifted_by, "unban"))
        return True

    def freeze_avatar(self, user_id, frozen_by, reason, pose):
        self.calls.append((user_id, frozen_by, "freeze"))
        return {}

    def unfreeze_avatar(self, user_id, unfrozen_by):
        self.calls.append((user_id, unfrozen_by, "unfreeze"))
        return True

    def mute_user(self, user_id, muted_by, duration):
        self.calls.append((user_id, muted_by, "mute"))

    def unmute_user(self, user_id, unmuted_by):
        self.calls.append((user_id, unmuted_by, "unmute"))


class HubNoop:
    async def broadcast_system_event(self, payload):
        return None

    def update_production_state(self, payload):
        return None


class CamerasOkay:
    def __init__(self):
        self.program = None
        self.preview = None

    def list_sources(self):
        return []

    def list_status(self):
        return []

    def get_program_source(self):
        return type("Cam", (), {"source_id": self.program})() if self.program else None

    def get_preview_source(self):
        return type("Cam", (), {"source_id": self.preview})() if self.preview else None

    def set_program_source(self, source_id):
        self.program = source_id
        return True

    def set_preview_source(self, source_id):
        self.preview = source_id
        return True

    def register(self, source):
        return None


class RecordingStub:
    def __init__(self, base: Path):
        self.imports_dir = base

    def list_profiles(self):
        return []

    def list_sessions(self):
        return []

    def storage_status(self):
        return {"ok": True}

    def privacy_matrix(self):
        return {"ok": True}


@pytest.fixture()
def auth_db(tmp_path, monkeypatch):
    monkeypatch.setattr(userdb, "_DB_PATH", tmp_path / "users.db")
    return tmp_path


async def _seed_users():
    await userdb.init_db()
    await userdb.create_user("moddy", "secret", role="mod")
    await userdb.create_user("guesty", "secret", role="guest")


def _token(username: str, role: str) -> str:
    return auth_module.create_access_token({"sub": username, "role": role})


def test_auth_login_verifies_password_and_role(auth_db):
    import asyncio

    asyncio.run(_seed_users())
    auth_routes.set_auth_instance(auth_module)
    app = FastAPI()
    app.include_router(auth_routes.router)

    with TestClient(app) as client:
        ok = client.post("/api/auth/login", json={"username": "moddy", "password": "secret"})
        assert ok.status_code == 200
        token = ok.json()["access_token"]

        verify = client.get("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
        assert verify.status_code == 200
        assert verify.json()["payload"]["sub"] == "moddy"
        assert verify.json()["payload"]["role"] == "mod"

        bad = client.post("/api/auth/login", json={"username": "moddy", "password": "wrong"})
        assert bad.status_code == 401


def test_governance_requires_mod_when_auth_enforced(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    gov = GovWithModeration()
    app = FastAPI()
    app.include_router(create_governance_router(gov, HubNoop()))
    with TestClient(app) as client:
        missing = client.post("/api/governance/ban", json={"user_id": "victim"})
        assert missing.status_code == 401

        guest = client.post(
            "/api/governance/ban",
            json={"user_id": "victim"},
            headers={"Authorization": f"Bearer {_token('guesty', 'guest')}"},
        )
        assert guest.status_code == 403

        mod = client.post(
            "/api/governance/ban",
            json={"user_id": "victim", "issued_by": "pretender"},
            headers={"Authorization": f"Bearer {_token('moddy', 'mod')}"},
        )
        assert mod.status_code == 200
        # privileged caller may override actor label, but route must still succeed cleanly.
        assert gov.calls[-1][0] == "victim"


def test_production_switch_requires_mod_when_auth_enforced(monkeypatch, tmp_path):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    app = FastAPI()
    app.include_router(create_production_router(CamerasOkay(), RecordingStub(tmp_path), HubNoop()))
    with TestClient(app) as client:
        missing = client.post("/api/cameras/switch", json={"target": "program", "source_id": "cam-1"})
        assert missing.status_code == 401

        guest = client.post(
            "/api/cameras/switch",
            json={"target": "program", "source_id": "cam-1"},
            headers={"Authorization": f"Bearer {_token('guesty', 'guest')}"},
        )
        assert guest.status_code == 403

        mod = client.post(
            "/api/cameras/switch",
            json={"target": "program", "source_id": "cam-1"},
            headers={"Authorization": f"Bearer {_token('moddy', 'mod')}"},
        )
        assert mod.status_code == 200
        assert mod.json()["source_id"] == "cam-1"
