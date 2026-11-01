"""Adversarial tests for actual 2.5D frame publication and remote confidence viewing.

The JPEG fixture is a real 64x64 image, not forged byte markers. These test
files must be executed in a full checkout; mere presence is not a pass.
"""
from __future__ import annotations

import base64
import asyncio

import httpx
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.cameras import CameraSource, CameraTransport, create_default_cameras
from modules.studio25d_media_routes import (
    MAX_BYTES, create_studio25d_media_router, jpeg_dimensions,
)

JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABIMDRANCxIQDhAUExIVGywdGxgYGzYnKSAsQDlEQz85Pj1HUGZXR0thTT0+WXlaYWlt"
    "cnNyRVV9hnxvhWZwcm7/2wBDARMUFBsXGzQdHTRuST5Jbm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5u"
    "bm5ubm5ubm7/wAARCABAAEADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAT/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QA"
    "FgEBAQEAAAAAAAAAAAAAAAAAAAME/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AkAaEAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAH/2Q=="
)

SOURCE = "p25d_news_wide"
SESSION = "pubcast25d-test-session-001"
SECOND = "pubcast25d-test-session-002"


def h(role="owner", session=SESSION, actor="operator"):
    token = create_access_token({"sub": actor, "role": role})
    return {"Authorization": "Bearer " + token, "X-Studio-Session": session, "Content-Type": "image/jpeg"}


def server():
    now = [1000.0]
    cameras = create_default_cameras()
    cameras.register(CameraSource(
        source_id=SOURCE, name="News wide", location="studio25d",
        description="Browser-origin confidence producer", transport=CameraTransport.VIRTUAL,
        endpoint="virtual://" + SOURCE, tags=["studio25d", "news"],
    ))
    app = FastAPI()
    app.include_router(create_studio25d_media_router(cameras, clock=lambda: now[0]))
    return TestClient(app), now


def test_actual_jpeg_decodes_and_is_bounded():
    assert jpeg_dimensions(JPEG) == (64, 64)


def test_anonymous_view_and_publish_never_allowed_even_in_dev_mode(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    c, _ = server()
    assert c.get("/api/studio25d/media/status").status_code == 403
    assert c.get("/api/studio25d/media/frames/" + SOURCE).status_code == 403
    assert c.post("/api/studio25d/media/frames/" + SOURCE, content=JPEG,
                  headers={"X-Studio-Session": SESSION, "Content-Type": "image/jpeg"}).status_code == 403
    assert c.post("/api/studio25d/media/frames/" + SOURCE, content=JPEG, headers=h("viewer")).status_code == 403


def test_frame_roundtrip_sequence_content_and_freshness():
    c, now = server()
    path = "/api/studio25d/media/frames/" + SOURCE
    result = c.post(path, content=JPEG, headers=h())
    assert result.status_code == 200, result.text
    assert result.json()["sequence"] == 1
    response = c.get(path, headers=h())
    assert response.status_code == 200 and response.content == JPEG
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.headers["cache-control"].startswith("no-store")
    assert response.headers["x-studio-frame-width"] == "64"
    assert response.headers["x-studio-frame-height"] == "64"
    assert len(c.get("/api/studio25d/media/status", headers=h()).json()["fresh_sources"]) == 1
    now[0] += 0.2
    assert c.post(path, content=JPEG, headers=h()).json()["sequence"] == 2
    now[0] += 5.1
    assert c.get(path, headers=h()).status_code == 503
    assert c.get("/api/studio25d/media/status", headers=h()).json()["fresh_sources"] == []


def test_rate_limit_and_lease_hijack_rejected():
    c, now = server()
    path = "/api/studio25d/media/frames/" + SOURCE
    assert c.post(path, content=JPEG, headers=h()).status_code == 200
    assert c.post(path, content=JPEG, headers=h()).status_code == 429
    now[0] += 0.2
    assert c.post(path, content=JPEG, headers=h(session=SECOND)).status_code == 409
    assert c.post(path, content=JPEG, headers=h(actor="different", session=SESSION)).status_code == 409


def test_cleanup_rejects_in_flight_late_frames():
    c, now = server()
    path = "/api/studio25d/media/frames/" + SOURCE
    assert c.post(path, content=JPEG, headers=h()).status_code == 200
    deleted = c.delete("/api/studio25d/media/sessions/" + SESSION, headers=h())
    assert deleted.status_code == 200
    assert SOURCE in deleted.json()["released"]
    assert c.get(path, headers=h()).status_code == 503
    assert c.post(path, content=JPEG, headers=h()).status_code == 410
    assert c.post(path, content=JPEG, headers=h(session=SECOND)).status_code == 200


def test_malformed_media_and_unregistered_sources_are_rejected():
    c, now = server()
    path = "/api/studio25d/media/frames/" + SOURCE
    assert c.post(path, content=b"x" * (MAX_BYTES + 1), headers=h()).status_code == 413
    assert c.post(path, content=b"x" * 500, headers=h()).status_code == 422
    assert c.post(path, content=JPEG, headers=h(session="bad")).status_code == 400
    assert c.post(path, content=JPEG, headers={**h(), "Content-Type": "image/png"}).status_code == 415
    assert c.post("/api/studio25d/media/frames/p25d_unknown_other", content=JPEG, headers=h()).status_code == 404
    assert c.get("/api/studio25d/media/frames/wide_shot", headers=h()).status_code == 400


@pytest.mark.parametrize("interruption,expected", [("other_owner", 409), ("same_owner", 429), ("release", 410)])
async def test_upload_revalidates_lease_after_waiting_for_body(interruption, expected):
    """A slow upload must not overwrite another publisher or resurrect a release."""
    c, _ = server()
    started, resume = asyncio.Event(), asyncio.Event()

    async def delayed_body():
        yield JPEG[:20]
        started.set()
        await resume.wait()
        yield JPEG[20:]

    path = "/api/studio25d/media/frames/" + SOURCE
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url="http://test") as client:
        pending = asyncio.create_task(client.post(path, content=delayed_body(), headers=h()))
        await started.wait()
        try:
            if interruption == "release":
                result = await client.delete("/api/studio25d/media/sessions/" + SESSION, headers=h())
            else:
                competing = h(session=SECOND, actor="other") if interruption == "other_owner" else h()
                result = await client.post(path, content=JPEG, headers=competing)
            assert result.status_code == 200, result.text
        finally:
            resume.set()
        response = await pending
        assert response.status_code == expected, response.text
