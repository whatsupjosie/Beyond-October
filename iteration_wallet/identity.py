"""Local identity/session records for Iteration Wallet.

This is not OAuth or biometric auth. It is the local shape every custody gate can
trust after a real auth provider or human ceremony has established identity.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


class IdentityError(RuntimeError):
    """Raised for expected identity/session failures."""


HUMAN_KIND = "human"
BOT_KINDS = {"ai_assistant", "bot", "tool", "script", "unknown"}
HUMAN_INTENT_METHODS = {
    "human_ceremony",
    "ceremony_token",
    "live_ceremony",
    "manual_ceremony",
    "camera_verification",
    "typing_challenge",
    "read_aloud_challenge",
    "head_user_approval",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ActorIdentity:
    actor_id: str
    actor_kind: str = "unknown"
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:24])
    device_id: Optional[str] = None
    verified_methods: List[str] = field(default_factory=list)
    role_claims: Dict[str, Any] = field(default_factory=dict)
    issued_at: datetime = field(default_factory=_now)
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.actor_id:
            raise IdentityError("actor_id is required")
        self.actor_kind = str(self.actor_kind or "unknown")
        self.verified_methods = list(dict.fromkeys(str(item) for item in self.verified_methods))
        if self.expires_at is None:
            self.expires_at = self.issued_at + timedelta(hours=8)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        return bool(self.expires_at and (now or _now()) > self.expires_at)

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_valid(self, now: Optional[datetime] = None) -> bool:
        return not self.is_revoked() and not self.is_expired(now)

    def is_human(self) -> bool:
        return self.actor_kind == HUMAN_KIND

    def is_bot_like(self) -> bool:
        return self.actor_kind in BOT_KINDS

    def has_any_verified_method(self, methods: Iterable[str]) -> bool:
        mine = set(self.verified_methods)
        return any(method in mine for method in methods)

    def has_human_intent_proof(self) -> bool:
        return self.is_human() and self.has_any_verified_method(HUMAN_INTENT_METHODS)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in ("issued_at", "expires_at", "revoked_at"):
            value = data[key]
            data[key] = value.isoformat() if value else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActorIdentity":
        def parse(value: Optional[str]) -> Optional[datetime]:
            return datetime.fromisoformat(value) if value else None
        return cls(
            actor_id=str(data["actor_id"]),
            actor_kind=str(data.get("actor_kind", "unknown")),
            session_id=str(data.get("session_id") or uuid.uuid4().hex[:24]),
            device_id=data.get("device_id"),
            verified_methods=list(data.get("verified_methods") or []),
            role_claims=dict(data.get("role_claims") or {}),
            issued_at=parse(data.get("issued_at")) or _now(),
            expires_at=parse(data.get("expires_at")),
            revoked_at=parse(data.get("revoked_at")),
        )


class LocalIdentityProvider:
    """Small local session store with atomic JSON writes."""

    def __init__(self, vault_root: str | Path):
        self.vault_root = Path(vault_root)
        self.session_dir = self.vault_root / "identity" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def issue_session(self, actor_id: str, actor_kind: str, *, device_id: Optional[str] = None, verified_methods: Optional[Sequence[str]] = None, role_claims: Optional[Dict[str, Any]] = None, ttl_minutes: int = 480) -> ActorIdentity:
        issued = _now()
        identity = ActorIdentity(
            actor_id=actor_id,
            actor_kind=actor_kind,
            device_id=device_id,
            verified_methods=list(verified_methods or []),
            role_claims=dict(role_claims or {}),
            issued_at=issued,
            expires_at=issued + timedelta(minutes=max(1, int(ttl_minutes))),
        )
        self._write_json_atomic(self.session_dir / f"{identity.session_id}.json", identity.to_dict())
        return identity

    def get_session(self, session_id: str) -> Optional[ActorIdentity]:
        path = self.session_dir / f"{session_id}.json"
        if not session_id or not path.exists():
            return None
        try:
            return ActorIdentity.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None

    def require_session(self, session_id: str) -> ActorIdentity:
        identity = self.get_session(session_id)
        if identity is None:
            raise IdentityError("Unknown identity session")
        if not identity.is_valid():
            raise IdentityError("Identity session is expired or revoked")
        return identity

    def revoke_session(self, session_id: str, reason: str = "") -> Optional[ActorIdentity]:
        identity = self.get_session(session_id)
        if identity is None:
            return None
        identity.revoked_at = _now()
        if reason:
            identity.role_claims = {**identity.role_claims, "revoke_reason": reason}
        self._write_json_atomic(self.session_dir / f"{identity.session_id}.json", identity.to_dict())
        return identity

    def list_sessions(self, actor_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sessions: List[ActorIdentity] = []
        for path in self.session_dir.glob("*.json"):
            try:
                session = ActorIdentity.from_dict(json.loads(path.read_text(encoding="utf-8")))
                if actor_id is None or session.actor_id == actor_id:
                    sessions.append(session)
            except Exception:
                continue
        sessions.sort(key=lambda item: item.issued_at)
        return [item.to_dict() for item in sessions]


__all__ = ["ActorIdentity", "BOT_KINDS", "HUMAN_INTENT_METHODS", "HUMAN_KIND", "IdentityError", "LocalIdentityProvider"]
