from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

import main
from modules import auth as auth_module


def _token(user_id: str, role: str) -> str:
    return auth_module.create_access_token({"sub": user_id, "role": role})


class HubStub:
    def __init__(self):
        self.production_state = {}
        self.events = []

    def update_production_state(self, payload):
        self.production_state.update(payload)
        return dict(self.production_state)

    async def broadcast_system_event(self, payload):
        self.events.append(payload)

    async def broadcast_presence_update(self, client_id, display_name):
        self.events.append({"client_id": client_id, "display_name": display_name})


class CamerasStub:
    def __init__(self):
        self.program = None
        self.preview = None

    def set_program_source(self, source_id):
        self.program = source_id
        return True

    def set_preview_source(self, source_id):
        self.preview = source_id
        return True

    def get(self, source_id):
        return object()

    def get_program_source(self):
        return type("Cam", (), {"source_id": self.program})() if self.program else None

    def get_preview_source(self):
        return type("Cam", (), {"source_id": self.preview})() if self.preview else None



def test_main_production_state_requires_mod_when_auth_enforced(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    monkeypatch.setattr(main, "hub", HubStub())
    monkeypatch.setattr(main, "_HAS_PUBWORLD_ROUTER", False)
    monkeypatch.setattr(main, "push_production_state_to_pubworld", None)
    with TestClient(main.app) as client:
        monkeypatch.setattr(main, "hub", HubStub())
        monkeypatch.setattr(main, "_HAS_PUBWORLD_ROUTER", False)
        monkeypatch.setattr(main, "push_production_state_to_pubworld", None)
        missing = client.post("/api/state/production", json={"mode": "live"})
        assert missing.status_code == 401

        guest = client.post(
            "/api/state/production",
            json={"mode": "live"},
            headers={"Authorization": f"Bearer {_token('guesty', 'guest')}"},
        )
        assert guest.status_code == 403

        mod = client.post(
            "/api/state/production",
            json={"mode": "live"},
            headers={"Authorization": f"Bearer {_token('moddy', 'mod')}"},
        )
        assert mod.status_code == 200
        assert mod.json()["mode"] == "live"



def test_main_camera_switch_requires_mod_when_auth_enforced(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    monkeypatch.setattr(main, "cameras", CamerasStub())
    with TestClient(main.app) as client:
        monkeypatch.setattr(main, "cameras", CamerasStub())
        monkeypatch.setattr(main, "hub", HubStub())
        monkeypatch.setattr(main, "_HAS_PUBWORLD_ROUTER", False)
        monkeypatch.setattr(main, "push_production_state_to_pubworld", None)
        missing = client.post("/api/cameras/program/cam-1")
        assert missing.status_code == 401

        guest = client.post(
            "/api/cameras/program/cam-1",
            headers={"Authorization": f"Bearer {_token('guesty', 'guest')}"},
        )
        assert guest.status_code == 403

        mod = client.post(
            "/api/cameras/program/cam-1",
            headers={"Authorization": f"Bearer {_token('moddy', 'mod')}"},
        )
        assert mod.status_code == 200
        assert mod.json()["program"] == "cam-1"



def test_main_session_register_rejects_spoofed_user_when_auth_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    with TestClient(main.app) as client:
        bad = client.post(
            "/api/session/register",
            json={"user_id": "eve", "session_id": "sess", "project_id": "proj"},
            headers={
                "Authorization": f"Bearer {_token('alice', 'viewer')}",
                "X-Client-Id": "bob",
            },
        )
        assert bad.status_code == 403

        ok = client.post(
            "/api/session/register",
            json={"session_id": "sess", "project_id": "proj", "display_name": "Alice"},
            headers={
                "Authorization": f"Bearer {_token('alice', 'viewer')}",
                "X-Client-Id": "alice",
            },
        )
        assert ok.status_code == 200
        assert ok.json()["participant"]["user_id"] == "alice"



def test_main_avatar_route_rejects_header_token_mismatch_when_auth_enforced(monkeypatch, tmp_path):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    with TestClient(main.app) as client:
        response = client.get(
            "/api/avatars/me",
            headers={
                "Authorization": f"Bearer {_token('alice', 'viewer')}",
                "X-Client-Id": "bob",
            },
        )
        assert response.status_code == 403



def test_main_session_role_requires_mod_when_auth_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    with TestClient(main.app) as client:
        register = client.post(
            "/api/session/register",
            json={"session_id": "sess", "project_id": "proj"},
            headers={
                "Authorization": f"Bearer {_token('alice', 'viewer')}",
                "X-Client-Id": "alice",
            },
        )
        assert register.status_code == 200

        guest = client.post(
            "/api/session/sess/role",
            json={"target_user_id": "alice", "session_role": "director"},
            headers={"Authorization": f"Bearer {_token('guesty', 'guest')}"},
        )
        assert guest.status_code == 403

        mod = client.post(
            "/api/session/sess/role",
            json={"target_user_id": "alice", "session_role": "director"},
            headers={"Authorization": f"Bearer {_token('moddy', 'mod')}"},
        )
        assert mod.status_code == 200
        assert mod.json()["participant"]["session_role"] == ["director"]


def test_main_visual_patch_approve_requires_mod_and_persists_when_approved(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    payload = {
        "patch_kind": "adaptive_extension",
        "target": "both",
        "scene_id": "scene_default",
        "asset_id": "route_tail_chair_patch",
        "approval": {"state": "approved"},
        "adaptive_extension": {
            "extension_id": "route_tail_chair_patch",
            "object_id": "chair_01",
            "object_type": "chair",
            "interaction": "sit",
            "reason": "make chair usable for avatar silhouette and tail clearance",
            "voxel_patch": {
                "dimensions": [6, 4, 4],
                "subtractive_cutouts": [{"operation": "subtract", "kind": "tail_slot"}],
            },
        },
    }
    with TestClient(main.app) as client:
        monkeypatch.setattr(main, "DATA_DIR", tmp_path)
        missing = client.post("/api/visual-patch/approve", json=payload)
        assert missing.status_code == 401

        guest = client.post(
            "/api/visual-patch/approve",
            json=payload,
            headers={"Authorization": f"Bearer {_token('guesty', 'guest')}"},
        )
        assert guest.status_code == 403

        mod = client.post(
            "/api/visual-patch/approve",
            json=payload,
            headers={"Authorization": f"Bearer {_token('moddy', 'mod')}"},
        )
        assert mod.status_code == 200
        data = mod.json()
        assert data["ok"] is True
        assert data["patch_kind"] == "adaptive_extension"
        assert data["approval"]["state"] == "approved"
        assert data["voxel_set"]["asset_id"] == "route_tail_chair_patch"
        assert data["voxel_set"]["safety"]["approved_by_user"] is True
        assert data["voxel_set_path"]
        assert (tmp_path / "pubworld" / "props").exists()
        assert (tmp_path / "pubworld" / "voxel_sets" / "route_tail_chair_patch.json").exists()

class _BotConfigStub:
    name = "Test Bot"


class _BotManagerSpeakStub:
    def get_config(self, bot_id):
        return _BotConfigStub() if bot_id == "test-bot" else None

    def bot_user_id(self, bot_id):
        return f"bot-{bot_id}"


class _HubSpeakStub:
    def __init__(self):
        self.messages = []

    async def post_chat_message(self, room, user_id, text):
        self.messages.append((room, user_id, text))


def test_main_bot_speak_requires_mod_when_auth_enforced(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    with TestClient(main.app) as client:
        manager = _BotManagerSpeakStub()
        hub = _HubSpeakStub()
        monkeypatch.setattr(main, "bot_manager", manager)
        monkeypatch.setattr(main, "hub", hub)

        missing = client.post(
            "/api/bots/test-bot/speak",
            json={"room": "studio", "text": "line"},
        )
        assert missing.status_code == 401

        guest = client.post(
            "/api/bots/test-bot/speak",
            json={"room": "studio", "text": "line"},
            headers={"Authorization": f"Bearer {_token('guesty', 'guest')}"},
        )
        assert guest.status_code == 403

        mod = client.post(
            "/api/bots/test-bot/speak",
            json={"room": "studio", "text": "line"},
            headers={"Authorization": f"Bearer {_token('moddy', 'mod')}"},
        )
        assert mod.status_code == 200
        assert hub.messages == [("studio", "bot-test-bot", "line")]


def test_governance_audit_requires_mod_when_auth_enforced(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    with TestClient(main.app) as client:
        missing = client.get("/api/governance/audit?limit=1")
        assert missing.status_code == 401

        guest = client.get(
            "/api/governance/audit?limit=1",
            headers={"Authorization": f"Bearer {_token('guesty', 'guest')}"},
        )
        assert guest.status_code == 403

        mod = client.get(
            "/api/governance/audit?limit=1",
            headers={"Authorization": f"Bearer {_token('moddy', 'mod')}"},
        )
        assert mod.status_code == 200


def test_governance_user_audit_requires_mod_when_auth_enforced(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    with TestClient(main.app) as client:
        missing = client.get("/api/governance/audit/alice")
        assert missing.status_code == 401
        mod = client.get(
            "/api/governance/audit/alice",
            headers={"Authorization": f"Bearer {_token('moddy', 'mod')}"},
        )
        assert mod.status_code == 200
