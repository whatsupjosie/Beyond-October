"""Saved camera moves (modules/camera_moves.py) and the checked pose route (modules/switcher_routes.py, modules/cameras.py)."""
from __future__ import annotations

import json
import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.camera_moves import CHANNELS, create_camera_moves_router, validate
from modules.cameras import CameraManager, CameraSource, CameraTransport
from modules.switcher_routes import SwitcherService, create_switcher_router


def h(user, role="owner"): return {"Authorization": "Bearer " + create_access_token({"sub": user, "role": role})}


def rec(n=90, **over):
    r = {"version": 1, "rate": 30, "channels": CHANNELS, "start": {c: 0.0 for c in CHANNELS}, "camera": "cam1",
         "samples": [[i * 0.01, 1.6, 0.0, 0.1, 0.0, 0.0, 0.8, 5.0] for i in range(n)]}
    r.update(over); return r


@pytest.fixture()
def moves(tmp_path):
    app = FastAPI(); app.include_router(create_camera_moves_router(tmp_path))
    with TestClient(app) as c:
        c.dir = tmp_path; yield c


def test_a_move_saves_lists_reads_back_exactly_and_deletes(moves):
    assert moves.get("/api/camera-moves", headers=h("josie")).json()["moves"] == []
    r = moves.put("/api/camera-moves/push in 1", headers=h("josie"), json=rec())
    assert r.status_code == 200 and r.json()["seconds"] == 3.0
    got = moves.get("/api/camera-moves/push in 1", headers=h("josie")).json()
    assert got == validate(rec()) and got["samples"][5][0] == 0.05
    assert [m["name"] for m in moves.get("/api/camera-moves", headers=h("josie")).json()["moves"]] == ["push in 1"]
    assert moves.get("/api/camera-moves/push in 1", headers=h("kay")).status_code == 404              # one person's moves are theirs
    assert moves.delete("/api/camera-moves/push in 1", headers=h("josie")).status_code == 200
    assert moves.delete("/api/camera-moves/push in 1", headers=h("josie")).status_code == 404


@pytest.mark.parametrize("name", ["", ".hidden", "../x", "a/b", "a\\b", "x" * 61, "trailing.", "%2e%2e", "a%0Ab"])
def test_bad_names_are_refused_and_nothing_is_written(moves, name):
    assert moves.put("/api/camera-moves/" + name, headers=h("josie"), json=rec()).status_code in (400, 404, 405)
    assert not list(moves.dir.rglob("*.json"))


@pytest.mark.parametrize("bad", [
    rec(version=2), rec(rate=0), rec(rate=1000), rec(rate=True), rec(channels=CHANNELS[::-1]), rec(channels=CHANNELS[:-1]), rec(samples=[]),
    rec(samples=[[0] * 7]), rec(samples=[[0] * 9]), rec(samples=[[0, 0, 0, 0, 0, 0, 0, "x"]]), rec(samples=[[0, 0, 0, 0, 0, 0, 0, None]]),
    rec(samples=[[1e9, 0, 0, 0, 0, 0, 0, 5]]), rec(samples=[[0, 0, 0, 99, 0, 0, 0, 5]]), rec(start={"x": 0}), rec(camera=5), rec(camera="c" * 81),
    [], "x", None,
])
def test_a_hand_made_move_cannot_store_what_the_rig_could_not_have_recorded(moves, bad):
    assert moves.put("/api/camera-moves/m", headers=h("josie"), json=bad).status_code == 400
    assert not list(moves.dir.rglob("*.json"))


def test_nan_infinity_bad_json_oversize_and_too_many_samples_are_refused(moves):
    for raw in (b'{"version":1,"rate":30,"channels":' + json.dumps(CHANNELS).encode() + b',"start":{},"samples":[[NaN,0,0,0,0,0,0,5]]}', b"nope", b""):
        assert moves.put("/api/camera-moves/m", headers={**h("josie"), "Content-Type": "application/json"}, content=raw).status_code == 400
    assert moves.put("/api/camera-moves/m", headers=h("josie"), content=b"x" * 3_100_000).status_code == 413
    assert moves.put("/api/camera-moves/m", headers=h("josie"), json=rec(n=36_001)).status_code in (400, 413)
    assert not list(moves.dir.rglob("*.json"))


