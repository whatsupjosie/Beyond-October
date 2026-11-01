"""Typed event contracts for the EVO semantic runtime.

The envelope carries provenance, correlation, priority, and a bounded hop count so
runtime events can be traced without allowing unbounded recursive rebroadcasts.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from time import time
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from .mutation import Role


def _freeze_payload(value: Any) -> Any:
    """Own data containers so producers and subscribers cannot edit an event.

    Events carry structured data, not live mutable runtime objects. Arrays are
    exposed as tuples; mapping access remains compatible with existing handlers.
    """
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_payload(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_payload(item) for item in value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError("event payload values must be structured data")


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Immutable event metadata and an owned, recursively read-only payload."""

    source: str
    role: Role
    event_type: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    priority: int = 0
    correlation_id: str = field(default_factory=lambda: uuid4().hex)
    event_id: str = field(default_factory=lambda: uuid4().hex)
    parent_id: str | None = None
    hop: int = 0
    max_hops: int = 8
    created_at: float = field(default_factory=time)

    def __post_init__(self) -> None:
        if not isinstance(self.payload, Mapping):
            raise TypeError("event payload must be a mapping")
        object.__setattr__(self, "payload", _freeze_payload(self.payload))
        if not self.source.strip():
            raise ValueError("event source must be non-empty")
        if not self.event_type.strip():
            raise ValueError("event_type must be non-empty")
        if self.hop < 0:
            raise ValueError("event hop cannot be negative")
        if self.max_hops < 1:
            raise ValueError("event max_hops must be at least 1")
        if self.hop > self.max_hops:
            raise ValueError("event hop exceeds max_hops")

    @property
    def can_forward(self) -> bool:
        return self.hop < self.max_hops

    def child(
        self,
        *,
        source: str,
        role: Role,
        event_type: str,
        payload: Mapping[str, Any] | None = None,
        priority: int | None = None,
    ) -> "EventEnvelope":
        """Create a causally linked event while preserving the trace correlation."""
        if not self.can_forward:
            raise RuntimeError("event hop budget exhausted")
        return EventEnvelope(
            source=source,
            role=role,
            event_type=event_type,
            payload={} if payload is None else payload,
            priority=self.priority if priority is None else priority,
            correlation_id=self.correlation_id,
            parent_id=self.event_id,
            hop=self.hop + 1,
            max_hops=self.max_hops,
        )

    def with_payload(self, payload: Mapping[str, Any]) -> "EventEnvelope":
        """Return a copy with replacement payload and identical event identity."""
        return replace(self, payload=payload)
