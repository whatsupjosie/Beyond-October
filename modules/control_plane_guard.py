"""Require the ``mod`` role for shared production-control routes when auth is enforced.

The audit (Round 2) found 24 mutating routes that steer the live broadcast, switcher,
stage, audio devices, microphones and the camera boxer with no authorisation signal at
all. Those routers are registered late in the lifespan from many modules, so the
policy lives in one auditable place instead of 24 edits: a pure-ASGI guard with an
explicit table.

Behaviour is unchanged unless ``PUBCAST_ENFORCE_AUTH`` is on (the same switch every
other guarded route follows), and then it applies the same ``mod`` policy that
``/api/production/state`` and the camera switch already use.
"""
from __future__ import annotations

import re
from typing import Awaitable, Callable

from fastapi import HTTPException
from fastapi.security import HTTPBearer
from starlette.requests import Request
from starlette.responses import JSONResponse

from .route_security import auth_enforced, require_role

_bearer = HTTPBearer(auto_error=False)
_mod = require_role("mod")

_SEG = r"[^/]+"
# (method, path pattern). Reads stay as they were; only state-changing calls are listed.
CONTROL_ROUTES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (method, re.compile("^" + pattern + "$"))
    for method, pattern in (
        ("POST", r"/api/choreo/(start|stop)"),
        ("POST", r"/api/vision/cameras/register"),
        ("POST", r"/api/vision/broadcast/(start|stop|camera/switch|camera/auto)"),
        ("POST", r"/api/vision/scene/update"),
        ("POST", rf"/api/switcher/(preview|cut|ptz)/{_SEG}"),
        ("POST", r"/api/switcher/(cut|transition)"),
        ("POST", rf"/api/stage/(load|actor)/{_SEG}"),
        ("DELETE", rf"/api/stage/actor/{_SEG}"),
        ("POST", r"/api/stage/screen/focus"),
        ("POST", r"/api/audio/devices/(refresh|select|test)"),
        ("POST", r"/api/mic/profiles"),
        ("DELETE", rf"/api/mic/profiles/{_SEG}"),
        ("POST", r"/api/boxer/override"),
        ("POST", r"/api/performance/profile"),
    )
)


def is_control_route(method: str, path: str) -> bool:
    return any(m == method and rx.match(path) for m, rx in CONTROL_ROUTES)


class ControlPlaneGuardMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if (scope["type"] == "http" and auth_enforced()
                and is_control_route(scope["method"], scope["path"])):
            request = Request(scope, receive)
            try:
                await _mod(request, await _bearer(request))
            except HTTPException as exc:
                await JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                                   headers=getattr(exc, "headers", None))(scope, receive, send)
                return
        await self.app(scope, receive, send)