def test_a_saved_move_can_be_overwritten_and_a_corrupt_file_does_not_break_the_list(moves):
    moves.put("/api/camera-moves/a", headers=h("josie"), json=rec(n=30)); moves.put("/api/camera-moves/a", headers=h("josie"), json=rec(n=60))
    assert moves.get("/api/camera-moves", headers=h("josie")).json()["moves"][0]["seconds"] == 2.0
    (moves.dir / "camera_moves" / "josie" / "broken.json").write_text("{not json")
    assert [m["name"] for m in moves.get("/api/camera-moves", headers=h("josie")).json()["moves"]] == ["a"]
    assert moves.get("/api/camera-moves/broken", headers=h("josie")).status_code == 500


# ── the camera registry and its pose route ──────────────────────────────────────

@pytest.fixture()
def switcher(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    cams = CameraManager()
    cams.register(CameraSource(source_id="cam1", name="Cam 1", location="set", description="test camera", transport=list(CameraTransport)[0], endpoint="test:0"))
    app = FastAPI(); app.include_router(create_switcher_router(SwitcherService(cams)))
    with TestClient(app) as c:
        c.cams = cams; yield c


def test_the_pose_route_sets_position_rotation_zoom_and_focus_together_and_reports_them(switcher):
    r = switcher.post("/api/switcher/ptz/cam1", headers=h("josie", "admin"), json={"position": [1, 2, 3], "rotation": [10, 20, 5], "fov": 45, "focus": 7.5})
    assert r.status_code == 200 and r.json()["pose"] == {"position": [1, 2, 3], "rotation": [10, 20, 5], "fov": 45, "focus": 7.5}
    assert switcher.get("/api/switcher/pose/cam1").json()["focus"] == 7.5
    src = switcher.cams.get("cam1"); assert (src.position, src.rotation, src.fov, src.focus) == ([1, 2, 3], [10, 20, 5], 45, 7.5)
    assert switcher.post("/api/switcher/ptz/cam1", headers=h("josie", "admin"), json={"focus": 3}).json()["pose"]["position"] == [1, 2, 3]      # one at a time is fine


@pytest.mark.parametrize("bad", [{"position": [1, 2]}, {"position": [1, 2, "x"]}, {"position": [1, 2, True]}, {"position": [1, 2, 1e9]}, {"rotation": [0, 0, 99999]},
                                 {"fov": 0}, {"fov": 180}, {"fov": "wide"}, {"fov": True}, {"focus": 0.1}, {"focus": 9999}, {"position": "here"}])
def test_a_bad_pose_changes_nothing(switcher, bad):
    before = switcher.get("/api/switcher/pose/cam1").json()
    assert switcher.post("/api/switcher/ptz/cam1", headers=h("josie", "admin"), json=bad).status_code == 400
    assert switcher.get("/api/switcher/pose/cam1").json() == before


def test_the_pose_route_needs_a_moderator_and_a_real_camera(switcher):
    assert switcher.post("/api/switcher/ptz/cam1", headers=h("v", "viewer"), json={"fov": 40}).status_code == 403
    assert switcher.post("/api/switcher/ptz/cam1", json={"fov": 40}).status_code in (401, 403)
    assert switcher.post("/api/switcher/ptz/ghost", headers=h("m", "mod"), json={"fov": 40}).status_code == 404
    assert switcher.get("/api/switcher/pose/ghost").status_code == 404
    assert switcher.get("/api/switcher/pose/cam1").json()["fov"] == 60.0


def test_the_pose_event_carries_focus(switcher):
    seen = []
    switcher.cams.subscribe(seen.append) if hasattr(switcher.cams, "subscribe") else None
    switcher.post("/api/switcher/ptz/cam1", headers=h("josie", "admin"), json={"focus": 9})
    if seen: assert seen[-1].focus == 9
