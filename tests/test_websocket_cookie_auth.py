from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from modules import auth as auth_module
from modules import auth_routes, userdb
from modules.chat_rooms import _websocket_identity


def _make_user_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(userdb, "_DB_PATH", tmp_path / "users.db")
    asyncio.run(userdb.init_db())
    asyncio.run(userdb.create_user("owner-test", "secret", role="owner"))
    auth_routes.set_auth_instance(auth_module)


def _probe_app() -> FastAPI:
    app = FastAPI()

    @app.websocket("/probe")
    async def probe(ws: WebSocket):
        try:
            identity = _websocket_identity(ws)
        except ValueError as exc:
            await ws.close(code=1008, reason=str(exc))
            return
        await ws.accept()
        await ws.send_json(identity)

    return app


def test_login_verify_and_logout_manage_httponly_socket_cookie(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    _make_user_db(tmp_path, monkeypatch)
    app = FastAPI(); app.include_router(auth_routes.router)
    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"username": "owner-test", "password": "secret"})
        assert login.status_code == 200
        cookie = login.headers.get("set-cookie", "")
        assert "pubcast_ws_session=" in cookie
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie
        token = login.json()["access_token"]

        client.cookies.clear()
        verify = client.get("/api/auth/verify", headers={"Authorization": "Bearer " + token})
        assert verify.status_code == 200
        assert client.cookies.get("pubcast_ws_session") == token

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200
        assert client.cookies.get("pubcast_ws_session") is None


def test_websocket_accepts_cookie_and_authorization_header_not_query_by_default(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    monkeypatch.delenv("PUBCAST_ALLOW_LEGACY_WS_QUERY_TOKEN", raising=False)
    token = auth_module.create_access_token({"sub": "crew-test", "role": "crew"})
    app = _probe_app()

    with TestClient(app) as client:
        client.cookies.set("pubcast_ws_session", token)
        with client.websocket_connect("/probe") as ws:
            assert ws.receive_json()["user_id"] == "crew-test"

    with TestClient(app) as client:
        with client.websocket_connect("/probe", headers={"Authorization": "Bearer " + token}) as ws:
            assert ws.receive_json()["role"] == "crew"

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/probe?token=" + token) as ws:
                ws.receive_json()
        assert exc.value.code == 1008


def test_query_token_compatibility_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    monkeypatch.setenv("PUBCAST_ALLOW_LEGACY_WS_QUERY_TOKEN", "1")
    token = auth_module.create_access_token({"sub": "legacy-client", "role": "guest"})
    with TestClient(_probe_app()) as client:
        with client.websocket_connect("/probe?token=" + token) as ws:
            assert ws.receive_json()["user_id"] == "legacy-client"


def test_browser_sources_never_put_bearer_tokens_in_websocket_urls():
    root = Path(__file__).resolve().parents[1]
    helper = (root / "static" / "reach_auth.js").read_text(encoding="utf-8")
    widget = (root / "static" / "world_chat_widget.js").read_text(encoding="utf-8")
    assert "searchParams.set('token'" not in helper
    assert 'searchParams.set("token"' not in helper
    assert "searchParams.set('token'" not in widget
    assert 'searchParams.set("token"' not in widget
