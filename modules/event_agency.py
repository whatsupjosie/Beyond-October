"""Persistent event-agency substrate for PubPartner.

V1 purpose:
    Generalize the existing nudge mechanism into a durable, typed Event without
    changing the character-generation contract.

Design laws:
    - An Event records something that happened; it is not itself permission to act.
    - Event records are append-only JSONL. State transitions are additional records.
    - Generated/model text is never authoritative character state.
    - The ledger is inspectable and provider-neutral.
    - Existing Nudge behavior remains compatible through PersistentEventAgency.

This module is deliberately dependency-free so it can become foundational without
pulling the runtime into a new framework.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


EVENT_SCHEMA_VERSION = "PubPartner.Event.v1"
VALID_STATUSES = {
    "created",
    "queued",
    "observed",
    "considered",
    "delivered",
    "deferred",
    "dismissed",
    "resolved",
    "expired",
    "failed",
}


def _now() -> float:
    return time.time()


@dataclass(frozen=True)
class Event:
    """A durable fact that something happened in the character runtime."""

    event_id: str
    event_type: str
    source: str
    target: Optional[str] = None
    timestamp: float = field(default_factory=_now)
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: float = 0.5
    confidence: float = 1.0
    parent_event_id: Optional[str] = None
    expires_at: Optional[float] = None
    status: str = "created"
    schema_version: str = EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id is required")
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.source:
            raise ValueError("source is required")
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid event status: {self.status}")
        if not 0.0 <= float(self.priority) <= 1.0:
            raise ValueError("priority must be between 0 and 1")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EventLedger:
    """Append-only, inspectable JSONL ledger for runtime events."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def append(self, event: Event) -> Event:
        record = {
            "record_kind": "event",
            "record_version": EVENT_SCHEMA_VERSION,
            **event.to_dict(),
        }
        self._append_record(record)
        return event

    def transition(
        self,
        event_id: str,
        status: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid event status: {status}")
        record = {
            "record_kind": "event_status",
            "record_version": EVENT_SCHEMA_VERSION,
            "event_id": event_id,
            "status": status,
            "timestamp": _now() if timestamp is None else float(timestamp),
            "metadata": dict(metadata or {}),
        }
        self._append_record(record)
        return record

    def _append_record(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass

    def records(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with self._lock:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(row, dict):
                        rows.append(row)
        return rows

    def events(self) -> List[Dict[str, Any]]:
        return [r for r in self.records() if r.get("record_kind") == "event"]

    def event_history(self, event_id: str) -> List[Dict[str, Any]]:
        return [
            r for r in self.records()
            if r.get("event_id") == event_id
        ]

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Reconstruct latest status for each event without mutating the ledger."""
        state: Dict[str, Dict[str, Any]] = {}
        for row in self.records():
            if row.get("record_kind") == "event":
                event_id = str(row["event_id"])
                state[event_id] = dict(row)
            elif row.get("record_kind") == "event_status":
                event_id = str(row.get("event_id", ""))
                if event_id in state:
                    state[event_id]["status"] = row.get("status")
                    state[event_id]["last_transition_at"] = row.get("timestamp")
                    state[event_id]["last_transition_metadata"] = row.get("metadata", {})
        return state


class PersistentEventAgency:
    """Small V1 facade used by runtime components.

    It intentionally does not make decisions. It creates/records events and
    lifecycle transitions so future attention, intention, and deliberation layers
    can consume the same substrate.
    """

    def __init__(self, data_dir: Path | str) -> None:
        root = Path(data_dir) / "pubpartner" / "events"
        root.mkdir(parents=True, exist_ok=True)
        self.ledger = EventLedger(root / "events.jsonl")
        # Observation is intentionally optional and side-effect free with respect
        # to character state. It can be introduced without changing nudge behavior.
        self._observer = None

    def create(
        self,
        *,
        event_type: str,
        source: str,
        target: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        priority: float = 0.5,
        confidence: float = 1.0,
        parent_event_id: Optional[str] = None,
        expires_at: Optional[float] = None,
        status: str = "created",
    ) -> Event:
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            target=target,
            payload=dict(payload or {}),
            priority=max(0.0, min(1.0, float(priority))),
            confidence=max(0.0, min(1.0, float(confidence))),
            parent_event_id=parent_event_id,
            expires_at=expires_at,
            status=status,
        )
        return self.ledger.append(event)

    def transition(
        self,
        event_id: str,
        status: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.ledger.transition(event_id, status, metadata=metadata)

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        return self.ledger.snapshot()

    def observer(self):
        """Return the lazy observation layer for this event agency."""
        if self._observer is None:
            from .agency_observation import PersistentEventObserver
            self._observer = PersistentEventObserver(self.ledger)
        return self._observer

    def observe(self, event: Event, **kwargs: Any):
        """Record that a character observed an event; does not authorize action."""
        return self.observer().observe(event, **kwargs)
