from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.alex_core import AIState, UserBattery
from modules.alex_jeremy_bridge import AlexJeremyBridge
from modules.governance import GovernanceEngine
from modules.governance_routes import create_governance_router


class FakeUserState:
    def __init__(self):
        self.stress_level = 0.0
        self.clarity_score = 1.0
        self.energy_level = 1.0

    def calculate_stress_score(self):
        return (self.stress_level * 0.5) + ((1 - self.clarity_score) * 0.3) + ((1 - self.energy_level) * 0.2)


class FakeMemory:
    def __init__(self):
        self.stored = []

    def recall(self, days_back=14, limit=5):
        return []

    def store(self, content, emotional_state):
        self.stored.append((content, emotional_state))


class FakeAlex:
    def __init__(self):
        self._current_state = AIState.GUIDE
        self._user_battery = UserBattery.CHARGED
        self._user_state = FakeUserState()
        self._cached_stress_score = 0.0
        self.memory = FakeMemory()

    def _update_ai_state(self):
        if self._user_state.calculate_stress_score() >= 0.7:
            self._current_state = AIState.ANCHOR

    def shutdown(self):
        pass


def make_bridge(tmp_path, *, cooldown=30, reviewer=None, blackbox_logger=None):
    events = []

    def logger(data_dir, event):
        events.append(event)

    bridge = AlexJeremyBridge(
        tmp_path,
        authority_reviewer=reviewer,
        blackbox_logger=blackbox_logger or logger,
        signal_cooldown_seconds=cooldown,
    )
    fake = FakeAlex()
    bridge.alex_for = lambda user_id: fake
    return bridge, fake, events


def test_entry_packet_logs_scrubbed_bridge_event(tmp_path):
    bridge, fake, events = make_bridge(tmp_path)

    packet = bridge.build_entry_packet(
        user_id="user/private id",
        session_id="session-1",
        project_id="prime",
        room_id="studio",
        display_name="User",
    )

    assert packet["bridge_scope"] == "entry"
    assert packet["blackbox_recorded"] is True
    assert fake.memory.stored
    assert events[-1]["event_type"] == "alex_entry_packet"
    assert events[-1]["user_id"] == "user_private_id"
    assert "raw_text" not in events[-1]
    assert "private_profile" not in events[-1]


def test_nonurgent_jeremy_signal_is_cooldown_suppressed(tmp_path):
    bridge, _, events = make_bridge(tmp_path, cooldown=60)

    first = bridge.signal_from_jeremy(
        user_id="u1",
        session_id="s1",
        room_state="stable",
        urgency="low",
        reason="first check",
        payload={"room_id": "room-a"},
    )
    second = bridge.signal_from_jeremy(
        user_id="u1",
        session_id="s1",
        room_state="stable",
        urgency="low",
        reason="repeat check",
        payload={"room_id": "room-a"},
    )

    assert first["bridge_scope"] == "signal_response"
    assert second["bridge_scope"] == "cooldown_suppressed"
    assert second["latest_signal"]["suppressed"] is True
    assert [event["event_type"] for event in events][-2:] == [
        "jeremy_signal_applied",
        "jeremy_signal_suppressed",
    ]


def test_unapproved_authority_request_is_blocked_not_executable(tmp_path):
    bridge, _, events = make_bridge(tmp_path, cooldown=60)

    bridge.signal_from_jeremy(
        user_id="u1",
        session_id="s1",
        room_state="stable",
        urgency="low",
        reason="first check",
        payload={"room_id": "room-a"},
    )
    packet = bridge.signal_from_jeremy(
        user_id="u1",
        session_id="s1",
        room_state="tense",
        urgency="low",
        reason="possible unsafe actor",
        payload={"room_id": "room-a", "requested_action": "freeze_actor"},
    )

    assert packet["bridge_scope"] == "signal_response"
    assert packet["authority_review"]["requires_authority"] is True
    assert packet["authority_review"]["approved"] is False
    assert packet["authority_review"]["action_allowed"] is False
    assert packet["authority_status"] == "blocked_pending_authority"
    assert packet["blocked_authority_action"] == "freeze_actor"
    assert "allowed_authority_action" not in packet
    with pytest.raises(PermissionError):
        bridge.assert_authority_action_allowed(packet, "freeze_actor")
    assert events[-1]["status"] == "authority_required"
    assert events[-1]["authority_action"] == "freeze_actor"


def test_approved_authority_request_becomes_explicitly_executable(tmp_path):
    def reviewer(signal):
        return {
            "reviewer": "pub_manager",
            "approved": True,
            "decision": "temporary_freeze_approved",
            "requires_authority": True,
        }

    bridge, _, _ = make_bridge(tmp_path, cooldown=0, reviewer=reviewer)
    packet = bridge.signal_from_jeremy(
        user_id="u1",
        session_id="s1",
        room_state="critical",
        urgency="high",
        reason="freeze requested",
        payload={"requested_action": "freeze_actor"},
    )

    review = packet["authority_review"]
    assert review["reviewer"] == "pub_manager"
    assert review["approved"] is True
    assert review["action_allowed"] is True
    assert packet["authority_status"] == "approved"
    assert packet["allowed_authority_action"] == "freeze_actor"
    bridge.assert_authority_action_allowed(packet, "freeze_actor")


def test_private_signal_payload_is_not_written_to_bridge_event_or_latest_signal(tmp_path):
    bridge, _, events = make_bridge(tmp_path, cooldown=0)

    packet = bridge.signal_from_jeremy(
        user_id="u1",
        session_id="s1",
        room_state="destabilizing",
        urgency="medium",
        reason="care-sensitive handoff",
        payload={
            "room_id": "room-a",
            "raw_text": "do not write this",
            "private_cue": "do not write this either",
        },
    )

    assert "payload" not in packet["latest_signal"]
    assert "raw_text" not in events[-1]
    assert "private_cue" not in events[-1]
    assert events[-1]["reason"] == "care-sensitive handoff"


