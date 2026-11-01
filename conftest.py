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

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

# ── Make sure the project root is on sys.path ─────────────────────────────────
ROOT = Path(__file__).resolve().parent

# Full-host tests previously booted against the build's real ``data/`` tree.
# That meant perfectly legitimate runtime persistence (BlackBox, room history,
# user profiles, SQLite stores, emergency-bridge commands, etc.) polluted the
# source candidate and made later tests order-dependent. Use the application's
# existing PUBCAST_DATA_DIR hook to give every pytest process a disposable copy
# of the realistic seed data *before main.py can be imported*. Direct fixture
# reads such as tests/test_ai_characters.py -> data/bots/*.json remain untouched.
_PYTEST_RUNTIME_DATA = Path(tempfile.mkdtemp(prefix="pubcast-pytest-data-"))
_SOURCE_DATA = ROOT / "data"
if _SOURCE_DATA.exists():
    shutil.copytree(_SOURCE_DATA, _PYTEST_RUNTIME_DATA, dirs_exist_ok=True)
_PREVIOUS_PUBCAST_DATA_DIR = os.environ.get("PUBCAST_DATA_DIR")
os.environ["PUBCAST_DATA_DIR"] = str(_PYTEST_RUNTIME_DATA)

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "modules" / "wired"))
sys.path.insert(0, str(ROOT / "pubpartner"))  # Import the single canonical federation package.
sys.path.insert(0, str(ROOT / "modules"))


def pytest_sessionfinish(session, exitstatus):
    """Remove disposable runtime state and restore the caller's environment."""
    if _PREVIOUS_PUBCAST_DATA_DIR is None:
        os.environ.pop("PUBCAST_DATA_DIR", None)
    else:
        os.environ["PUBCAST_DATA_DIR"] = _PREVIOUS_PUBCAST_DATA_DIR
    shutil.rmtree(_PYTEST_RUNTIME_DATA, ignore_errors=True)


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
