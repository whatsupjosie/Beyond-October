"""Consent, quotas, revocation and actual media boundaries for camera pooling."""
import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.camera_pool import CameraPool, create_camera_pool_router
from modules.cameras import CameraSource, CameraTransport, create_default_cameras
from modules.studio25d_media_routes import create_studio25d_media_router
from tests.test_studio25d_media_routes import JPEG

SOURCE = "p25d_news_anchor"
OTHER = "p25d_news_wide"


def auth(actor="director", role="owner"):
    return {"Authorization": "Bearer " + create_access_token({"sub": actor, "role": role})}


def setup():
    now = [100.0]
    cameras = create_default_cameras()
    for source in (SOURCE, OTHER):
        cameras.register(CameraSource(source, source, "studio25d", "preview", CameraTransport.VIRTUAL,
                                      "virtual://" + source, tags=["studio25d", "news"]))
    pool = CameraPool(cameras, clock=lambda: now[0])
    app = FastAPI()
    app.include_router(create_camera_pool_router(pool))
    app.include_router(create_studio25d_media_router(cameras, pool=pool, clock=lambda: now[0]))
    return app, pool, now


def fixture():
    app, pool, now = setup()
    c = TestClient(app)
    sid = c.post("/api/camera-pool/sessions", json={"package": "news"}, headers=auth()).json()["id"]
    base = "/api/camera-pool/sessions/" + sid
    c.put(base + "/scene", json={"package": "news", "performers": []}, headers=auth()).raise_for_status()
    body = {"consent": True, "label": "Buddy", "limits": {"max_cameras": 1, "max_fps": 2, "max_upload_kbps": 256}}
    pid = c.post(base + "/join", json=body, headers=auth("buddy", "viewer")).json()["participant_id"]
    c.post(base + "/assignments", json={"source_id": SOURCE, "participant_id": pid, "fps": 2}, headers=auth()).raise_for_status()
    grant = pool.get(sid)["assignments"][SOURCE]["grant"]
    headers = auth("buddy", "viewer") | {"X-Camera-Pool": sid, "X-Pool-Participant": pid,
               "X-Pool-Grant": grant, "X-Studio-Session": pid, "Content-Type": "image/jpeg", "X-Pool-Scene-Version": "1"}
    return app, c, pool, now, sid, base, pid, headers


