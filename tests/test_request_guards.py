"""Regression coverage for the two front-door ASGI guards added in the merged-all audit.

The original tests for these guards were lost when the merged-all archive was
truncated. These exercise the shipped modules directly and through minimal apps,
so they do not depend on the full host lifespan.
"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from modules.control_plane_guard import CONTROL_ROUTES, ControlPlaneGuardMiddleware, is_control_route
from modules.unicode_guard import MAX_INSPECT, UnicodeGuardMiddleware, body_has_invalid_unicode


# -- Unicode guard: pure detection ----------------------------------------------------

@pytest.mark.parametrize("body", [
    b'{"text": "plain"}',
    b'{"text": "caf\\u00e9"}',
    b'{"text": "pair \\ud83d\\ude00 ok"}',          # valid surrogate pair (emoji)
    '{"text": "already utf-8 \U0001F600"}'.encode(),
    b'{"text": "escaped backslash \\\\ud800 is literal"}',
    b'{"text": "\\n\\t\\" escapes"}',
    b"",
])
def test_valid_bodies_pass(body):
    assert body_has_invalid_unicode(body) is False


@pytest.mark.parametrize("body", [
    b'{"text": "\\ud800"}',                         # lone high surrogate
    b'{"text": "\\udc00"}',                         # lone low surrogate
    b'{"text": "\\ud800x"}',                        # high not followed by low
    b'{"text": "\\ud800\\n\\udc00"}',               # interrupted pair
    b'{"text": "\\ud800\\ud800\\udc00"}',           # two highs
    b'{"text": "bad \xff byte"}',                   # not UTF-8
])
def test_invalid_bodies_rejected(body):
    assert body_has_invalid_unicode(body) is True


def _echo_app() -> FastAPI:
    app = FastAPI()

    @app.post("/echo")
    async def echo(payload: dict):
        return payload

    app.add_middleware(UnicodeGuardMiddleware)
    return app


def test_middleware_returns_400_for_unpaired_surrogate():
    with TestClient(_echo_app()) as client:
        r = client.post("/echo", content=b'{"text": "\\ud800"}',
                        headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert "invalid Unicode" in r.json()["detail"]


def test_middleware_replays_valid_body_unchanged():
    payload = {"text": "pair \U0001F600 and café", "n": 3}
    with TestClient(_echo_app()) as client:
        r = client.post("/echo", content=json.dumps(payload).encode(),
                        headers={"content-type": "application/json"})
    assert r.status_code == 200
    assert r.json() == payload


def test_middleware_ignores_non_json_bodies():
    app = FastAPI()

    @app.post("/raw")
    async def raw(request_body: bytes = b""):
        return {"ok": True}

    app.add_middleware(UnicodeGuardMiddleware)
    with TestClient(app) as client:
        r = client.post("/raw", content=b'\\ud800', headers={"content-type": "text/plain"})
    assert r.status_code != 400


def test_large_valid_body_is_not_rejected():
    # A valid body larger than the inspection window must reach the route intact.
    app = FastAPI()

    @app.post("/sink")
    async def sink(payload: dict):
        return {"length": len(payload["text"])}

    app.add_middleware(UnicodeGuardMiddleware)
    text = "a" * (MAX_INSPECT + 16)
    with TestClient(app) as client:
        r = client.post("/sink", content=json.dumps({"text": text}).encode(),
                        headers={"content-type": "application/json"})
    assert r.status_code == 200
    assert r.json() == {"length": len(text)}


def test_main_app_installs_unicode_guard():
    import main
    assert any(m.cls is UnicodeGuardMiddleware for m in main.app.user_middleware)


# -- Control-plane guard --------------------------------------------------------------

@pytest.mark.parametrize("method,path", [
    ("POST", "/api/vision/broadcast/start"),
    ("POST", "/api/vision/broadcast/stop"),
    ("POST", "/api/switcher/cut"),
    ("POST", "/api/switcher/transition"),
    ("POST", "/api/switcher/preview/cam2"),
    ("POST", "/api/stage/actor/pete"),
    ("DELETE", "/api/stage/actor/pete"),
    ("POST", "/api/audio/devices/select"),
    ("DELETE", "/api/mic/profiles/studio"),
    ("POST", "/api/boxer/override"),
    ("POST", "/api/performance/profile"),
])
def test_listed_control_routes_match(method, path):
    assert is_control_route(method, path)


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/vision/broadcast/start"),        # reads are not listed
    ("POST", "/api/switcher/cut/extra/segment"),
    ("POST", "/api/vision/broadcast/startx"),
    ("POST", "/api/chat"),
])
def test_unlisted_routes_do_not_match(method, path):
    assert not is_control_route(method, path)


def test_control_table_has_no_duplicates():
    keys = [(m, rx.pattern) for m, rx in CONTROL_ROUTES]
    assert len(keys) == len(set(keys))


def _control_app() -> FastAPI:
    app = FastAPI()

    @app.post("/api/switcher/cut")
    async def cut():
        return {"cut": True}

    @app.post("/api/chat")
    async def chat():
        return {"chat": True}

    app.add_middleware(ControlPlaneGuardMiddleware)
    return app


def test_control_route_open_when_auth_not_enforced(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    with TestClient(_control_app()) as client:
        assert client.post("/api/switcher/cut").status_code == 200


def test_control_route_denied_to_anonymous_when_enforced(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    with TestClient(_control_app()) as client:
        r = client.post("/api/switcher/cut")
        assert r.status_code in (401, 403)
        assert client.post("/api/chat").status_code == 200   # unlisted route untouched


def test_main_app_installs_control_plane_guard():
    import main
    assert any(m.cls is ControlPlaneGuardMiddleware for m in main.app.user_middleware)
