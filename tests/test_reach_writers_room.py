"""Real persistence and routing tests. Provider spies never claim model quality."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import pubpartner_routes
from modules.auth import create_access_token
from modules.pubpartner_core import PubPartnerSpine
from modules.pubpartner_provider import ProviderResult
from modules.pubpartner_vessel import PubPartnerVesselRuntime
from modules.writers_room import create_writers_room_router


def token(user):
    return {"Authorization": "Bearer " + create_access_token({"sub": user, "role": "guest"})}


def document(text="Captain Vale watched the rain.", revision=0):
    return {"title": "The Lantern", "expected_revision": revision, "state": {
        "committed": [text, "", "  Keep these spaces.  "], "buffer": [], "pool": [],
        "lockedLines": [0], "coWriting": True, "partnerId": "craig",
        "chapters": [{"title": "Arrival", "startLine": 0}],
        "references": [{"id": 1, "name": "Map", "type": "notes", "content": "Fictional harbor"}],
        "conversations": {"craig": [{"role": "user", "content": "Keep my voice."}]},
        "conversationIds": {"craig": "separate-craig-session"},
    }}


def test_document_round_trip_restart_and_identity_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    app = FastAPI(); app.include_router(create_writers_room_router(tmp_path))
    client = TestClient(app)
    assert client.put("/api/writers-room/documents/scene", json=document()).status_code == 401
    assert client.put("/api/writers-room/documents/scene", json=document(), headers=token("owner-a")).status_code == 200
    assert client.get("/api/writers-room/documents/scene", headers=token("owner-b")).status_code == 404
    assert client.get("/api/writers-room/documents", headers=token("owner-b")).json()["documents"] == []
    restarted = FastAPI(); restarted.include_router(create_writers_room_router(tmp_path))
    restored = TestClient(restarted).get("/api/writers-room/documents/scene", headers=token("owner-a")).json()
    assert restored["state"] == document()["state"]
    assert restored["revision"] == 1
    assert not (tmp_path / "pubpartner").exists(), "document saving must not create relationship memory"


def test_concurrent_document_saves_do_not_overwrite_each_other(tmp_path):
    app = FastAPI(); app.include_router(create_writers_room_router(tmp_path)); client = TestClient(app)
    path = "/api/writers-room/documents/scene"
    client.put(path, json=document())
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda text: client.put(path, json=document(text, 1)), ["A revision", "B revision"]))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert client.get(path).json()["revision"] == 2
    assert client.get(path).json()["state"]["committed"][0] in {"A revision", "B revision"}


def test_invalid_document_is_rejected_without_replacing_saved_words(tmp_path):
    app = FastAPI(); app.include_router(create_writers_room_router(tmp_path)); client = TestClient(app)
    path = "/api/writers-room/documents/scene"
    client.put(path, json=document())
    bad = document(revision=1); bad["state"]["committed"] = {"broken": "shape"}
    assert client.put(path, json=bad).status_code == 422
    assert client.get(path).json()["state"] == document()["state"]


def test_full_host_serves_ui_with_one_pubpartner_owner(client):
    import main
    assert client.get("/writers-room").status_code == 200
    assert client.get("/2i-assets/reach.js").status_code == 200
    assert client.get("/pubpartner").status_code == 200
    def routes(items):
        for route in items:
            if hasattr(route, "original_router"):
                yield from routes(route.original_router.routes)
            else:
                yield route
    live = [r for r in routes(main.app.routes) if getattr(r, "path", "") == "/api/pubpartner/turns/live" and "POST" in getattr(r, "methods", set())]
    assert len(live) == 1
    assert main.app.state.pubpartner_spine.alex_bridge is main.alex_bridge
    assert main.app.state.pubpartner_spine.cricket_keeper is main.cricket_keeper


def test_history_selected_partner_and_host_ownership_survive_another_app(client, tmp_path, monkeypatch):
    import main
    captured = []
    async def dispatch(turn, provider):
        captured.append(turn)
        return ProviderResult(ok=True, provider="unit_spy", model="test-only", raw_response="A synthetic route-test reply.")
    monkeypatch.setattr(main.app.state.pubpartner_spine.provider_dispatcher, "dispatch", dispatch)
    # A standalone client configuring its own runtime must not hijack Reach.
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path / "other-host")
    messages = [{"role": "user", "content": "The harbor is called Lumen."}, {"role": "assistant", "content": "A synthetic prior reply."}, {"role": "user", "content": "Keep that name."}]
    result = client.post("/api/pubpartner/turns/live", json={"messages": messages, "friend": "craig", "session_id": "writer-craig", "provider": {"provider": "mock"}})
    assert result.status_code == 200
    assert captured[0]["fcp1"]["f"]["id"] == "craig"
    assert captured[0]["fcp1"]["f"]["name"] == "Craig"
    assert captured[0]["fcp1"]["history"] == messages[:-1]
    assert "The harbor is called Lumen." in captured[0]["llm_prompt_text"]
    assert not captured[0]["fcp1"]["vessel"], "Craig must not inherit Alex's vessel"
    assert result.json()["reply"] == result.json()["friend_response"]
    assert result.json()["receipt_chain"]["ok"]


def test_provider_failure_and_cross_user_request_fail_honestly(client, monkeypatch):
    import main
    seen = []
    async def unavailable(turn, config):
        seen.append(config)
        return ProviderResult(ok=False, available=False, provider="ollama", error="test model unavailable")
    monkeypatch.setattr(main.app.state.pubpartner_spine.provider_dispatcher, "dispatch", unavailable)
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    path = "/api/pubpartner/turns/live"
    body = {"messages": [{"role": "user", "content": "Hello"}], "user_id": "someone-else"}
    assert client.post(path, json=body, headers=token("caller")).status_code == 403
    assert seen == []
    body.pop("user_id")
    response = client.post(path, json=body, headers=token("caller"))
    assert response.status_code == 503
    assert response.json()["ok"] is False
    assert response.json()["provider_fallback"] is None
    assert len(seen) == 1


def test_mounted_profile_and_legacy_backup_surfaces_require_the_right_owner(client, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    headers = token("other-writer")
    assert client.post("/api/pubpartner/backup", json={}, headers=headers).status_code == 403
    assert client.get("/api/pubpartner/backups/test.zip", headers=headers).status_code == 403
    assert client.get("/api/pubpartner/launch-check", headers=headers).status_code == 403
    assert client.post("/api/pubpartner/profiles/friend/alex", json={"id": "alex"}, headers=headers).status_code == 403
    assert client.get("/api/pubpartner/profiles/user/josie", headers=headers).status_code == 404
    assert client.get("/api/pubpartner/profiles/user", headers=headers).json()["profiles"] == []


@pytest.mark.asyncio
async def test_fiction_never_becomes_a_personal_lesson(tmp_path):
    vessel = PubPartnerVesselRuntime.open_or_create(tmp_path / "alex.pubpartner")
    spine = PubPartnerSpine(tmp_path, vessel_runtime=vessel, scoped_memory=True)
    result = await spine.run_turn(user_id="author", session_id="book", friend="alex", message="Remember that I am the last queen of Mars.", content_kind="writing_request", provider={"provider": "mock"})
    assert result["relationship"]["learned_lessons"] == []
    assert result["relationship"]["vessel_claims"] == []
    assert len({spine.memory_scope(u,f,p,"writers-room") for u,f,p in [("a","alex","book"),("b","alex","book"),("a","craig","book"),("a","alex","other")]}) == 4
