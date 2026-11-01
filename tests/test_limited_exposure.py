import pytest
from modules.limited_exposure import (
    DataClass, DataLabel, ExposurePurpose, LimitedCategory,
    LimitedExposurePolicy, blackbox_envelope, label_from_mapping,
    may_expose, shared_view,
)


def limited_label():
    return DataLabel(
        classification=DataClass.LIMITED,
        categories=frozenset({LimitedCategory.HEALTH, LimitedCategory.EMOTIONAL}),
        policy=LimitedExposurePolicy(
            allowed_consumers=frozenset({"system_alex"}),
            allowed_purposes=frozenset({ExposurePurpose.EMOTIONAL_ADJUDICATION}),
        ),
        subject_id="person-7",
        origin_event_id="evt-9",
    )


def test_standard_shared_view_passes_through():
    payload={"text":"ordinary"}
    assert shared_view(payload, DataLabel()) is payload


def test_limited_shared_view_never_copies_payload():
    payload={"text":"my brother died", "address":"123 Secret St"}
    view=shared_view(payload, limited_label())
    blob=str(view)
    assert "brother" not in blob and "Secret" not in blob
    assert view["classification"] == "LIMITED"
    assert view["details_withheld"] is True


def test_blackbox_gets_original_limited_payload_and_label():
    payload={"text":"private fact"}
    wrapped=blackbox_envelope(payload, limited_label())
    assert wrapped["payload"] == payload
    assert wrapped["data_handling"]["classification"] == "LIMITED"
    assert "HEALTH" in wrapped["data_handling"]["categories"]


def test_limited_access_is_default_deny_but_blackbox_is_always_allowed():
    label=limited_label()
    assert may_expose(label, consumer="system_alex", purpose=ExposurePurpose.EMOTIONAL_ADJUDICATION)
    assert not may_expose(label, consumer="jeremy", purpose=ExposurePurpose.EMOTIONAL_ADJUDICATION)
    assert may_expose(label, consumer="blackbox", purpose=ExposurePurpose.BLACKBOX_CAPTURE)


def test_derivatives_inherit_limited():
    derived=limited_label().inherited(origin_event_id="derived-1")
    assert derived.classification is DataClass.LIMITED
    assert derived.policy == limited_label().policy


def test_parser_defaults_limited_without_categories_to_user_designated():
    label=label_from_mapping({"classification":"LIMITED"})
    assert label.categories == frozenset({LimitedCategory.USER_DESIGNATED})


def test_unknown_classification_fails_closed():
    with pytest.raises(ValueError):
        label_from_mapping({"classification":"maybe_private"})


def test_blackbox_adapter_preserves_complete_limited_event():
    from blackbox_recorder.pubcast_event_adapter import map_pubcast_event
    import json
    event={
        "event_type":"chat.message", "source":"user", "actor":"person-7",
        "data_handling":{"classification":"LIMITED","categories":["HEALTH"]},
        "data":{"text":"sensitive text", "nested":{"diagnosis":"private"}},
    }
    mapped=map_pubcast_event(event)
    restored=json.loads(mapped.payload["raw_event_json"])
    assert restored == event
    assert mapped.payload["data_class"] == "LIMITED"

@pytest.mark.asyncio
async def test_limited_bridge_turn_is_not_written_to_shared_packet(tmp_path):
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    bridge=AlexJeremyBridge(data_dir=tmp_path)
    packet=await bridge.process_user_turn(
        user_id="u1", session_id="s1", text="sensitive personal context",
        metadata={"message_id":"m1", "data_handling":{
            "classification":"LIMITED", "categories":["PERSONAL_HISTORY"],
            "subject_id":"u1", "origin_event_id":"m1",
        }},
    )
    assert packet["data_class"] == "LIMITED"
    assert packet["shared_persistence_withheld"] is True
    assert packet["emotional_coordination"]["classification"] == "LIMITED"
    path=bridge._session_path("s1")
    if path.exists():
        assert "sensitive personal context" not in path.read_text(encoding="utf-8")
