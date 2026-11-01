# PubCast AI — auth_routes.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""First-run setup, login, and token verification routes."""
from __future__ import annotations

import re
import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from modules import userdb
from modules.auth import WS_SESSION_COOKIE
from modules.auth_rate_limit import SlidingWindowLimiter
from modules.route_security import auth_enforced

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

_SETUP_LIMITER = SlidingWindowLimiter(limit=5, window_seconds=600, max_keys=256)
_LOGIN_LIMITER = SlidingWindowLimiter(limit=10, window_seconds=300, max_keys=2048)
_GLOBAL_LOGIN_LIMITER = SlidingWindowLimiter(limit=60, window_seconds=60, max_keys=256)
_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$")
_COMMON_PASSWORDS = {
    "password", "password123", "123456789012", "qwertyuiop12", "letmein123456",
    "adminadminadmin", "pubpartner", "pubpartner123", "changeme12345",
}

_auth_module = None
_dummy_hash_cache: Optional[str] = None


def set_auth_instance(auth_module: Any) -> None:
    global _auth_module, _dummy_hash_cache
    _auth_module = auth_module
    _dummy_hash_cache = None


def _set_ws_session_cookie(response: Response, request: Request, token: str) -> None:
    """Give same-origin browser WebSockets an HttpOnly authentication path.

    HTTP APIs remain bearer-token authenticated; this cookie is consumed only by
    WebSocket identity resolution. SameSite=Strict keeps it scoped to first-party
    navigation, and Secure is enabled automatically when Reach itself is HTTPS.
    """
    response.set_cookie(
        WS_SESSION_COOKIE,
        token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )


def _dummy_hash() -> str:
    """A fixed-cost password hash used to equalize login timing for unknown
    usernames, so an attacker cannot use response time to enumerate valid
    accounts (real PBKDF2 verification vs. an immediate short-circuit)."""
    global _dummy_hash_cache
    if _dummy_hash_cache is None:
        _dummy_hash_cache = _auth_module.get_password_hash(secrets.token_urlsafe(32))
    return _dummy_hash_cache


def _client_ip(request: Request) -> str:
    # The app is local-first and does not trust forwarded headers unless an
    # explicit trusted proxy layer is added later.
    return request.client.host if request.client else "unknown"


def _normalize_username(value: str) -> str:
    return value.strip()


def _validate_password(password: str, username: str) -> None:
    if len(password) < 12:
        raise HTTPException(400, "Password must be at least 12 characters")
    if len(password) > 256:
        raise HTTPException(400, "Password is too long")
    lowered = password.casefold()
    if lowered in _COMMON_PASSWORDS or lowered == username.casefold() or username.casefold() in lowered:
        raise HTTPException(400, "Choose a less predictable password")
    categories = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if categories < 3:
        raise HTTPException(400, "Use at least three of: lowercase, uppercase, number, symbol")


def _rate_limit_or_raise(limiter: SlidingWindowLimiter, key: str) -> None:
    result = limiter.allow(key)
    if not result.allowed:
        raise HTTPException(
            429,
            "Too many attempts. Try again later.",
            headers={"Retry-After": str(result.retry_after)},
        )


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = _normalize_username(value)
        if not _USERNAME_RE.fullmatch(value):
            raise ValueError("Username may use letters, numbers, dot, dash, and underscore")
        return value


class SetupRequest(LoginRequest):
    confirm_password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


@router.get("/status")
async def setup_status() -> Dict[str, Any]:
    count = await userdb.count_users()
    return {
        "ok": True,
        "auth_enforced": auth_enforced(),
        "setup_required": count == 0,
        "user_count": count,
        "mode": "owner-local" if auth_enforced() else "relaxed-development",
    }


@router.post("/setup", response_model=TokenResponse, status_code=201)
async def first_run_setup(payload: SetupRequest, request: Request, response: Response) -> TokenResponse:
    if _auth_module is None:
        raise HTTPException(503, "Auth system not initialized")
    _rate_limit_or_raise(_SETUP_LIMITER, f"setup:{_client_ip(request)}")
    if payload.password != payload.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    _validate_password(payload.password, payload.username)
    created = await userdb.create_owner_via_setup(payload.username, payload.password)
    if not created:
        # Do not expose account details; setup is a one-time transition.
        raise HTTPException(409, "Initial setup has already been completed")
    token = _auth_module.create_access_token({"sub": payload.username, "role": "owner"})
    _set_ws_session_cookie(response, request, token)
    return TokenResponse(access_token=token, username=payload.username, role="owner")


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, response: Response) -> TokenResponse:
    if _auth_module is None:
        raise HTTPException(503, "Auth system not initialized")
    ip = _client_ip(request)
    _rate_limit_or_raise(_GLOBAL_LOGIN_LIMITER, f"global:{ip}")
    key = f"login:{ip}:{payload.username.casefold()}"
    _rate_limit_or_raise(_LOGIN_LIMITER, key)

    user = await userdb.get_user(payload.username)
    hashed = user.get("hashed_password", "") if user else _dummy_hash()
    # Always run the real verification, even for unknown usernames, so
    # response timing does not leak whether an account exists.
    password_ok = _auth_module.verify_password(payload.password, hashed)
    valid = bool(user) and password_ok
    if not valid:
        raise HTTPException(401, "Authentication failed")

    # Transparently migrate legacy/weak hashes after a successful login.
    if _auth_module.password_hash_needs_upgrade(hashed):
        await userdb.update_password_hash(payload.username, _auth_module.get_password_hash(payload.password))

    _LOGIN_LIMITER.clear(key)
    role = str(user.get("role") or "guest")
    token = _auth_module.create_access_token({"sub": payload.username, "role": role})
    _set_ws_session_cookie(response, request, token)
    return TokenResponse(access_token=token, username=payload.username, role=role)


@router.get("/verify")
async def verify_token(request: Request, response: Response, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    if _auth_module is None:
        raise HTTPException(503, "Auth system not initialized")
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    payload = _auth_module.decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    _set_ws_session_cookie(response, request, credentials.credentials)
    return {
        "valid": True,
        "payload": payload,
        "username": payload.get("sub"),
        "role": payload.get("role", "guest"),
        "expires_at": payload.get("exp"),
    }


@router.post("/logout")
async def logout(response: Response) -> Dict[str, Any]:
    # Access tokens are stateless; clear the browser-only socket session cookie.
    response.delete_cookie(WS_SESSION_COOKIE, path="/")
    return {"ok": True, "message": "Local token and socket session may be discarded"}
