from pathlib import Path

from modules.event_agency import Event, EventLedger, PersistentEventAgency


def test_event_is_append_only_and_reconstructs_status(tmp_path: Path):
    ledger = EventLedger(tmp_path / "events.jsonl")
    event = Event(
        event_id="e1",
        event_type="nudge",
        source="room_conductor",
        target="pete",
        payload={"room_id": "r1", "hint": "follow up"},
        priority=0.8,
    )
    ledger.append(event)
    ledger.transition("e1", "queued", metadata={"queue": "room:r1"})
    ledger.transition("e1", "delivered")

    rows = ledger.records()
    assert len(rows) == 3
    assert rows[0]["record_kind"] == "event"
    assert rows[1]["record_kind"] == "event_status"
    assert rows[2]["record_kind"] == "event_status"

    snapshot = ledger.snapshot()
    assert snapshot["e1"]["status"] == "delivered"
    assert snapshot["e1"]["payload"]["hint"] == "follow up"


def test_agency_clamps_scores_and_persists(tmp_path: Path):
    agency = PersistentEventAgency(tmp_path)
    event = agency.create(
        event_type="nudge",
        source="room_conductor",
        target="pete",
        payload={"room_id": "r1"},
        priority=9,
        confidence=-4,
        status="queued",
    )
    assert event.priority == 1.0
    assert event.confidence == 0.0
    assert agency.snapshot()[event.event_id]["status"] == "queued"


def test_event_model_does_not_grant_action_permission(tmp_path: Path):
    agency = PersistentEventAgency(tmp_path)
    event = agency.create(
        event_type="nudge",
        source="room_conductor",
        target="pete",
        payload={"action": "speak"},
        status="created",
    )
    row = agency.snapshot()[event.event_id]
    assert row["status"] == "created"
    assert "permission" not in row
    assert "authorized" not in row


def test_nudge_instrumentation_preserves_existing_signature():
    from modules.bots import BotManager
    import inspect

    signature = inspect.signature(BotManager.nudge)
    assert list(signature.parameters) == ["self", "room_id", "hint"]
