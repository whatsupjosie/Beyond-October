"""Human ceremony token primitives for Iteration Wallet.

This module is intentionally small and deterministic. It does not make custody
decisions by itself; it issues and verifies scoped proof that a human ceremony
occurred.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional


@dataclass
class CeremonyTokenRecord:
    """Stored token metadata without the raw token secret."""

    token_hash: str
    actor_id: str
    scope: str
    issued_at: str
    expires_at: str
    consumed_at: Optional[str] = None

    def safe_dict(self) -> Dict[str, Optional[str]]:
        return asdict(self)


class CeremonyLedger:
    """In-memory ceremony ledger suitable for local deterministic flows.

    Production adapters may persist these records, but closed views must still
    expose only token hashes and metadata, never raw token values.
    """

    def __init__(self, *, ttl_seconds: int = 300):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = ttl_seconds
        self._records: Dict[str, CeremonyTokenRecord] = {}

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue(self, *, actor_id: str, scope: str) -> str:
        if not actor_id:
            raise ValueError("actor_id is required")
        if not scope:
            raise ValueError("scope is required")
        token = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        expires = now + timedelta(seconds=self.ttl_seconds)
        record = CeremonyTokenRecord(
            token_hash=self.hash_token(token),
            actor_id=actor_id,
            scope=scope,
            issued_at=now.isoformat() + "Z",
            expires_at=expires.isoformat() + "Z",
        )
        self._records[record.token_hash] = record
        return token

    def verify(self, token: str, *, scope: str) -> bool:
        record = self._records.get(self.hash_token(token))
        if record is None or record.scope != scope or record.consumed_at is not None:
            return False
        return datetime.utcnow() <= datetime.fromisoformat(record.expires_at.removesuffix("Z"))

    def consume(self, token: str, *, scope: str) -> bool:
        if not self.verify(token, scope=scope):
            return False
        record = self._records[self.hash_token(token)]
        record.consumed_at = datetime.utcnow().isoformat() + "Z"
        return True

    def closed_status(self) -> Dict[str, object]:
        return {
            "token_count": len(self._records),
            "records": [record.safe_dict() for record in self._records.values()],
            "raw_tokens_exposed": False,
        }


__all__ = ["CeremonyLedger", "CeremonyTokenRecord"]

