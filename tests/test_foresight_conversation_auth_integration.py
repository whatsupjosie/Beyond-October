"""Foresight conversation creation must use the shared Reach owner session."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.conversation_routes import create_conversation_router

ROOT = Path(__file__).resolve().parents[1]


def test_foresight_new_chat_does_not_forge_guest_or_client_identity():
    source = (ROOT / "static" / "foresight_programs.js").read_text(encoding="utf-8")
    function = source.split("async function newChat(){", 1)[1].split("\n    // --- reload", 1)[0]
    assert "fetch('/api/conversations'" in function
    assert "'X-Dev-Role'" not in function
    assert "'X-Client-Id'" not in function
    assert "localStorage" not in function


def test_new_chat_uses_authenticated_archive_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    app = FastAPI()
    app.include_router(create_conversation_router(tmp_path))
    client = TestClient(app)
    url = "/api/conversations"
    assert client.post(url, json={"title": "From Foresight"}).status_code == 401
    token = create_access_token({"sub": "owner-one", "role": "owner"})
    owner = {"Authorization": f"Bearer {token}"}
    created = client.post(url, json={"title": "From Foresight"}, headers=owner)
    assert created.status_code == 200, created.text
    assert created.json()["conversation_id"]
    assert len(client.get(url, headers=owner).json()["conversations"]) == 1
    other = {"Authorization": "Bearer " + create_access_token({"sub": "owner-two", "role": "owner"})}
    assert client.get(url, headers=other).json()["conversations"] == []
