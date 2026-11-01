"""Observation layer for PubPartner's persistent event-agency substrate.

This is the first step beyond event recording:
    event happened -> character was exposed to it -> salience was estimated.

It deliberately does NOT decide what the character should do.  It produces an
inspectable observation record that future attention, intention, and
permission layers can consume.
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Optional

from .event_agency import Event, EventLedger


OBSERVATION_SCHEMA_VERSION = "PubPartner.Observation.v1"


@dataclass(frozen=True)
class AttentionPolicy:
    """Deterministic, inspectable salience policy.

    Scores are deliberately simple at first.  The point is not to simulate
    cognition; it is to make attention measurable before introducing model
    judgement or autonomous action.
    """

    priority_weight: float = 0.45
    confidence_weight: float = 0.20
    recency_weight: float = 0.15
    relationship_weight: float = 0.10
    context_weight: float = 0.10
    half_life_seconds: float = 3600.0

    def score(
        self,
        event: Event,
        *,
        now: Optional[float] = None,
        relationship_salience: float = 0.0,
        context_salience: float = 0.0,
    ) -> float:
        now = time.time() if now is None else float(now)
        age = max(0.0, now - float(event.timestamp))
        decay = math.exp(-math.log(2.0) * age / max(1.0, self.half_life_seconds))
        recency = max(0.0, min(1.0, decay))
        relationship = max(0.0, min(1.0, float(relationship_salience)))
        context = max(0.0, min(1.0, float(context_salience)))
        score = (
            self.priority_weight * float(event.priority)
            + self.confidence_weight * float(event.confidence)
            + self.recency_weight * recency
            + self.relationship_weight * relationship
            + self.context_weight * context
        )
        return max(0.0, min(1.0, score))


@dataclass(frozen=True)
class EventObservation:
    observation_id: str
    event_id: str
    observer_id: str
    observed_at: float
    attention_score: float
    disposition: str = "noticed"
    relationship_salience: float = 0.0
    context_salience: float = 0.0
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = OBSERVATION_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ObservationLedger:
    """Append observations to the same durable event ledger."""

    def __init__(self, ledger: EventLedger) -> None:
        self.ledger = ledger

    def record(self, observation: EventObservation) -> EventObservation:
        self.ledger._append_record({  # intentional shared append-only primitive
            "record_kind": "event_observation",
            "record_version": OBSERVATION_SCHEMA_VERSION,
            **observation.to_dict(),
        })
        return observation

    def for_event(self, event_id: str) -> list[Dict[str, Any]]:
        return [
            row for row in self.ledger.records()
            if row.get("record_kind") == "event_observation"
            and row.get("event_id") == event_id
        ]


class PersistentEventObserver:
    """Observe events without mutating character state or taking action."""

    def __init__(
        self,
        ledger: EventLedger,
        policy: Optional[AttentionPolicy] = None,
    ) -> None:
        self.ledger = ledger
        self.policy = policy or AttentionPolicy()
        self.observations = ObservationLedger(ledger)

    def observe(
        self,
        event: Event,
        *,
        observer_id: str,
        relationship_salience: float = 0.0,
        context_salience: float = 0.0,
        disposition: str = "noticed",
        evidence_refs: tuple[str, ...] = (),
        now: Optional[float] = None,
    ) -> EventObservation:
        if not observer_id:
            raise ValueError("observer_id is required")
        score = self.policy.score(
            event,
            now=now,
            relationship_salience=relationship_salience,
            context_salience=context_salience,
        )
        observation = EventObservation(
            observation_id=str(uuid.uuid4()),
            event_id=event.event_id,
            observer_id=observer_id,
            observed_at=time.time() if now is None else float(now),
            attention_score=score,
            disposition=disposition,
            relationship_salience=max(0.0, min(1.0, float(relationship_salience))),
            context_salience=max(0.0, min(1.0, float(context_salience))),
            evidence_refs=tuple(evidence_refs),
        )
        return self.observations.record(observation)
