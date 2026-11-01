from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.alex_jeremy_bridge import AlexJeremyBridge
from modules.governance import GovernanceEngine
from modules.governance_routes import create_governance_router
from modules.pub_manager_authority import PubManagerAuthorityStore, create_pub_manager_control_router
from modules.pub_manager_decision import PubManagerDecisionEngine


def strong_evidence(**extra):
    return {
        "severity": 0.92,
        "confidence": 0.95,
        "security_risk": True,
        "repeat_count": 4,
        "incident_type": "room_safety",
        **extra,
    }


def test_permanent_actions_remain_human_required_even_during_critical_incident(tmp_path):
    engine = PubManagerDecisionEngine(tmp_path)
    decision = engine.evaluate(
        action="ban_user",
        urgency="critical",
        evidence=strong_evidence(data_loss_risk=True),
        ai_advisory={"recommendation": "approve", "confidence": 1.0},
    )
    assert decision["approved"] is False
    assert decision["status"] == "human_required"
    assert decision["authority_class"] == "D"
    assert decision["ai_advisory_decisive"] is False


def test_reversible_action_auto_approves_only_with_risk_urgency_and_bounded_lease(tmp_path):
    engine = PubManagerDecisionEngine(tmp_path)
    approved = engine.evaluate(
        action="freeze_actor",
        urgency="critical",
        evidence=strong_evidence(),
        requested_duration_seconds=60,
    )
    assert approved["approved"] is True
    assert approved["status"] == "auto_approved"
    assert approved["decision_source"] == "deterministic_policy"
    assert approved["rollback_action"] == "unfreeze_actor"

    too_long = engine.evaluate(
        action="freeze_actor",
        urgency="critical",
        evidence=strong_evidence(),
        requested_duration_seconds=900,
    )
    assert too_long["approved"] is False
    assert too_long["status"] == "pending_human"

    weak = engine.evaluate(
        action="freeze_actor",
        urgency="low",
        evidence={"severity": 0.2, "confidence": 0.9},
        requested_duration_seconds=60,
        ai_advisory={"recommendation": "approve"},
    )
    assert weak["approved"] is False
    assert weak["ai_advisory_decisive"] is False


def test_new_evidence_can_change_an_unconsumed_decision(tmp_path):
    store = PubManagerAuthorityStore(tmp_path)
    row = store.create_request(
        action="mute_user",
        target_user_id="u1",
        session_id="s1",
        packet_user_id="u1",
        requested_by="jeremy",
        urgency="high",
        evidence={"severity": 0.2, "confidence": 0.8},
        requested_duration_seconds=60,
    )
    assert row["status"] == "pending_human"

    stronger = store.add_evidence(
        row["request_id"],
        evidence=strong_evidence(),
        replace=True,
        submitted_by="sensor_fusion",
    )
    assert stronger["status"] == "auto_approved"
    assert stronger["approved"] is True
    assert stronger["evidence_history"][-1]["submitted_by"] == "sensor_fusion"

    weaker = store.add_evidence(
        row["request_id"],
        evidence={"severity": 0.1, "confidence": 0.95, "incident_type": "room_safety"},
        replace=True,
        submitted_by="new_camera_evidence",
    )
    assert weaker["approved"] is False
    assert weaker["status"] == "pending_human"


def test_blackbox_failure_blocks_automatic_authority(tmp_path):
    def fail_log(data_dir, event):
        raise RuntimeError("disk unavailable")

    store = PubManagerAuthorityStore(tmp_path, blackbox_logger=fail_log)
    row = store.create_request(
        action="freeze_actor",
        target_user_id="u1",
        session_id="s1",
        packet_user_id="u1",
        requested_by="jeremy",
        urgency="critical",
        evidence=strong_evidence(),
        requested_duration_seconds=60,
    )
    assert row["approved"] is False
    assert row["status"] == "blocked_audit_failure"
    assert store.health()["audit_failures"] == 1


def test_conditional_preferences_require_repeated_human_review_and_do_not_escalate_class_d(tmp_path):
    store = PubManagerAuthorityStore(tmp_path)
    context = {"severity": 0.4, "confidence": 0.9, "incident_type": "provider_failure", "subsystem": "inference"}
    for index in range(3):
        row = store.create_request(
            action="select_recovery_path",
            requested_by="owner",
            urgency="medium",
            evidence=context,
            metadata={"failure_mode": "timeout"},
        )
        store.decide(row["request_id"], approved=True, reviewer="owner", reason=f"review {index}")

    suggestion = store.engine.preferences.suggestion(
        action="select_recovery_path",
        evidence=context,
        metadata={"failure_mode": "timeout"},
    )
    assert suggestion is not None
    assert suggestion["preferred"] == "approve"

    ban = store.create_request(
        action="ban_user",
        target_user_id="u2",
        session_id="s2",
        packet_user_id="u2",
        requested_by="jeremy",
        urgency="critical",
        evidence=strong_evidence(incident_type="provider_failure", subsystem="inference"),
        metadata={"failure_mode": "timeout"},
    )
    assert ban["status"] == "human_required"
    assert ban["approved"] is False


