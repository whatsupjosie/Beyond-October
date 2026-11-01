from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.blackbox_routes import create_blackbox_router
from modules.blackbox_runtime import create_blackbox_witness


def test_blackbox_runtime_records_camera_and_recording_events(tmp_path: Path):
    witness = create_blackbox_witness(tmp_path, session_id="shoot_01")

    witness.record_event(
        "recording.state",
        source="recording",
        actor="director",
        data={"session_id": "rec_01", "state": "active"},
    )
    witness.record_event(
        "broadcast.program_frame",
        source="recorder",
        actor="director",
        data={"program": "wide_shot", "preview": "close_up"},
    )

    result = witness.verify()
    assert result.ok is True
    assert result.checked >= 3


def test_blackbox_operator_routes_do_not_expose_records(tmp_path: Path):
    witness = create_blackbox_witness(tmp_path, session_id="shoot_01")
    witness.record_event("runtime.error", source="system", actor="SYS", data={"code": "E1"})

    app = FastAPI()
    app.include_router(create_blackbox_router(witness))
    client = TestClient(app)

    status = client.get("/api/operator/blackbox/status", headers={"X-Client-Id": "owner"})
    assert status.status_code == 200
    body = status.json()
    assert body["player_menu_exposed"] is False
    assert body["record_contents_exposed"] is False
    assert "records" not in body

    verify = client.get("/api/operator/blackbox/verify", headers={"X-Client-Id": "owner"})
    assert verify.status_code == 200
    assert verify.json()["ok"] is True
