from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from modules import auth, auth_routes, userdb
from modules.route_security import require_role


@pytest.fixture
def auth_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(userdb, "_DB_PATH", tmp_path / "users.db")
    asyncio.run(userdb.init_db())
    auth_routes.set_auth_instance(auth)
    # Avoid cross-test limiter state for TestClient's stable source address.
    for limiter in (auth_routes._SETUP_LIMITER, auth_routes._LOGIN_LIMITER, auth_routes._GLOBAL_LOGIN_LIMITER):
        limiter._events.clear()
        limiter._last_seen.clear()
    app = FastAPI()
    app.include_router(auth_routes.router)

    @app.get("/protected")
    async def protected(identity=Depends(require_role("mod"))):
        return {"ok": True, "user": identity["user_id"], "role": identity["role"]}

    return app


def _strong_payload(username: str = "owner") -> dict:
    return {
        "username": username,
        "password": "Lantern!River9Stone",
        "confirm_password": "Lantern!River9Stone",
    }


def test_password_hash_and_tamper_resistant_token():
    hashed = auth.get_password_hash("Lantern!River9Stone")
    assert hashed.startswith("pbkdf2_sha256$600000$")
    assert auth.verify_password("Lantern!River9Stone", hashed)
    assert not auth.verify_password("wrong", hashed)

    token = auth.create_access_token({"sub": "owner", "role": "owner"}, expires_minutes=5)
    payload = auth.decode_access_token(token)
    assert payload and payload["sub"] == "owner"
    header, body, sig = token.split(".")
    replacement = ("A" if sig[-1] != "A" else "B")
    assert auth.decode_access_token(f"{header}.{body}.{sig[:-1]}{replacement}") is None


def test_first_run_setup_login_verify_and_protected_route(auth_app, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    with TestClient(auth_app) as client:
        status = client.get("/api/auth/status")
        assert status.status_code == 200
        assert status.json()["setup_required"] is True

        weak = _strong_payload()
        weak["password"] = weak["confirm_password"] = "password123"
        assert client.post("/api/auth/setup", json=weak).status_code == 400

        created = client.post("/api/auth/setup", json=_strong_payload())
        assert created.status_code == 201, created.text
        token = created.json()["access_token"]
        assert created.json()["role"] == "owner"

        second = client.post("/api/auth/setup", json=_strong_payload("other"))
        assert second.status_code == 409

        assert client.get("/protected").status_code == 401
        protected = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert protected.status_code == 200
        assert protected.json()["role"] == "owner"

        verified = client.get("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
        assert verified.status_code == 200
        assert verified.json()["username"] == "owner"

        assert client.post("/api/auth/login", json={"username": "owner", "password": "wrong"}).status_code == 401
        login = client.post("/api/auth/login", json={"username": "owner", "password": "Lantern!River9Stone"})
        assert login.status_code == 200
        assert login.json()["role"] == "owner"


def test_atomic_first_owner_creation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(userdb, "_DB_PATH", tmp_path / "users.db")
    asyncio.run(userdb.init_db())

    async def race():
        return await asyncio.gather(
            userdb.create_owner_via_setup("owner_a", "Lantern!River9Stone"),
            userdb.create_owner_via_setup("owner_b", "Harbor!Cloud8Glass"),
        )

    results = asyncio.run(race())
    assert sorted(results) == [False, True]
    assert asyncio.run(userdb.count_users()) == 1


def test_auth_limiter_is_bounded():
    from modules.auth_rate_limit import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(limit=2, window_seconds=60, max_keys=3)
    assert limiter.allow("a").allowed
    assert limiter.allow("a").allowed
    blocked = limiter.allow("a")
    assert not blocked.allowed and blocked.retry_after >= 1
    for key in ("b", "c", "d", "e"):
        limiter.allow(key)
    key_count, _ = limiter.snapshot()
    assert key_count <= 3


def test_frontend_and_launcher_auth_wiring():
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "pubpartner.html").read_text(encoding="utf-8")
    js = (root / "static" / "pubpartner.js").read_text(encoding="utf-8")
    launcher = (root / "run_pubpartner.py").read_text(encoding="utf-8")
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")

    assert 'id="authGate"' in html
    assert '<script src="/static/reach_auth.js"></script>' in html
    # PubPartner constructs the auth route dynamically; do not require a stale
    # literal /api/auth/setup string that would duplicate implementation detail.
    assert "'/api/' + 'auth/' + mode" in js or "`/api/auth/${mode}`" in js
    assert "Bearer ${authState.token}" in js
    assert "PUBCAST_ENFORCE_AUTH" in launcher
    assert "--unsafe-no-auth" in launcher
    assert "python-jose" not in requirements
    assert "passlib" not in requirements


def test_pubpartner_routes_are_protected_when_auth_is_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from modules import pubpartner_routes

    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    app = FastAPI()
    app.include_router(pubpartner_routes.router)
    token = auth.create_access_token({"sub": "owner", "role": "owner"})

    with TestClient(app) as client:
        assert client.get("/api/pubpartner/status").status_code == 401
        response = client.get("/api/pubpartner/status", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["ok"] is True
