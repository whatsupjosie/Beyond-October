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
