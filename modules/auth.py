# PubCast AI — auth.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""Authentication primitives for PubPartner/PubCast.

Design goals
------------
* No hard-coded secrets.
* No dependency on a JWT package for the only algorithm we use (HS256).
* Versioned password hashes using stdlib PBKDF2-HMAC-SHA256.
* Optional verification of legacy bcrypt hashes for existing installations.
* Strict token header/claim validation and constant-time signature comparison.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:  # Optional legacy compatibility only; new passwords do not depend on it.
    import bcrypt as _bcrypt
except Exception:  # pragma: no cover - lean environments
    _bcrypt = None


class JWTError(Exception):
    """Raised internally when a token fails validation."""


ROLE_ORDER: Dict[str, int] = {
    "guest": 0,
    "viewer": 1,
    "mod": 2,
    "admin": 3,
    "owner": 4,
}

_configured_secret = os.environ.get("PUBCAST_JWT_SECRET", "").strip()
_SECRET_KEY: str = _configured_secret or secrets.token_urlsafe(64)
_ALGORITHM = "HS256"
_ISSUER = os.environ.get("PUBCAST_JWT_ISSUER", "pubpartner-local").strip() or "pubpartner-local"
_AUDIENCE = os.environ.get("PUBCAST_JWT_AUDIENCE", "pubpartner-ui").strip() or "pubpartner-ui"
_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("PUBCAST_JWT_EXPIRE_MINUTES", "1440"))
WS_SESSION_COOKIE = "pubcast_ws_session"
_PBKDF2_ITERATIONS = max(600_000, int(os.environ.get("PUBCAST_PBKDF2_ITERATIONS", "600000")))

if not _configured_secret:
    logger.warning(
        "PUBCAST_JWT_SECRET is not set — using a secure process-local secret. "
        "Tokens will not survive restart. Launch through run_pubpartner.py for a persistent secret."
    )


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    if not isinstance(data, str) or not data:
        raise JWTError("Invalid base64url input")
    pad = "=" * ((4 - len(data) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode((data + pad).encode("ascii"))
    except Exception as exc:
        raise JWTError("Invalid base64url input") from exc
    # Base64url can decode multiple textual spellings to the same bytes when
    # unused trailing bits differ. JWT segments must use the canonical unpadded
    # spelling; otherwise a visibly tampered signature could compare equal.
    if _b64url_encode(decoded) != data:
        raise JWTError("Non-canonical base64url input")
    return decoded


def _json_object(raw: bytes, *, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise JWTError(f"Invalid {label}") from exc
    if not isinstance(value, dict):
        raise JWTError(f"Invalid {label}")
    return value


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def get_password_hash(plain: str) -> str:
    """Create a versioned PBKDF2-HMAC-SHA256 password hash.

    Passwords are length-bounded by the API layer. This function still rejects
    empty input so direct callers cannot accidentally create unusable accounts.
    """
    if not isinstance(plain, str) or not plain:
        raise ValueError("Password must not be empty")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        plain.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
        dklen=32,
    )
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ITERATIONS,
        _b64url_encode(salt),
        _b64url_encode(digest),
    )


def _verify_pbkdf2(plain: str, hashed: str) -> bool:
    try:
        scheme, iteration_s, salt_s, expected_s = hashed.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iteration_s)
        if iterations < 100_000 or iterations > 10_000_000:
            return False
        salt = _b64url_decode(salt_s)
        expected = _b64url_decode(expected_s)
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            plain.encode("utf-8"),
            salt,
            iterations,
            dklen=len(expected),
        )
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against current or legacy supported hash formats."""
    if not isinstance(plain, str) or not isinstance(hashed, str) or not hashed:
        return False
    if hashed.startswith("pbkdf2_sha256$"):
        return _verify_pbkdf2(plain, hashed)
    if hashed.startswith(("$2a$", "$2b$", "$2y$")) and _bcrypt is not None:
        try:
            return bool(_bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii")))
        except Exception:
            return False
    logger.warning("Unsupported password hash format")
    return False


def password_hash_needs_upgrade(hashed: str) -> bool:
    """Return True for legacy hashes or PBKDF2 work factors below policy."""
    if not isinstance(hashed, str):
        return True
    if hashed.startswith("pbkdf2_sha256$"):
        try:
            return int(hashed.split("$", 2)[1]) < _PBKDF2_ITERATIONS
        except Exception:
            return True
    return True


# ---------------------------------------------------------------------------
# HS256 JWT implementation
# ---------------------------------------------------------------------------

def _jwt_encode(payload: Dict[str, Any], secret: str) -> str:
    header = {"alg": _ALGORITHM, "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(sig)}"


def _jwt_decode(token: str, secret: str) -> Dict[str, Any]:
    if len(token) > 16_384:
        raise JWTError("Token too large")
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise JWTError("Malformed token") from exc

    header = _json_object(_b64url_decode(header_b64), label="header")
    if header.get("alg") != _ALGORITHM or header.get("typ") not in (None, "JWT"):
        raise JWTError("Unsupported token header")

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual = _b64url_decode(sig_b64)
    if not hmac.compare_digest(expected, actual):
        raise JWTError("Invalid signature")

    payload = _json_object(_b64url_decode(payload_b64), label="payload")
    now = int(time.time())

    try:
        exp = int(payload["exp"])
    except Exception as exc:
        raise JWTError("Missing or invalid exp claim") from exc
    if now >= exp:
        raise JWTError("Token expired")

    if "nbf" in payload and now < int(payload["nbf"]):
        raise JWTError("Token not yet valid")
    if payload.get("iss") != _ISSUER:
        raise JWTError("Invalid issuer")
    if payload.get("aud") != _AUDIENCE:
        raise JWTError("Invalid audience")
    if not str(payload.get("sub") or "").strip():
        raise JWTError("Missing subject")
    return payload


def create_access_token(data: Dict[str, Any], *, expires_minutes: Optional[int] = None) -> str:
    """Encode a signed local access token with strict issuer/audience claims."""
    now = datetime.now(timezone.utc)
    minutes = expires_minutes if expires_minutes is not None else _ACCESS_TOKEN_EXPIRE_MINUTES
    expire = now + timedelta(minutes=max(1, int(minutes)))
    payload = dict(data)
    payload.update({
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_urlsafe(18),
    })
    return _jwt_encode(payload, _SECRET_KEY)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a token; return None for every invalid form."""
    if not token or not isinstance(token, str):
        return None
    try:
        return _jwt_decode(token, _SECRET_KEY)
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        return None
    except Exception as exc:  # defensive boundary
        logger.debug("JWT decode failed unexpectedly: %s", exc)
        return None


def role_gte(user_role: str, min_role: str) -> bool:
    return ROLE_ORDER.get(user_role, -1) >= ROLE_ORDER.get(min_role, 999)