def test_blackbox_failure_is_visible_on_packet_and_bridge_health(tmp_path):
    def failing_logger(data_dir, event):
        raise RuntimeError("blackbox offline")

    bridge, _, _ = make_bridge(tmp_path, blackbox_logger=failing_logger)
    packet = bridge.build_entry_packet(
        user_id="u1",
        session_id="s1",
        project_id="prime",
        room_id="studio",
    )

    assert packet["blackbox_recorded"] is False
    health = bridge.bridge_health()
    assert health["blackbox_failures"] == 1
    assert health["last_blackbox_failure"]["status"] == "blackbox_record_failed"

def test_reviewer_cannot_downgrade_hard_authority_action(tmp_path):
    def reviewer(signal):
        return {
            "reviewer": "bad_reviewer",
            "approved": False,
            "requires_authority": False,
            "decision": "attempted_downgrade",
        }

    bridge, _, _ = make_bridge(tmp_path, cooldown=0, reviewer=reviewer)
    packet = bridge.signal_from_jeremy(
        user_id="u1",
        session_id="s1",
        room_state="tense",
        urgency="low",
        reason="freeze requested",
        payload={"requested_action": "freeze_avatar"},
    )

    review = packet["authority_review"]
    assert review["requested_action"] == "freeze_actor"
    assert review["requires_authority"] is True
    assert review["action_allowed"] is False
    assert packet["authority_status"] == "blocked_pending_authority"


def test_approved_authority_request_is_blocked_when_blackbox_recording_fails(tmp_path):
    def reviewer(signal):
        return {"reviewer": "pub_manager", "approved": True, "decision": "approved"}

    def failing_logger(data_dir, event):
        raise RuntimeError("blackbox offline")

    bridge, _, _ = make_bridge(
        tmp_path,
        cooldown=0,
        reviewer=reviewer,
        blackbox_logger=failing_logger,
    )
    packet = bridge.signal_from_jeremy(
        user_id="u1",
        session_id="s1",
        room_state="critical",
        urgency="high",
        reason="freeze requested",
        payload={"requested_action": "freeze_actor"},
    )

    assert packet["blackbox_recorded"] is False
    assert packet["authority_review"]["decision"] == "blocked_blackbox_record_failed"
    assert packet["authority_review"]["action_allowed"] is False
    assert packet["authority_status"] == "blocked_blackbox_record_failed"
    assert packet["blocked_authority_action"] == "freeze_actor"
    assert "allowed_authority_action" not in packet
    with pytest.raises(PermissionError):
        bridge.assert_authority_action_allowed(packet, "freeze_actor")


def make_governance_client(tmp_path, bridge):
    app = FastAPI()
    gov = GovernanceEngine(tmp_path)
    app.include_router(create_governance_router(gov, authority_bridge=bridge))
    return TestClient(app), gov


def test_governance_freeze_route_rejects_unapproved_bridge_packet_before_mutation(tmp_path):
    bridge, _, _ = make_bridge(tmp_path, cooldown=0)
    bridge.signal_from_jeremy(
        user_id="target-user",
        session_id="session-1",
        room_state="tense",
        urgency="low",
        reason="possible unsafe actor",
        payload={"requested_action": "freeze_actor"},
    )
    client, gov = make_governance_client(tmp_path, bridge)

    response = client.post(
        "/api/governance/freeze",
        headers={"X-Client-Id": "mod-1"},
        json={
            "user_id": "target-user",
            "frozen_by": "mod-1",
            "reason": "Jeremy requested review",
            "authority_source": "alex_jeremy",
            "authority_session_id": "session-1",
        },
    )

    assert response.status_code == 403
    frozen, _ = gov.is_frozen("target-user")
    assert frozen is False


def test_governance_freeze_route_accepts_server_loaded_approved_bridge_packet(tmp_path):
    def reviewer(signal):
        return {"reviewer": "pub_manager", "approved": True, "decision": "freeze_approved"}

    bridge, _, _ = make_bridge(tmp_path, cooldown=0, reviewer=reviewer)
    bridge.signal_from_jeremy(
        user_id="target-user",
        session_id="session-1",
        room_state="critical",
        urgency="high",
        reason="temporary freeze approved",
        payload={"requested_action": "freeze_actor"},
    )
    client, gov = make_governance_client(tmp_path, bridge)

    response = client.post(
        "/api/governance/freeze",
        headers={"X-Client-Id": "mod-1"},
        json={
            "user_id": "target-user",
            "frozen_by": "mod-1",
            "reason": "Pub Manager approved temporary freeze",
            "authority_source": "alex_jeremy",
            "authority_session_id": "session-1",
        },
    )

    assert response.status_code == 200
    frozen, state = gov.is_frozen("target-user")
    assert frozen is True
    assert state.frozen_by == "mod-1"


def test_governance_freeze_route_rejects_client_supplied_authority_packet(tmp_path):
    bridge, _, _ = make_bridge(tmp_path, cooldown=0)
    client, gov = make_governance_client(tmp_path, bridge)

    response = client.post(
        "/api/governance/freeze",
        headers={"X-Client-Id": "mod-1"},
        json={
            "user_id": "target-user",
            "frozen_by": "mod-1",
            "authority_source": "alex_jeremy",
            "authority_packet": {"allowed_authority_action": "freeze_actor"},
        },
    )

    assert response.status_code == 400
    frozen, _ = gov.is_frozen("target-user")
    assert frozen is False
