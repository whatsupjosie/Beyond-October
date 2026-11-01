from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from modules.pub_manager_authority import PubManagerAuthorityStore
from modules.pub_manager_decision import PubManagerDecisionEngine


def strong_evidence() -> dict:
    return {
        "severity": 0.96,
        "confidence": 0.98,
        "security_risk": True,
        "repeat_count": 5,
        "incident_type": "room_safety",
    }


def test_kick_and_ban_ignore_ai_self_approval_even_when_critical(tmp_path):
    engine = PubManagerDecisionEngine(tmp_path)
    for action in ("kick_user", "ban_user"):
        decision = engine.evaluate(
            action=action,
            urgency="critical",
            evidence=strong_evidence(),
            ai_advisory={"approved": True, "recommendation": "approve", "confidence": 1.0},
        )
        assert decision["approved"] is False
        assert decision["status"] == "human_required"
        assert decision["authority_class"] == "D"
        assert decision["ai_advisory_decisive"] is False


def _auto_freeze(store: PubManagerAuthorityStore) -> dict:
    row = store.create_request(
        action="freeze_actor",
        target_user_id="target-a",
        session_id="session-a",
        packet_user_id="target-a",
        requested_by="jeremy",
        urgency="critical",
        evidence=strong_evidence(),
        requested_duration_seconds=60,
    )
    assert row["approved"] is True
    return row


def test_authorization_cannot_be_reused_for_another_target_action_or_session(tmp_path):
    store = PubManagerAuthorityStore(tmp_path)
    row = _auto_freeze(store)
    cases = [
        {"action": "mute_user", "target_user_id": "target-a", "session_id": "session-a", "packet_user_id": "target-a"},
        {"action": "freeze_actor", "target_user_id": "target-b", "session_id": "session-a", "packet_user_id": "target-a"},
        {"action": "freeze_actor", "target_user_id": "target-a", "session_id": "session-b", "packet_user_id": "target-a"},
        {"action": "freeze_actor", "target_user_id": "target-a", "session_id": "session-a", "packet_user_id": "target-b"},
    ]
    for case in cases:
        with pytest.raises(PermissionError):
            store.validate_authorization(row["request_id"], requested_duration_seconds=60, **case)


def test_expired_authorization_is_not_executable(tmp_path):
    store = PubManagerAuthorityStore(tmp_path)
    row = _auto_freeze(store)
    path = store._path(row["request_id"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["expires_at"] = time.time() - 1
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PermissionError):
        store.validate_authorization(
            row["request_id"],
            action="freeze_actor",
            target_user_id="target-a",
            session_id="session-a",
            packet_user_id="target-a",
            requested_duration_seconds=60,
        )


def test_concurrent_consumers_get_exactly_one_use(tmp_path):
    store = PubManagerAuthorityStore(tmp_path)
    row = _auto_freeze(store)

    def consume(label: str) -> str:
        try:
            store.consume_authorization(row["request_id"], consumed_by=label)
            return "consumed"
        except PermissionError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, ["worker-a", "worker-b"]))
    assert sorted(results) == ["blocked", "consumed"]
