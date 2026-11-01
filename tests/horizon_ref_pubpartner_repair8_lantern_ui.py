from pathlib import Path
from fastapi.testclient import TestClient
from fastapi import FastAPI

from modules import pubpartner_routes


def _client(tmp_path):
    app = FastAPI()
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    app.include_router(pubpartner_routes.router)
    return TestClient(app)


def test_lantern_ui_static_files_exist_and_have_customizable_panels():
    html = Path("static/pubpartner.html")
    css = Path("static/pubpartner.css")
    js = Path("static/pubpartner.js")
    assert html.exists(), "PubPartner HTML shell missing"
    assert css.exists(), "PubPartner CSS shell missing"
    assert js.exists(), "PubPartner JS shell missing"
    h = html.read_text(encoding="utf-8")
    c = css.read_text(encoding="utf-8")
    j = js.read_text(encoding="utf-8")
    assert "friend layer" in h.lower()
    assert "Customize Layout" in h
    assert "data-panel=\"conversation\"" in h
    assert "data-panel=\"preview\"" in h
    assert "data-panel=\"wardrobe\"" in h
    assert "fan-menu" in h
    assert "clip-path" in c
    assert "localStorage" in j
    assert "/api/pubpartner/turns/live" in j
    assert "/api/pubpartner/sources/" in j


def test_lantern_ui_api_still_runs_live_turn_and_receipts(tmp_path):
    client = _client(tmp_path)
    session = client.post("/api/pubpartner/sessions", json={
        "user_id": "josie",
        "session_id": "lantern_ui",
        "friend": "craig",
        "provider": {"provider": "mock"},
        "project_id": "pubpartner",
        "room_id": "phone",
    })
    assert session.status_code == 200
    turn = client.post("/api/pubpartner/turns/live", json={
        "user_id": "josie",
        "session_id": "lantern_ui",
        "message": "This exact line must be preserved.",
        "friend": "craig",
        "provider": {"provider": "mock"},
        "content_kind": "quote",
    })
    assert turn.status_code == 200
    payload = turn.json()
    assert payload["source"]["id"]
    assert payload["receipt"]
    restored = client.get(f"/api/pubpartner/sources/{payload['source']['id']}", params={"user_id":"josie", "session_id":"lantern_ui"})
    assert restored.status_code == 200
    assert restored.json()["text"] == "This exact line must be preserved."
