from __future__ import annotations

import textwrap
from pathlib import Path

from tools.route_inventory import build_inventory


def test_route_inventory_detects_matching_route(tmp_path: Path):
    (tmp_path / "modules").mkdir()
    (tmp_path / "static").mkdir()
    (tmp_path / "modules" / "camera_router.py").write_text(
        textwrap.dedent(
            """
            from fastapi import APIRouter
            router = APIRouter()

            @router.get('/api/cameras')
            async def list_cameras():
                return []
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "static" / "stage.html").write_text(
        "<script>fetch('/api/cameras')</script>",
        encoding="utf-8",
    )

    inv = build_inventory(tmp_path)

    assert any(route.path == "/api/cameras" for route in inv.backend_routes)
    assert any(endpoint.url == "/api/cameras" for endpoint in inv.frontend_endpoints)
    assert not inv.likely_missing


def test_route_inventory_flags_missing_frontend_endpoint(tmp_path: Path):
    (tmp_path / "modules").mkdir()
    (tmp_path / "static").mkdir()
    (tmp_path / "modules" / "health.py").write_text(
        textwrap.dedent(
            """
            from fastapi import APIRouter
            router = APIRouter()

            @router.get('/health')
            async def health():
                return {'ok': True}
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "static" / "stage.html").write_text(
        "<script>fetch('/api/switcher/program')</script>",
        encoding="utf-8",
    )

    inv = build_inventory(tmp_path)

    assert any(endpoint.url == "/api/switcher/program" for endpoint in inv.frontend_endpoints)
    assert any(endpoint.url == "/api/switcher/program" for endpoint in inv.likely_missing)


def test_route_inventory_treats_route_family_as_review_covered(tmp_path: Path):
    (tmp_path / "modules").mkdir()
    (tmp_path / "static").mkdir()
    (tmp_path / "modules" / "camera_router.py").write_text(
        textwrap.dedent(
            """
            from fastapi import APIRouter
            router = APIRouter()

            @router.post('/api/cameras/select')
            async def select_camera():
                return {'ok': True}
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "static" / "stage.html").write_text(
        "<script>fetch('/api/cameras/active')</script>",
        encoding="utf-8",
    )

    inv = build_inventory(tmp_path)

    assert any(route.path == "/api/cameras/select" for route in inv.backend_routes)
    assert any(endpoint.url == "/api/cameras/active" for endpoint in inv.frontend_endpoints)
    assert not inv.likely_missing
