"""Full-host route/admission ownership regressions restored from the promoted Reach contract."""
from __future__ import annotations

try:
    from fastapi.routing import _IncludedRouter
except ImportError:  # pragma: no cover
    _IncludedRouter = None

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.routing import Route

from modules.runtime_control_routes import create_runtime_control_router
from modules.stage_compat_routes import create_stage_compat_router
from modules.recording_pipeline_routes import create_recording_pipeline_router


def _effective(app):
    for route in app.routes:
        if _IncludedRouter is not None and isinstance(route, _IncludedRouter):
            for ctx in route.effective_route_contexts():
                underlying = getattr(ctx, "starlette_route", None) or ctx.original_route
                path = getattr(ctx, "path", "") or getattr(underlying, "path", "")
                if path:
                    yield path, underlying
        elif hasattr(route, "path"):
            yield route.path, route


def _http_keys(app):
    keys=[]
    for path, route in _effective(app):
        if not isinstance(route, Route):
            continue
        for method in (route.methods or {"GET"}):
            if method not in {"HEAD", "OPTIONS"}:
                keys.append((method, path))
    return keys


def test_full_host_has_one_owner_per_http_method_path(main_module):
    keys=_http_keys(main_module.app)
    dup=sorted({key for key in keys if keys.count(key)>1})
    assert dup == [], f"duplicate full-host HTTP authorities: {dup}"


def test_runtime_compat_can_disable_only_full_host_overlaps():
    app=FastAPI()
    app.include_router(create_runtime_control_router(include_overlapping_routes=False))
    keys=set(_http_keys(app))
    assert ("GET", "/api/choreo/status") in keys
    assert ("POST", "/api/performance/profile") in keys
    assert ("GET", "/api/performance/status") not in keys
    assert ("GET", "/api/choreo/actions") not in keys
    assert ("POST", "/api/choreo/cue") not in keys


def test_stage_compat_can_disable_only_full_host_overlaps():
    app=FastAPI()
    app.include_router(create_stage_compat_router(include_overlapping_routes=False))
    keys=set(_http_keys(app))
    assert ("GET", "/api/switcher") in keys
    assert ("POST", "/api/switcher") in keys
    assert ("GET", "/api/state/production") not in keys
    assert ("POST", "/api/state/production") not in keys
    assert ("GET", "/api/state/user") not in keys


def test_recording_pipeline_full_host_surface_drops_shadow_marker_only():
    app=FastAPI()
    app.include_router(create_recording_pipeline_router(include_marker_route=False))
    keys=set(_http_keys(app))
    assert ("GET", "/api/recording/{session_id}/events") in keys
    assert ("GET", "/api/recording/{session_id}/summary") in keys
    assert ("POST", "/api/recording/{session_id}/marker") not in keys


def test_waiting_room_ui_polls_server_approval_instead_of_auto_entering():
    from pathlib import Path
    html=(Path(__file__).resolve().parents[1]/"static"/"waiting_room.html").read_text(encoding="utf-8")
    assert "/api/governance/waiting-room/status/${encodeURIComponent(entryId)}" in html
    assert "auto-approve after 2 seconds" not in html
    assert "nextStep(4);" in html  # still advances, but only inside approved branch
