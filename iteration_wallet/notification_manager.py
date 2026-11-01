"""Human-intent notification and access decision primitives.

AI and tools can request access. They cannot approve their own custody actions.
This module returns explicit decisions and records enough evidence for BlackBox.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ActorKind(str, Enum):
    HUMAN = "human"
    AI_ASSISTANT = "ai_assistant"
    BOT = "bot"
    TOOL = "tool"
    SCRIPT = "script"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class NotificationLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


class RequestStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    DENIED = "denied"
    BLOCKED = "blocked"


class RequestClassification(str, Enum):
    NORMAL = "normal"
    PROTECTED_CUSTODY = "protected_custody"
    BOT_PRESSURE = "bot_pressure"
    HOSTILE_OR_UNKNOWN = "hostile_or_unknown"


@dataclass
class Notification:
    notification_id: str
    level: str
    message: str
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AccessRequest:
    request_id: str
    actor_kind: str
    action: str
    protected: bool
    status: str
    reason: str
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


ApprovalRequest = AccessRequest


class NotificationManager:
    """In-memory decision log for protected action requests."""

    def __init__(self, vault_root: str | Path, *, blackbox: Optional[Any] = None):
        self.vault_root = Path(vault_root)
        self.blackbox = blackbox
        self.requests: List[AccessRequest] = []
        self.notifications: List[Notification] = []

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def coerce_actor_kind(actor_kind: ActorKind | str | None) -> ActorKind:
        if isinstance(actor_kind, ActorKind):
            return actor_kind
        try:
            return ActorKind(str(actor_kind or ActorKind.UNKNOWN.value))
        except ValueError:
            return ActorKind.UNKNOWN

    def notify(self, level: NotificationLevel | str, message: str, **metadata: Any) -> Notification:
        item = Notification(
            notification_id=uuid.uuid4().hex[:16],
            level=str(level.value if isinstance(level, NotificationLevel) else level),
            message=message,
            created_at=self._now(),
            metadata=metadata,
        )
        self.notifications.append(item)
        return item

    def evaluate_direct_access(self, actor_kind: ActorKind | str | None, action: str, *, protected: bool = True, human_ceremony_passed: bool = False, actor_identity: Optional[Any] = None) -> Dict[str, Any]:
        kind = self.coerce_actor_kind(actor_kind)
        has_human_identity = bool(actor_identity and getattr(actor_identity, "has_human_intent_proof", lambda: False)())
        has_human_proof = bool(human_ceremony_passed or has_human_identity)
        if protected and kind != ActorKind.HUMAN:
            allowed = False
            reason = "AI/tools stay outside the yard; human approval is required."
        elif protected and not has_human_proof:
            allowed = False
            reason = "Protected custody requires verified human intent."
        else:
            allowed = True
            reason = "Human-intent gate passed."
        request = AccessRequest(
            request_id=uuid.uuid4().hex[:16],
            actor_kind=kind.value,
            action=action,
            protected=protected,
            status=RequestStatus.APPROVED.value if allowed else RequestStatus.BLOCKED.value,
            reason=reason,
            created_at=self._now(),
            metadata={"actor_id": getattr(actor_identity, "actor_id", None)},
        )
        self.requests.append(request)
        if self.blackbox and hasattr(self.blackbox, "write_event"):
            self.blackbox.write_event("HUMAN_INTENT_GATE_DECISION", reason, decision=request.to_dict())
        return {"allowed": allowed, "reason": reason, "request": request.to_dict()}

    def status(self) -> Dict[str, Any]:
        return {
            "requests": [item.to_dict() for item in self.requests],
            "notifications": [item.to_dict() for item in self.notifications],
        }


__all__ = ["AccessRequest", "ActorKind", "ApprovalRequest", "Notification", "NotificationLevel", "NotificationManager", "RequestClassification", "RequestStatus"]
