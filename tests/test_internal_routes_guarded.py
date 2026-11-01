"""The /api/internal/* routes declare themselves internal-only (guest_visible
False) and expose filesystem paths, so they must not answer anonymous callers
when auth enforcement is on. Found by the anonymous-GET audit."""
import importlib
import sys

import pytest
from starlette.testclient import TestClient

INTERNAL = (
    "/api/internal/room-conductor/status",
    "/api/internal/pete/status",
    "/api/internal/pete/diagnostics",
    "/api/internal/pete/runtime-components",
)


@pytest.fixture()
def enforced_client(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    import main
    with TestClient(main.app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize("path", INTERNAL)
def test_internal_routes_reject_anonymous_when_enforced(enforced_client, path):
    assert enforced_client.get(path).status_code in (401, 403)


@pytest.mark.parametrize("path", INTERNAL)
def test_internal_routes_reject_guest_token(enforced_client, path):
    from modules.auth import create_access_token
    token = create_access_token({"sub": "guest-test", "role": "guest"})
    r = enforced_client.get(path, headers={"Authorization": "Bearer " + token})
    assert r.status_code in (401, 403)


@pytest.mark.parametrize("path", INTERNAL)
def test_internal_routes_allow_mod_token(enforced_client, path):
    from modules.auth import create_access_token
    token = create_access_token({"sub": "mod-test", "role": "mod"})
    r = enforced_client.get(path, headers={"Authorization": "Bearer " + token})
    assert r.status_code not in (401, 403)