def _make_live_authority_stack(tmp_path):
    events = []

    def blackbox(data_dir, event):
        events.append(event)

    store = PubManagerAuthorityStore(tmp_path, blackbox_logger=blackbox)
    bridge = AlexJeremyBridge(
        tmp_path,
        authority_reviewer=store.reviewer,
        blackbox_logger=blackbox,
        signal_cooldown_seconds=0,
    )
    gov = GovernanceEngine(tmp_path)
    app = FastAPI()
    app.include_router(create_governance_router(gov, authority_bridge=bridge, authority_store=store))
    return TestClient(app), store, bridge, gov, events


def test_governance_consumes_exact_auto_approval_once(tmp_path):
    client, store, bridge, gov, events = _make_live_authority_stack(tmp_path)
    row = store.create_request(
        action="mute_user",
        target_user_id="target",
        session_id="session-1",
        packet_user_id="target",
        requested_by="jeremy",
        urgency="critical",
        evidence=strong_evidence(),
        requested_duration_seconds=60,
    )
    assert row["status"] == "auto_approved"
    packet = bridge.signal_from_jeremy(
        user_id="target",
        session_id="session-1",
        room_state="critical",
        urgency="high",
        reason="temporary containment",
        payload={
            "requested_action": "mute_user",
            "authority_request_id": row["request_id"],
            "target_user_id": "target",
        },
    )
    assert packet["allowed_authority_action"] == "mute_user"

    payload = {
        "user_id": "target",
        "muted_by": "jeremy",
        "duration_seconds": 60,
        "authority_source": "alex_jeremy",
        "authority_request_id": row["request_id"],
        "authority_session_id": "session-1",
        "authority_user_id": "target",
    }
    first = client.post("/api/governance/mute", headers={"X-Client-Id": "jeremy"}, json=payload)
    assert first.status_code == 200, first.text
    assert gov.is_muted("target") is True
    final = store.get(row["request_id"])
    assert final["status"] == "executed"
    assert final["consumed_at"] is not None

    replay = client.post("/api/governance/mute", headers={"X-Client-Id": "jeremy"}, json=payload)
    assert replay.status_code == 403
    assert any(event["event_type"] == "pub_manager_execution_result" for event in events)


def test_human_approval_is_required_for_ban_then_executes_once(tmp_path):
    client, store, bridge, gov, _ = _make_live_authority_stack(tmp_path)
    row = store.create_request(
        action="ban_user",
        target_user_id="target",
        session_id="session-2",
        packet_user_id="target",
        requested_by="jeremy",
        urgency="critical",
        evidence=strong_evidence(),
    )
    assert row["status"] == "human_required"
    row = store.decide(row["request_id"], approved=True, reviewer="owner", reason="reviewed evidence")
    packet = bridge.signal_from_jeremy(
        user_id="target",
        session_id="session-2",
        room_state="critical",
        urgency="high",
        reason="human approved",
        payload={"requested_action": "ban_user", "authority_request_id": row["request_id"]},
    )
    assert packet["allowed_authority_action"] == "ban_user"

    response = client.post(
        "/api/governance/ban",
        headers={"X-Client-Id": "jeremy"},
        json={
            "user_id": "target",
            "issued_by": "jeremy",
            "reason": "reviewed",
            "ban_type": "session",
            "authority_source": "alex_jeremy",
            "authority_request_id": row["request_id"],
            "authority_session_id": "session-2",
            "authority_user_id": "target",
        },
    )
    assert response.status_code == 200, response.text
    assert gov.is_banned("target")[0] is True
    assert store.get(row["request_id"])["status"] == "executed"


def test_engineering_action_executes_through_registered_callback(tmp_path):
    calls = []

    async def executor(row):
        calls.append(row["action"])
        return {"saved": True}

    store = PubManagerAuthorityStore(tmp_path, executor=executor)
    app = FastAPI()
    app.include_router(create_pub_manager_control_router(store))
    client = TestClient(app)

    response = client.post(
        "/api/pubmanager/decisions",
        headers={"X-Client-Id": "owner"},
        json={
            "action": "emergency_save",
            "requested_by": "owner",
            "urgency": "critical",
            "evidence": {"severity": 0.8, "confidence": 0.95, "data_loss_risk": True},
            "execute_immediately": True,
        },
    )
    assert response.status_code == 200, response.text
    decision = response.json()["decision"]
    assert decision["status"] == "executed"
    assert decision["execution"]["result"]["saved"] is True
    assert calls == ["emergency_save"]
