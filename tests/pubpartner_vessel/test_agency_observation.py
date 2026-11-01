from pathlib import Path

from modules.agency_observation import AttentionPolicy, PersistentEventObserver
from modules.event_agency import EventLedger, PersistentEventAgency


def test_attention_score_is_bounded_and_deterministic(tmp_path: Path):
    agency = PersistentEventAgency(tmp_path)
    event = agency.create(
        event_type="nudge",
        source="room_conductor",
        target="pete",
        priority=0.8,
        confidence=1.0,
        status="queued",
    )
    policy = AttentionPolicy()
    a = policy.score(event, now=event.timestamp, relationship_salience=0.5, context_salience=0.5)
    b = policy.score(event, now=event.timestamp, relationship_salience=0.5, context_salience=0.5)
    assert 0.0 <= a <= 1.0
    assert a == b


def test_observation_is_distinct_from_event_status(tmp_path: Path):
    agency = PersistentEventAgency(tmp_path)
    event = agency.create(event_type="user_message", source="user", target="pete")
    observer = PersistentEventObserver(agency.ledger)
    observation = observer.observe(event, observer_id="pete", relationship_salience=0.9)

    rows = agency.ledger.records()
    assert any(r.get("record_kind") == "event" and r.get("event_id") == event.event_id for r in rows)
    assert any(r.get("record_kind") == "event_observation" and r.get("observation_id") == observation.observation_id for r in rows)
    assert event.status == "created"
    assert observation.event_id == event.event_id


def test_recency_decay_reduces_attention(tmp_path: Path):
    agency = PersistentEventAgency(tmp_path)
    event = agency.create(event_type="world_event", source="world")
    policy = AttentionPolicy(half_life_seconds=10.0)
    fresh = policy.score(event, now=event.timestamp, relationship_salience=0, context_salience=0)
    old = policy.score(event, now=event.timestamp + 100.0, relationship_salience=0, context_salience=0)
    assert fresh > old