def test_consent_identity_and_director_boundaries(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    _, c, _, _, _, base, pid, _ = fixture()
    assert c.post(base + "/join", json={"consent": True, "label": "anonymous"}).status_code == 403
    assert c.post(base + "/join", json={"consent": False, "label": "no"}, headers=auth("other")).status_code == 422
    assert c.post(base + "/join", json={"consent": 1, "label": "no"}, headers=auth("other")).status_code == 422
    assert c.get(base, headers=auth("outsider")).status_code == 403
    assert c.post(base + "/assignments", json={"source_id": OTHER, "participant_id": pid}, headers=auth("buddy", "viewer")).status_code == 403
    assert c.delete(base + "/participants/" + pid, headers=auth("outsider")).status_code == 403
    assert c.post("/api/camera-pool/sessions", json={"package": []}, headers=auth()).status_code == 422


def test_task_count_fps_and_nonconsenting_assignments_cannot_exceed_limits():
    _, c, _, _, _, base, pid, _ = fixture()
    assert c.post(base + "/assignments", json={"source_id": OTHER, "participant_id": pid}, headers=auth()).status_code == 409
    assert c.post(base + "/assignments", json={"source_id": SOURCE, "participant_id": pid, "fps": 3}, headers=auth()).status_code == 409
    assert c.post(base + "/assignments", json={"source_id": OTHER, "participant_id": "not-consenting"}, headers=auth()).status_code == 409


def test_actual_frame_upload_delivery_and_server_measured_traffic():
    _, c, _, now, _, base, pid, headers = fixture()
    path = "/api/studio25d/media/frames/" + SOURCE
    assert c.post(path, content=JPEG, headers=headers).status_code == 200
    response = c.get(path, headers=auth())
    assert response.content == JPEG
    assert c.get(path, headers=auth("buddy", "viewer")).status_code == 200
    assert c.get(path, headers=auth("outsider", "viewer")).status_code == 403
    row = c.get(base, headers=auth()).json()["members"][0]
    assert row["frames"] == 1 and row["bytes"] == len(JPEG)
    assert row["upload_kbps"] > 0 and row["relay_out_kbps"] > 0
    assert {flow["to"] for flow in c.get(base, headers=auth()).json()["flows"]} == {"director", "buddy"}
    assert c.post(path, content=JPEG, headers=headers).status_code == 429
    now[0] += .6
    assert c.post(path, content=JPEG, headers=headers).status_code == 200
    assert c.post(path, content=JPEG, headers=auth() | {"X-Studio-Session": "local-session-001", "Content-Type": "image/jpeg"}).status_code == 409


def test_withdrawal_invalidates_frames_and_old_grants_immediately():
    _, c, _, _, _, base, pid, headers = fixture()
    path = "/api/studio25d/media/frames/" + SOURCE
    assert c.post(path, content=JPEG, headers=headers).status_code == 200
    assert c.delete(base + "/participants/" + pid, headers=auth("buddy", "viewer")).status_code == 200
    assert c.get(path, headers=auth()).status_code == 503
    assert c.post(path, content=JPEG, headers=headers).status_code == 410
    assert c.get(base, headers=auth()).json()["assignments"] == []


def test_heartbeat_expiry_scene_staleness_and_lower_limits_release_work():
    _, c, _, now, _, base, pid, headers = fixture()
    path = "/api/studio25d/media/frames/" + SOURCE
    now[0] += 6.1
    assert c.post(path, content=JPEG, headers=headers).status_code == 409
    c.put(base + "/scene", json={"package": "news", "performers": []}, headers=auth()).raise_for_status()
    c.post(base + "/assignments", json={"source_id": SOURCE, "participant_id": pid}, headers=auth()).raise_for_status()
    headers["X-Pool-Grant"] = c.get(base, headers=auth("buddy", "viewer")).json()["assignments"][0]["grant"]
    assert c.post(path, content=JPEG, headers=headers).status_code == 200
    assert c.put(base + "/participants/" + pid + "/limits", json={"max_cameras": 1, "max_fps": 1}, headers=auth("buddy", "viewer")).status_code == 200
    assert c.get(base, headers=auth()).json()["assignments"] == []
    now[0] += 6
    assert c.get(base, headers=auth()).json()["members"][0]["active"] is False
    assert c.post(base + "/participants/" + pid + "/heartbeat", headers=auth("buddy", "viewer")).status_code == 410


def test_reassignment_cannot_reuse_previous_grant():
    _, c, _, now, _, base, pid, headers = fixture()
    path = "/api/studio25d/media/frames/" + SOURCE
    assert c.post(path, content=JPEG, headers=headers).status_code == 200
    now[0] += 1
    c.post(base + "/assignments", json={"source_id": SOURCE, "participant_id": pid}, headers=auth()).raise_for_status()
    assert c.post(path, content=JPEG, headers=headers).status_code == 409
    assert c.get(path, headers=auth()).status_code == 503


def test_upload_quota_is_committed_only_after_real_frame_validation():
    _, c, pool, _, sid, _, _, headers = fixture()
    path = "/api/studio25d/media/frames/" + SOURCE
    assert c.post(path, content=b"bad", headers=headers).status_code == 422
    assert pool.get(sid)["members"][headers["X-Pool-Participant"]]["bytes"] == 0
    big = JPEG[:-2] + b"0" * 40000 + JPEG[-2:]
    assert c.post(path, content=big, headers=headers).status_code == 429
    assert c.post(path, content=JPEG, headers=headers).status_code == 200


def test_releasing_an_unassigned_camera_cannot_erase_someone_elses_feed():
    _, c, _, _, _, base, _, headers = fixture()
    path = "/api/studio25d/media/frames/" + SOURCE
    c.post(path, content=JPEG, headers=headers).raise_for_status()
    other = c.post("/api/camera-pool/sessions", json={"package": "news"}, headers=auth("other-director")).json()["id"]
    result = c.delete(f"/api/camera-pool/sessions/{other}/assignments/{SOURCE}", headers=auth("other-director"))
    assert result.status_code == 404
    assert c.get(path, headers=auth()).content == JPEG


def test_program_promotion_revokes_a_preview_job_and_rejects_late_uploads():
    _, c, pool, _, _, base, pid, headers = fixture()
    path = "/api/studio25d/media/frames/" + SOURCE
    c.post(path, content=JPEG, headers=headers).raise_for_status()
    pool.cameras.set_program_source(SOURCE)
    assert c.post(path, content=JPEG, headers=headers).status_code == 409
    assert c.get(path, headers=auth()).status_code == 503
    assert c.get(base, headers=auth()).json()["assignments"] == []
    assert c.post(base + "/assignments", json={"source_id": SOURCE, "participant_id": pid}, headers=auth()).status_code == 409


def test_changing_scene_rejects_old_content_and_invalidates_existing_frames():
    _, c, _, now, _, base, _, headers = fixture()
    path = "/api/studio25d/media/frames/" + SOURCE
    headers["X-Pool-Scene-Version"] = "1"
    c.post(path, content=JPEG, headers=headers).raise_for_status()
    now[0] += 1
    c.put(base + "/scene", json={"package": "news", "performers": [], "lowerText": "New scene"}, headers=auth()).raise_for_status()
    assert c.get(path, headers=auth()).status_code == 503
    assert c.post(path, content=JPEG, headers=headers).status_code == 409
    headers["X-Pool-Scene-Version"] = "2"
    assert c.post(path, content=JPEG, headers=headers).status_code == 200


def test_stale_director_releases_reservations_and_orphan_sessions_are_reaped():
    _, c, pool, now, sid, base, _, _ = fixture()
    now[0] += 6.1
    assert pool.reservation(SOURCE) is None
    assert c.get(base, headers=auth()).json()["assignments"] == []
    now[0] += 60
    assert c.get(base, headers=auth()).status_code == 404


def test_unchanged_scene_heartbeat_preserves_version_and_frames():
    _, c, _, now, _, base, _, headers = fixture()
    path = "/api/studio25d/media/frames/" + SOURCE
    c.post(path, content=JPEG, headers=headers).raise_for_status()
    now[0] += 1
    result = c.put(base + "/scene", json={"package": "news", "performers": []}, headers=auth())
    assert result.json()["sequence"] == 1
    assert c.get(path, headers=auth()).content == JPEG


def test_stale_release_cannot_cancel_a_new_assignment():
    _, c, _, _, _, base, pid, _ = fixture()
    old = c.get(base, headers=auth()).json()["assignments"][0]["assignment_id"]
    c.post(base + "/assignments", json={"source_id": SOURCE, "participant_id": pid}, headers=auth()).raise_for_status()
    assert c.delete(base + "/assignments/" + SOURCE, params={"assignment_id": old}, headers=auth()).status_code == 409
    assert len(c.get(base, headers=auth()).json()["assignments"]) == 1


def test_reassigning_a_camera_does_not_reset_participant_fps_consent():
    _, c, _, now, _, base, pid, headers = fixture()
    path = "/api/studio25d/media/frames/" + SOURCE
    c.post(path, content=JPEG, headers=headers).raise_for_status()
    now[0] += .1
    c.post(base + "/assignments", json={"source_id": SOURCE, "participant_id": pid, "fps": 2}, headers=auth()).raise_for_status()
    headers["X-Pool-Grant"] = c.get(base, headers=auth("buddy", "viewer")).json()["assignments"][0]["grant"]
    assert c.post(path, content=JPEG, headers=headers).status_code == 429


@pytest.mark.asyncio
async def test_chunked_control_json_is_bounded_before_model_parsing():
    app, _, _ = setup()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        async def large():
            yield b'{"package":"news","padding":"'
            yield b'x' * 40000
            yield b'"}'
        response = await client.post("/api/camera-pool/sessions", content=large(), headers=auth() | {"Content-Type": "application/json"})
        assert response.status_code == 413


def test_inactive_members_do_not_permanently_exhaust_pool_capacity():
    _, c, pool, _, sid, base, _, _ = fixture()
    for i in range(40):
        result = c.post(base + "/join", json={"consent": True, "label": str(i)}, headers=auth("visitor"))
        assert result.status_code == 200
        c.delete(base + "/participants/" + result.json()["participant_id"], headers=auth("visitor")).raise_for_status()
    assert len(pool.get(sid)["members"]) <= 32


def test_removed_camera_releases_its_work_and_cached_frame():
    _, c, pool, _, _, base, _, headers = fixture()
    c.post("/api/studio25d/media/frames/" + SOURCE, content=JPEG, headers=headers).raise_for_status()
    pool.cameras.remove(SOURCE)
    assert pool.reservation(SOURCE) is None
    assert c.get(base, headers=auth()).json()["assignments"] == []


def test_nonfinite_or_deep_json_returns_validation_error_without_mutation():
    _, c, pool, _, sid, base, _, _ = fixture()
    result = c.put(base + "/scene", content=b'{"package":"news","performers":[],"scores":[NaN,0]}', headers=auth() | {"Content-Type": "application/json"})
    assert result.status_code == 400
    assert pool.get(sid)["sequence"] == 1
    deep = b'[' * 2000 + b'0' + b']' * 2000
    assert c.put(base + "/scene", content=deep, headers=auth() | {"Content-Type": "application/json"}).status_code == 400


def test_camera_pool_can_rearm_after_app_lifespan_shutdown():
    _, c, pool, _, _, base, _, _ = fixture()
    pool.close()
    assert pool._subscription is None
    pool.start()
    pool.start()
    sid = pool.create({"user_id": "director", "role": "owner"}, "news")
    session = pool.get(sid)
    session["assignments"][SOURCE] = {"participant_id": "unused"}
    pool.cameras.set_program_source(SOURCE)
    assert session["assignments"] == {}


@pytest.mark.asyncio
async def test_withdrawal_during_stream_read_prevents_late_commit():
    app, _, pool, _, sid, _, pid, headers = fixture()
    entered, resume = asyncio.Event(), asyncio.Event()

    async def stream():
        yield JPEG[:100]
        entered.set()
        await resume.wait()
        yield JPEG[100:]

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        task = asyncio.create_task(client.post("/api/studio25d/media/frames/" + SOURCE, content=stream(), headers=headers))
        await entered.wait()
        s = pool.get(sid)
        s["members"][pid]["active"] = False
        pool.drop_member_tasks(s, pid)
        resume.set()
        response = await task
        assert response.status_code == 410
        assert (await client.get("/api/studio25d/media/frames/" + SOURCE, headers=auth())).status_code == 503
