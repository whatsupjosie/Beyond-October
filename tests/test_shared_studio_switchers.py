"""Both environments must use the one canonical camera switcher and audio program state."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.cameras import create_default_cameras
from modules.program_audio import ProgramAudioState, apply_audio_event, validate_audio_event
from modules.switcher_routes import SwitcherService, create_switcher_router


def header(role="owner"):
    return {"Authorization": "Bearer " + create_access_token({"sub": "director", "role": role})}


def test_shared_cut_swaps_actual_program_and_preview():
    svc = SwitcherService(create_default_cameras())
    assert svc.state()["program"] == "wide_shot"
    assert svc.state()["preview"] == "medium_shot"
    assert svc.cut() is True
    assert svc.state()["program"] == "medium_shot"
    assert svc.state()["preview"] == "wide_shot"
    assert svc.state()["transition"] == {"type": "cut", "duration_ms": 0}
    assert svc.auto(transition="dissolve", duration_ms=600) is True
    assert svc.state()["program"] == "wide_shot"
    assert svc.state()["preview"] == "medium_shot"
    assert svc.state()["transition"]["type"] == "dissolve"
    assert svc.state()["transition"]["duration_ms"] == 600
    assert isinstance(svc.state()["transition"]["started_at"], float)


def test_bad_transition_does_not_mutate_switcher():
    svc = SwitcherService(create_default_cameras())
    before = svc.state()
    with pytest.raises(ValueError): svc.auto(transition="explosion")
    with pytest.raises(ValueError): svc.auto(duration_ms=-1)
    with pytest.raises(ValueError): svc.auto(duration_ms=True)
    assert svc.state() == before


def test_video_switcher_mutations_require_moderator(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    app = FastAPI()
    app.include_router(create_switcher_router(SwitcherService(create_default_cameras())))
    with TestClient(app) as c:
        for url in ("/api/switcher/cut", "/api/switcher/cut/close_up",
                    "/api/switcher/preview/close_up", "/api/switcher/transition"):
            body = {"type": "dissolve", "duration_ms": 400} if url.endswith("transition") else None
            assert c.post(url, json=body).status_code in (401, 403), url
            assert c.post(url, json=body, headers=header("viewer")).status_code == 403, url
        assert c.post("/api/switcher/preview/close_up", headers=header()).status_code == 200
        result = c.post("/api/switcher/cut", headers=header())
        assert result.status_code == 200
        assert result.json()["program"] == "close_up"
        assert result.json()["preview"] == "wide_shot"
        invalid = c.post("/api/switcher/transition", headers=header(), json={"type": "dissolve", "duration_ms": "oops"})
        assert invalid.status_code == 400


def test_one_audio_master_and_existing_bus_controls():
    state = ProgramAudioState()
    assert state.status()["master_volume"] == 1.0
    assert apply_audio_event(state, {"action": "set_volume", "bus": "master", "volume": 0.3})["master_volume"] == 0.3
    assert state.status()["buses"]["dialogue"]["volume"] == 1.0
    apply_audio_event(state, {"action": "set_volume", "bus": "dialogue", "volume": 0.45})
    apply_audio_event(state, {"action": "set_volume", "bus": "music", "volume": 0.2})
    assert state.status()["buses"]["dialogue"]["volume"] == 0.45
    assert state.status()["buses"]["music"]["volume"] == 0.2
    assert validate_audio_event({"action": "set_volume", "bus": "master", "volume": 5})["volume"] == 1.0
    with pytest.raises(ValueError): validate_audio_event({"action": "play", "bus": "master"})


def test_stage_camera_pair_activation_is_checked_before_any_switch():
    svc = SwitcherService(create_default_cameras())
    before = svc.state()
    assert svc.select("wide_shot", "missing_camera") is False
    assert svc.state() == before
    assert svc.select("close_up", "overhead") is True
    assert svc.state()["program"] == "close_up"
    assert svc.state()["preview"] == "overhead"


def test_atomic_activation_route_is_authorized_and_rejects_partial_ids(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    app = FastAPI()
    app.include_router(create_switcher_router(SwitcherService(create_default_cameras())))
    with TestClient(app) as c:
        endpoint = "/api/switcher/select"
        pair = {"program": "wide_shot", "preview": "close_up"}
        assert c.post(endpoint, json=pair).status_code in (401, 403)
        assert c.post(endpoint, json=pair, headers=header("viewer")).status_code == 403
        before = c.get("/api/switcher/state").json()
        fail = c.post(endpoint, json={"program": "wide_shot", "preview": "nonexistent"}, headers=header())
        assert fail.status_code == 404
        assert c.get("/api/switcher/state").json() == before
        response = c.post(endpoint, json=pair, headers=header())
        assert response.status_code == 200 and response.json()["preview"] == "close_up"
def test_production_video_cues_survive_hub_persistence(tmp_path):
    from modules.hub import Hub
    hub = Hub(tmp_path)
    cue = {"panic_seq": 1000.125, "blackout": True, "blackout_seq": 1000.125,
           "preview_bars": True, "preview_bars_seq": 999.75}
    hub.update_production_state(cue)
    persisted = Hub(tmp_path).get_production_state()
    assert {key: persisted[key] for key in cue} == cue
