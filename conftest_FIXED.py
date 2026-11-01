"""
conftest.py — PubCast AI startup test fixtures
═══════════════════════════════════════════════
Provides two levels of test client:

  client_no_lifespan — raw app with no startup/shutdown, for import/route
                       structure tests that don't need services running.

  client             — full TestClient run through the real lifespan.
                       Every service will have initialised. Use this for
                       testing startup reliability and endpoint responses.

The lifespan client is session-scoped: the app boots once, all startup tests
run against it, and it shuts down cleanly at the end of the session.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

# ── Make sure the project root is on sys.path ─────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ── Raw app (no lifespan) — for structural tests ──────────────────────────────
@pytest.fixture(scope="session")
def raw_app():
    """Import the FastAPI app without triggering lifespan."""
    import main  # noqa: PLC0415
    return main.app


@pytest.fixture(scope="session")
def client_no_lifespan(raw_app):
    """TestClient that does NOT run startup/shutdown.
    Use for route-structure and import tests only."""
    # raise_server_exceptions=False so structural tests don't explode on
    # uninitialised singletons being called.
    with TestClient(raw_app, raise_server_exceptions=False) as c:
        yield c


# ── Full lifespan client — services actually start ────────────────────────────
@pytest.fixture(scope="session")
def client():
    """TestClient that runs the full lifespan.
    Hub, BYOK, Jeremy Cricket, Studio Control, etc. all boot.
    Rust animation bridge timeout is handled gracefully by the lifespan itself.
    """
    import main  # noqa: PLC0415
    with TestClient(main.app, raise_server_exceptions=True) as c:
        yield c


# ── Convenience: give tests access to main module globals post-startup ─────────
@pytest.fixture(scope="session")
def main_module(client):          # client fixture ensures lifespan ran first
    import main  # noqa: PLC0415
    return main


# ── Per-test isolation of shared Hub state ────────────────────────────────────
# The `client` fixture is session-scoped (the lifespan is expensive), so every
# test shares one Hub instance. WebSocket tests that connect to /ws/{room} leave
# room entries behind, and later tests asserting on hub.rooms then fail for
# reasons that have nothing to do with what they're testing — six auth-parity
# tests passed in isolation but failed in a full run purely because of this.
#
# Snapshot and restore the room registry around each test so cross-test bleed
# can't produce false failures.
@pytest.fixture(autouse=True)
def _isolate_hub_rooms():
    try:
        import main  # noqa: PLC0415
        hub = getattr(main, "hub", None)
    except Exception:
        hub = None

    rooms = getattr(hub, "rooms", None) if hub is not None else None
    if not isinstance(rooms, dict):
        yield
        return

    before = {k: set(v) for k, v in rooms.items()}
    try:
        yield
    finally:
        rooms.clear()
        rooms.update(before)


# ── Per-test isolation of auth-enforcement env state ──────────────────────────
# PUBCAST_ENFORCE_AUTH flips global behaviour in modules/route_security.py.
# Tests that set it use monkeypatch (which restores), but any code path that
# sets it directly — or any cached state derived from it — can leak into later
# tests and produce failures unrelated to the test's own subject. Snapshot and
# restore it explicitly.
@pytest.fixture(autouse=True)
def _isolate_auth_env():
    import os  # noqa: PLC0415
    keys = ("PUBCAST_ENFORCE_AUTH", "PUBCAST_JWT_SECRET", "PUBCAST_AI_CONFIG_PATH")
    before = {k: os.environ.get(k) for k in keys}
    try:
        yield
    finally:
        for k, v in before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
