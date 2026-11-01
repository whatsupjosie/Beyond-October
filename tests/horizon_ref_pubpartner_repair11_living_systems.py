from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import pubpartner_routes


def _client(tmp_path):
    app = FastAPI()
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    app.include_router(pubpartner_routes.router)
    return TestClient(app)


def test_repair11_living_ui_assets_present():
    html = Path("static/pubpartner.html").read_text(encoding="utf-8")
    css = Path("static/pubpartner.css").read_text(encoding="utf-8")
    js = Path("static/pubpartner.js").read_text(encoding="utf-8")
    assert "Living" in html and "Hyperreal Lantern Desk" in html
    assert "modelName" in html
    assert "providerHost" in html
    assert "living-veil" in html
    assert "REPAIR11" in css
    assert "living/state" in js
    assert "providerConfig" in js
    assert "startLivingTelemetry" in js


def test_repair11_living_state_route(tmp_path):
    client = _client(tmp_path)
    response = client.get("/api/pubpartner/living/state", params={"user_id": "josie", "session_id": "living_route", "provider": "mock"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["mode"] == "living_systems_telemetry"
    assert "providers" in payload
    assert "counts" in payload
    assert "limiter" in payload


def test_repair11_ollama_status_query_is_honest(tmp_path):
    client = _client(tmp_path)
    response = client.get("/api/pubpartner/providers/status", params={"provider": "ollama", "model": "llama3.1", "host": "http://localhost:11434"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "ollama"
    assert "alive" in payload or "available" in payload
