"""User-chosen passwords survive real setup, hashing and login unchanged."""
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from modules import auth, auth_routes, userdb


@pytest.mark.parametrize('password', ['cat', 'A', 'owner', 'password', ' ', ' 👑 cat ', 'x' * 300])
def test_any_nonempty_password_can_create_account_and_sign_in(tmp_path, monkeypatch, password):
    monkeypatch.setattr(userdb, '_DB_PATH', tmp_path / 'users.db')
    userdb._sync_init_db()
    monkeypatch.setattr(auth_routes, '_auth_module', auth)
    from modules.auth_rate_limit import SlidingWindowLimiter
    monkeypatch.setattr(auth_routes, '_SETUP_LIMITER', SlidingWindowLimiter(limit=5, window_seconds=600, max_keys=256))
    monkeypatch.setattr(auth_routes, '_LOGIN_LIMITER', SlidingWindowLimiter(limit=10, window_seconds=300, max_keys=2048))
    monkeypatch.setattr(auth_routes, '_GLOBAL_LOGIN_LIMITER', SlidingWindowLimiter(limit=60, window_seconds=60, max_keys=256))
    app = FastAPI(); app.include_router(auth_routes.router)
    with TestClient(app) as client:
        result = client.post('/api/auth/setup', json={'username':'owner','password':password,'confirm_password':password})
        assert result.status_code == 201, result.text
        stored = userdb._sync_get_user('owner')['hashed_password']
        assert stored != password and auth.verify_password(password, stored)
        assert client.post('/api/auth/login', json={'username':'owner','password':password}).status_code == 200
        assert client.post('/api/auth/login', json={'username':'owner','password':password+'wrong'}).status_code == 401
        assert client.post('/api/auth/login', json={'username':'owner','password':''}).status_code == 422
