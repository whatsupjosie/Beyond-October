from __future__ import annotations

import json
import os

import pytest
from starlette.testclient import TestClient

if os.getenv("ENABLE_ALEX_LITTLE_ONE", "").strip().lower() in {"1", "true", "yes", "on", "enabled"}:
    pytest.skip(
        "Disabled-mode guards run with ENABLE_ALEX_LITTLE_ONE unset or false.",
        allow_module_level=True,
    )

import main


FORBIDDEN_TERMS = (
    "baby",
    "diaper",
    "youth_fountain",
    "regression",
    "care_profile",
    "little_one",
    "public_role",
)


def _assert_no_protocol_terms(payload: object) -> None:
    raw = json.dumps(payload, sort_keys=True).lower()
    found = [term for term in FORBIDDEN_TERMS if term in raw]
    assert not found, found


def test_alex_little_one_public_routes_are_not_exposed_when_disabled(tmp_path, monkeypatch, main_module):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    with TestClient(main.app) as client:
        assert client.get("/api/session/sess/public-role-policy").status_code == 404
        assert client.post("/api/session/sess/public-role/phrase", json={}).status_code == 404
        assert client.post("/api/session/sess/public-role/moderate", json={}).status_code == 404
        assert client.post("/api/session/sess/public-role/owner-attempt", json={}).status_code == 404


def test_default_user_and_session_payloads_are_neutral_when_disabled(tmp_path, monkeypatch, main_module):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "alex_bridge", None)
    with TestClient(main.app) as client:
        user_response = client.get("/api/state/user", headers={"X-Client-Id": "public-user"})
        assert user_response.status_code == 200
        _assert_no_protocol_terms(user_response.json())

        save_response = client.post(
            "/api/state/user",
            headers={"X-Client-Id": "public-user"},
            json={
                "display_name": "Public User",
                "care_profile": {"mode": "youth_fountain_regression"},
            },
        )
        assert save_response.status_code == 200
        _assert_no_protocol_terms(save_response.json())

        register_response = client.post(
            "/api/session/register",
            json={
                "session_id": "public-session",
                "project_id": "public-project",
                "user_id": "public-user",
                "host_user_id": "public-user",
                "care_profile": {"public_role": "baby"},
            },
        )
        assert register_response.status_code == 200
        _assert_no_protocol_terms(register_response.json())

        roster_response = client.get("/api/session/public-session/roster")
        assert roster_response.status_code == 200
        _assert_no_protocol_terms(roster_response.json())
