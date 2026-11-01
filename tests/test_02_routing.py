"""
test_02_routing.py — Route registration, ordering, and conflict detection
══════════════════════════════════════════════════════════════════════════
The most critical test in this file is the WebSocket route ordering check.

KNOWN BUG (fixed in main.py): /ws/{room} is a catch-all. If /unity/ws/{client_id}
and /studio/ws are registered AFTER it, Starlette matches them to the catch-all
first and the dedicated Unity/Studio handlers are never reached.

These tests enforce that the correct ordering is maintained permanently —
if someone reorders routes in main.py, a test will catch it before it ships.

Route-existence checks run against the fully-booted app (the `main_module`
fixture, which depends on `client` and therefore guarantees the lifespan has
run). Several routers — cameras, audio, mic, pubworld hotspots, lighting,
bridge — are mounted inside main.py's lifespan via `include_router()`, so
they simply don't exist yet on the bare pre-boot app object.

VERSION NOTE: the installed FastAPI (0.141.x) no longer flattens a included
APIRouter's routes into `app.routes` — `include_router()` appends a single
opaque `_IncludedRouter` wrapper instead, and dispatches through it lazily
at request time (`fastapi.routing._IncludedRouter.effective_route_contexts`).
Only routes decorated directly on `app` (e.g. `@app.get(...)`,
`@app.websocket(...)`) still appear as flat Route/WebSocketRoute objects.
Naively reading `route.path` off `app.routes` therefore misses every route
that arrived via `include_router()` — which is most of this app's surface —
even though those routes work perfectly at runtime. `_iter_effective_routes`
below recurses through `_IncludedRouter` wrappers to recover the real,
flattened route list; it falls back to the old flat behaviour on older
FastAPI versions that don't have `_IncludedRouter`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from starlette.routing import Route, WebSocketRoute, Mount

try:
    from fastapi.routing import _IncludedRouter
except ImportError:  # pragma: no cover - older FastAPI without the wrapper
    _IncludedRouter = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _iter_effective_routes(app):
    """Yield (path, underlying_route) for every route reachable from `app`,
    recursing through `_IncludedRouter` wrappers so routes mounted via
    `include_router()` are not silently skipped. See module docstring."""
    for route in app.routes:
        if _IncludedRouter is not None and isinstance(route, _IncludedRouter):
            for ctx in route.effective_route_contexts():
                starlette_route = getattr(ctx, "starlette_route", None)
                path = getattr(ctx, "path", "") or getattr(starlette_route, "path", None)
                underlying = starlette_route or ctx.original_route
                if path:
                    yield path, underlying
        elif hasattr(route, "path"):
            yield route.path, route


def _get_routes(app):
    """Flatten the app route list into (path, methods/type) tuples."""
    return list(_iter_effective_routes(app))


def _websocket_routes(app):
    """Return (path, route) pairs for WebSocket routes, in registration order."""
    return [(p, r) for p, r in _iter_effective_routes(app) if isinstance(r, WebSocketRoute)]


def _ws_path_order(app):
    """Return WebSocket route paths in registration order."""
    return [p for p, _ in _websocket_routes(app)]


# ─────────────────────────────────────────────────────────────────────────────
# 1. WebSocket route ordering — THE critical test
# ─────────────────────────────────────────────────────────────────────────────

def test_ws_unity_registered_before_catchall(main_module):
    """/unity/ws/{client_id} must appear in the route list BEFORE /ws/{room}.

    If /ws/{room} comes first, Starlette matches /unity/ws/{client_id} to the
    catch-all and the UnityBridge handler is never reached.
    """
    order = _ws_path_order(main_module.app)
    assert "/unity/ws/{client_id}" in order, "/unity/ws/{client_id} is not registered at all"
    assert "/ws/{room}" in order, "/ws/{room} is not registered at all"

    unity_idx  = order.index("/unity/ws/{client_id}")
    catchall_idx = order.index("/ws/{room}")
    assert unity_idx < catchall_idx, (
        f"/unity/ws/{{client_id}} is at position {unity_idx} but /ws/{{room}} is at {catchall_idx}. "
        f"The catch-all will shadow it — Unity Bridge WebSocket will be broken."
    )


def test_ws_studio_registered_before_catchall(main_module):
    """/studio/ws must appear in the route list BEFORE /ws/{room}.

    Same shadowing issue as Unity — Studio Control Room WebSocket
    will silently connect to the hub instead of the studio handler.
    """
    order = _ws_path_order(main_module.app)
    assert "/studio/ws" in order, "/studio/ws is not registered at all"

    studio_idx   = order.index("/studio/ws")
    catchall_idx = order.index("/ws/{room}")
    assert studio_idx < catchall_idx, (
        f"/studio/ws is at position {studio_idx} but /ws/{{room}} is at {catchall_idx}. "
        f"The catch-all will shadow /studio/ws — Studio Control Room will be broken."
    )


def test_specific_ws_routes_all_before_catchall(main_module):
    """Comprehensive: every WS route actually shape-shadowed by /ws/{room}
    (i.e. every literal two-segment "/ws/<name>" path) must precede it.
    Unrelated literal paths like "/api/logs/ws" can never collide with
    "/ws/{room}" regardless of registration order — Starlette only matches
    paths with the same segment count and matching literal prefix — so they
    are excluded here rather than flagged as false positives."""
    order = _ws_path_order(main_module.app)
    if "/ws/{room}" not in order:
        pytest.skip("/ws/{room} not registered — nothing to check")

    catchall_idx = order.index("/ws/{room}")
    at_risk = [
        p for p in order
        if "{" not in p and p != "/ws/{room}"
        and p.startswith("/ws/") and p.count("/") == 2
    ]

    for path in at_risk:
        idx = order.index(path)
        assert idx < catchall_idx, (
            f"Specific WS route {path!r} (pos {idx}) comes AFTER catch-all "
            f"/ws/{{room}} (pos {catchall_idx}) — it will never be reached."
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. All expected routes are registered
# ─────────────────────────────────────────────────────────────────────────────

EXPECTED_HTTP_ROUTES = [
    "/api/health",
    "/api/health/breakers",
    "/api/me",
    "/api/state/user",
    "/api/state/production",
    "/api/cameras",
    "/api/cameras/program",
    "/api/cameras/preview",
    "/api/cameras/cut",
    "/api/recording/profiles",
    "/api/recording/sessions",
    "/api/avatars/presets",
    "/api/avatars/me",
    "/api/bots",
    "/api/pubworld/scenes",
    "/api/pubworld/props",
    "/api/pubworld/prototypes",
    "/api/pubworld/props/generate",
    "/api/pubworld/generate/status",
    "/api/lighting/presets",
    "/api/lighting/active",
    "/api/bridge/status",
    "/api/bridge/connect",
    "/api/choreo/status",
    "/api/performer/status",
    "/api/engine/status",
    "/api/jeremy/health",
    "/api/internal/room-conductor/status",
    "/api/studio/status",
    "/api/unity/status",
    "/api/voxel/assets",
    # Audio device routes (registered directly on app, not via router)
    "/api/audio/devices",
    "/api/audio/devices/refresh",
    "/api/audio/devices/active",
    # Page routes
    "/", "/control", "/stage", "/dressing", "/bar", "/world",
    "/builder", "/gallery", "/analytics", "/launch", "/byok", "/studio",
    "/walk", "/world-walk",
]

EXPECTED_WS_ROUTES = ["/unity/ws/{client_id}", "/studio/ws", "/ws/control", "/ws/{room}"]

# Router-mounted routes (prefixed)
EXPECTED_ROUTER_ROUTES = [
    "/api/mic/cough",
    "/api/mic/cough/status",
    "/api/mic/profiles",
    "/pubworld/ws/{client_id}",
    "/pubworld/state",
]
# NOTE: there is no "/pubworld/api/room-change" REST route — room changes are
# a `room_change` *message type* sent over the /pubworld/ws WebSocket
# (see main.py's pubworld websocket handler), not an HTTP endpoint. A stale
# expectation for a nonexistent REST route was removed.


def _all_route_paths(app):
    """Collect all registered route paths from the app and included routers."""
    return {p for p, _ in _iter_effective_routes(app)}


@pytest.mark.parametrize("path", EXPECTED_HTTP_ROUTES)
def test_http_route_registered(main_module, path):
    paths = _all_route_paths(main_module.app)
    assert path in paths, f"Expected route {path!r} is not registered"


@pytest.mark.parametrize("path", EXPECTED_WS_ROUTES)
def test_ws_route_registered(main_module, path):
    ws_paths = {p for p, _ in _websocket_routes(main_module.app)}
    assert path in ws_paths, f"Expected WebSocket route {path!r} is not registered"


@pytest.mark.parametrize("path", EXPECTED_ROUTER_ROUTES)
def test_router_route_registered(main_module, path):
    paths = _all_route_paths(main_module.app)
    assert path in paths, (
        f"Expected router-mounted route {path!r} is not registered. "
        "Check that the router is included in main.py."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Static file mounts
# ─────────────────────────────────────────────────────────────────────────────

def test_static_mount_registered(raw_app):
    mount_paths = {r.path for r in raw_app.routes if isinstance(r, Mount)}
    assert "/static" in mount_paths, "/static is not mounted — all JS/CSS will 404"


def test_assets_mount_registered(raw_app):
    mount_paths = {r.path for r in raw_app.routes if isinstance(r, Mount)}
    assert "/assets" in mount_paths, "/assets is not mounted — GLB models and VOD will 404"


# ─────────────────────────────────────────────────────────────────────────────
# 4. No duplicate route definitions
# ─────────────────────────────────────────────────────────────────────────────

def test_no_duplicate_websocket_routes(main_module):
    """Each WebSocket path should appear exactly once — except the two
    routes intentionally defined twice: /ws/control and /api/logs/ws, each
    registered directly on `app` (so they actually get dispatched to ahead
    of anything that arrives later via include_router — see the
    control_websocket / logs_websocket_direct handlers above) AND once more
    inside their original router module (modules/stage_compat_routes.py,
    modules/structured_log_routes.py) for those modules' own standalone
    tests. The router-module copies are unreachable dead code in the full
    app, not live bugs."""
    KNOWN_HARMLESS_DUPLICATE_WS_ROUTES = {"/ws/control", "/api/logs/ws"}
    ws_paths = [p for p, _ in _websocket_routes(main_module.app)]
    seen = {}
    duplicates = []
    for p in ws_paths:
        seen[p] = seen.get(p, 0) + 1
        if seen[p] == 2 and p not in KNOWN_HARMLESS_DUPLICATE_WS_ROUTES:
            duplicates.append(p)
    assert not duplicates, (
        f"Duplicate WebSocket route(s) detected: {duplicates}. "
        "The later definition is dead code."
    )


# Full Reach requires exactly one HTTP authority per (method, path).
# Reusable compatibility routers preserve their standalone defaults, while the
# full host mounts them with overlapping routes disabled. Do not add allow-list
# exceptions here: a duplicate can make Starlette dispatch one handler while
# OpenAPI documents another.


def test_no_duplicate_http_routes(main_module):
    """Full Reach must expose one HTTP owner for every path+method pair."""
    from starlette.routing import Route as StarletteRoute
    seen: dict[tuple, int] = {}
    duplicates = []
    for path, route in _iter_effective_routes(main_module.app):
        if not isinstance(route, StarletteRoute):
            continue
        for method in (route.methods or {"GET"}):
            key = (path, method)
            seen[key] = seen.get(key, 0) + 1
            if seen[key] == 2:
                duplicates.append(key)
    assert not duplicates, f"Duplicate HTTP route(s): {duplicates}"
