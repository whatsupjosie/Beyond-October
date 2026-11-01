import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import pubpartner_routes


def _client(tmp_path):
    app = FastAPI()
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    app.include_router(pubpartner_routes.router)
    return TestClient(app)


def test_pubpartner_routes_reject_non_string_message(tmp_path):
    client = _client(tmp_path)
    response = client.post("/api/pubpartner/turns", json={"user_id": "u", "session_id": "s", "message": {"not": "string"}})
    assert response.status_code == 400
    assert "message must be a string" in response.text


def test_pubpartner_routes_reject_bad_max_memories(tmp_path):
    client = _client(tmp_path)
    response = client.post("/api/pubpartner/turns", json={"user_id": "u", "session_id": "s", "message": "hi", "max_memories": "lots"})
    assert response.status_code == 400
    assert "max_memories must be an integer" in response.text


def test_pubpartner_route_span_restore_and_audit_listing(tmp_path):
    client = _client(tmp_path)
    exact = "one\ntwo\nthree"
    response = client.post("/api/pubpartner/turns", json={"user_id": "u", "session_id": "s", "message": exact, "content_kind": "quote"})
    assert response.status_code == 200
    source_id = response.json()["source"]["id"]

    span = client.get(f"/api/pubpartner/sources/{source_id}/span", params={"user_id": "u", "session_id": "s", "start": 4, "end": 7})
    assert span.status_code == 200
    assert span.json()["span"]["text"] == "two"

    listed = client.get("/api/pubpartner/sources", params={"user_id": "u", "session_id": "s"})
    assert listed.status_code == 200
    assert listed.json()["audit"]["ok"] is True
    assert listed.json()["sources"][0]["source_id"] == source_id
